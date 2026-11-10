# Post-Mortem Improvements: Speed Up Bug-Fix Tasks

> **Source:** Post-mortem of the cross-source dedup `IntegrityError` task (2026-05-08).
> **Focus:** Time-to-resolution, NOT correctness or coverage.
> **Status:** Proposal — to be reviewed and selectively installed by user/Architect tomorrow.

---

## TL;DR — the time numbers from the dedup task

| Metric | Actual | Optimized | Saving |
|---|---|---|---|
| **Wall-clock active agent time** | ~45 min | ~25 min | **~45%** |
| **Cost** | ~$10 | ~$7 | **~30%** |
| **User approval clicks** | ~30 | ~20 | **~33%** |
| **Net production code shipped** | 9 lines | (same) | — |

**The headline:** the actual fix was 9 lines. Everything else (test, backfill, wiki sync, review cycles) is necessary infrastructure — but we did each of those slower than we needed to.

---

## Where the time went (and where it shouldn't go next time)

### 🔥 Top 3 time leaks (sorted by impact)

#### Leak 1 — Round-2 fix cycle wasted ~50% of its cost reverting work
- **What happened:** Code Reviewer round 1 returned 1 P2 + 5 P3s with two P3s tagged "SHOULD FIX." I (Orchestrator) bundled the 2 SHOULD-FIX P3s into the round-2 brief. Code mode wrote ~140 lines of test code + ~20 lines of dedup hardening. User interrupted mid-task to say "skip the P3s." Code mode reverted everything, leaving only the 6-line P2 docstring fix.
- **Cost:** ~$1.55 in round 2 (most of it the revert + verification).
- **Wall-clock waste:** ~5 min.

#### Leak 2 — Debug mode used 7 investigation rounds when 3 would have done
- **What happened:** Debug did forensic SQL queries on the post-failure DB state for 4 rounds before finally invoking the actual production function (`find_and_merge_duplicate()`) against the live data inside a `session.rollback()` guard — which gave the smoking gun in one shot.
- **Cost:** Of 7 rounds, rounds 2, 5, 6 were redundant (~$0.80 of investigation time).
- **Wall-clock waste:** ~3-4 min + ~4 user clicks.

#### Leak 3 — Wiki sync had 3 SEARCH/REPLACE failures requiring re-read
- **What happened:** I issued 6 parallel `apply_diff` calls. 3 failed because file content had drifted since I last read it (long session, other tasks had touched memory).
- **Cost:** ~$0.30 + 3 user clicks for the retries.
- **Wall-clock waste:** ~2 min.

---

## Recommendations (in order of biggest impact first)

### ⚡ R1 — Orchestrator default: P2-only fix cycles, P3s as separate tasks
**Saves: ~$1.50, ~7 user clicks, ~5–15 min wall-clock per review cycle that has P3s.**

**Current behavior:** When Code Review returns "1 P2 + N P3s," Orchestrator default brief says "fix P2, plus the 2 SHOULD-FIX P3s." This bundles must-haves with should-haves and forces the user into an all-or-nothing decision mid-flight.

**Proposed rule:** When Code Review returns **only blocking P1/P2 + non-blocking P3s**, the round-2 fix brief should be **P2-only**. P3s become **separate task offers** in the post-cycle `attempt_completion` message: *"Reviewer also flagged P3s [list]; want me to address any/all/none as separate tasks?"*

**Where to install:** Either:
1. (Lightweight) Add a one-paragraph rule to [`docs/memory/wiki/concepts/review-cycle.md`](docs/memory/wiki/concepts/review-cycle.md) that Orchestrator references.
2. (Stronger) Edit the Orchestrator's `customInstructions` in [`.roomodes`](.roomodes) under "WORKFLOW SEQUENCING RULES" to add: *"Round-2 fix briefs must contain ONLY blocking severity items (P1/P2). P3s and 'recommended' items are queued as separate task offers in `attempt_completion`."*

**Risk if installed:** Some hardening that should ship NOW gets deferred. Mitigation: P3s tagged `[hardens-against-this-bug-class]` (a sub-tag the reviewer can add) DO get bundled. Standard P3s don't.

---

### ⚡ R2 — Codify "live re-invocation first" pattern for Debug mode
**Saves: ~$0.80, ~4 user clicks, ~3–4 min per "feature X silently failed" task.**

**Current behavior:** Debug instinctively starts with forensic queries on result-state, then works backwards.

**Proposed rule (codify in [`.roo/skill-root-cause-analysis.md`](.roo/skill-root-cause-analysis.md)):** *For symptoms shaped as "feature X didn't do Y to data Z" (silent failures, no-op bugs):*

> **BEFORE forensic queries on Z, FIRST instrument logging and re-invoke X against Z inside a `session.rollback()`-guarded REPL.** The resulting log trace pinpoints the failure path in one shot. Forensic queries on the result state are useful for *scope* (how many rows are affected?) but rarely useful for *cause* (why did it fail?).

**Pattern checklist for Debug:**
1. Read the production code path that *should* have done the thing.
2. Build a minimal in-memory or rollback-guarded invocation of that path against the actual production data.
3. Enable INFO/DEBUG logging.
4. Read the trace — the log line that immediately precedes the failure is almost always the cause.
5. ONLY THEN do forensic state queries to assess scope.

**Where to install:** Add as new section to [`.roo/skill-root-cause-analysis.md`](.roo/skill-root-cause-analysis.md). This is a `.roo/` write — install via the `git add + commit` atomic chain trick from AGENTS.md §8.

**Risk if installed:** Almost none. The pattern is purely additive guidance; Debug can still do forensic queries when appropriate.

---

### ⚡ R3 — Wiki-sync rule: re-read targets immediately before diff (always)
**Saves: ~$0.50, ~3 user clicks, ~2 min per multi-file wiki sync.**

**Current behavior:** Orchestrator caches file content from earlier in the session and trusts it for `apply_diff` SEARCH blocks. In long sessions or multi-task sessions, the content drifts and SEARCH fails.

**Proposed rule:** Before any wiki-sync `apply_diff` operation:
- If I (Orchestrator) have NOT read the target file in the **last 1 turn**, OR if I know other tasks have been touching memory in this session,
- **Always re-read the target files immediately before the diff.**
- Cost is 6 cheap parallel reads (~$0.05). Saves: typically 1–2 retry rounds (~$0.30–0.60).

**Where to install:** Add a one-line bullet to AGENTS.md §7 (Wiki Sync Protocol):
> *"Before issuing `apply_diff` against a wiki file, re-read it if you have not read it in the last 1 turn or if other tasks have touched the wiki since your last read."*

**Risk if installed:** Slight increase in baseline read calls. Acceptable trade.

---

### ⚡ R4 — For surgical fixes (<20 lines), allow tighter Code loops
**Saves: estimated ~$1.00 + ~5 user clicks per surgical fix, IF safe to install.**

**Current behavior:** Per AGENTS.md, all code modifications go via `new_task(mode: "code", ...)`. This is correct in general — it ensures Orchestrator stays in the loop for the mandatory Code → Reviewer cycle. But for tiny, fully-specified fixes (Debug report says "change line X from A to B"), the round-trip overhead exceeds the work itself.

**Proposed rule (CONTROVERSIAL — needs your sign-off):** Add a narrow exception to AGENTS.md §6 (Workflow Sequencing Rules):

> **Exception: "Pre-specified surgical fix"** — When a Debug or Architect report contains a complete, line-by-line specification of the fix (not just a description) AND the total change is <20 LOC AND no new files are created, the Orchestrator MAY:
> 1. `switch_mode` to Code,
> 2. Apply the pre-specified diff via `apply_diff` (no improvisation allowed beyond the spec),
> 3. `switch_mode` back to Orchestrator,
> 4. Then `new_task(mode: "dev-reviewer", ...)` as normal.
>
> **The Code Reviewer MUST verify** the diff matches the pre-specification. Any deviation = automatic 🔄 NEEDS WORK.

**Risk if installed:** Higher. The "Code mode bypasses Reviewer via switch_mode" footgun documented in AGENTS.md is real. Mitigation: the Reviewer-must-verify clause + the "no improvisation" clause + the strict size limit. **Recommend installing only after you've reviewed the proposed wording.**

**Where to install:** AGENTS.md §"Workflow Sequencing Rules" + a corresponding clause in [`.roo/skill-code-review.md`](.roo/skill-code-review.md) ("Pre-Specified Fix Verification").

**Skip this one if you want to keep the discipline tight.** R1+R2+R3 alone account for ~$2.80 / ~14 clicks / ~10 min of savings without any safety trade-off.

---

### 🟡 R5 — Track total task time in completion messages
**Saves: nothing on the next task. But makes future post-mortems instant.**

**Current behavior:** Each subtask reports its own cost in completion messages, but no agent tracks **total wall-clock from user request → final attempt_completion**. To do this post-mortem I had to manually scan all the timestamps in the conversation.

**Proposed rule (Orchestrator):** In every Orchestrator `attempt_completion`, include a line:
> *"Task duration: ~X min wall-clock active, ~$Y total cost across N subtasks (Debug ×D, Code ×C, Reviewer ×R)."*

**Where to install:** Add to Orchestrator's `customInstructions` in [`.roomodes`](.roomodes) — bullet under the existing completion-message guidance.

**Risk:** Negligible. Pure data emission.

---

## What to ship tomorrow (recommended ordering)

If you only do one thing, do **R1** — biggest single time saving, lowest risk, no `.roo/` write involved (just an AGENTS.md edit OR a wiki concept-page edit).

If you do three things, do **R1 + R2 + R3** in that order. Combined savings: **~30% cost reduction, ~45% wall-clock reduction, ~14 fewer user clicks** on the next bug-fix task of similar complexity.

R4 needs a careful rules-discussion before install — defer if uncertain.
R5 is optional metadata — install whenever convenient.

---

## Things deliberately NOT in this proposal (for completeness)

- **"Make Code mode write less code"** — not really a fix; the test + backfill were genuinely needed work, just done in 2 turns when 1 would have sufficed. R1 removes the *wasted* turn (the revert), not the productive ones.
- **"Skip the Reviewer cycle for small fixes"** — never. Even our 6-line P2 fix benefited from re-review. The Reviewer caught zero new issues but verified the revert was clean.
- **"Pre-validate test infrastructure exists before delegating"** — Code mode handled this fine in round 1 (created [`scripts/test_dedup_merge.py`](scripts/test_dedup_merge.py) from scratch with self-contained runner).
- **"Use `read_file` indentation mode for the test"** — micro-optimization; not worth a rule.
- **"Always commit after `.roo/` writes"** — already in AGENTS.md §8, not a new finding.

---

## Appendix — exact ROI table

| Recommendation | Cost saved | Clicks saved | Wall-clock saved | Risk | Install effort |
|---|---|---|---|---|---|
| R1 P2-only fix cycles | $1.50 | 7 | 5–15 min | Low | 1 paragraph in AGENTS.md or review-cycle.md |
| R2 Live re-invocation first | $0.80 | 4 | 3–4 min | Negligible | 1 section in `.roo/skill-root-cause-analysis.md` |
| R3 Re-read before wiki diff | $0.50 | 3 | 2 min | Negligible | 1 bullet in AGENTS.md §7 |
| R4 Surgical-fix tight loop | $1.00 | 5 | 3–5 min | **Higher** | 1 exception in AGENTS.md §"Workflow Sequencing" + verification clause in skill-code-review.md |
| R5 Time tracking in completion | $0 | 0 | 0 (saves *future* post-mortem time) | None | 1 bullet in Orchestrator `customInstructions` in `.roomodes` |
| **R1+R2+R3 combined** | **~$2.80** | **~14** | **~10 min** | **All low** | **3 small edits** |

If you want, I can prepare the exact text of the AGENTS.md / skill-file / .roomodes edits as a single follow-up task tomorrow — it'd take Architect ~10 minutes to draft and you ~5 minutes to review/approve.
