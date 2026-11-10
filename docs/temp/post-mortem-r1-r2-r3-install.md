# Post-Mortem R1 + R2 + R3 — Install Spec

> **Status:** Architect-authored install instructions. R1 + R3 were applied directly by Architect (`.md` files within edit perms). **R2 requires user action** because it writes to `.roo/` (see AGENTS.md §8).
> **Source proposal:** [`docs/temp/post-mortem-dedup-fix-improvements.md`](post-mortem-dedup-fix-improvements.md)
> **Author:** 🏗️ Architect
> **Date:** 2026-05-10

---

## What's already done (no user action needed)

| # | Change | File | Status |
|---|--------|------|--------|
| R1.a | New section "Severity-based fix-cycle scope" | [`docs/memory/wiki/concepts/review-cycle.md`](../memory/wiki/concepts/review-cycle.md) | ✅ applied by Architect |
| R1.b | New bullet #5 under "Mandatory Code → Review → Fix Cycle" | [`AGENTS.md`](../../AGENTS.md) §"Workflow Sequencing Rules" | ✅ applied by Architect |
| R1 supporting | New backlog file with 9 pre-populated P3 rows + schema | [`docs/memory/p3-backlog.md`](../memory/p3-backlog.md) | ✅ created by Architect |
| R1 cleanup | Migrate inline P3 lists out of activeContext to backlog | [`docs/memory/tasks/default/activeContext.md`](../memory/tasks/default/activeContext.md) | ✅ applied by Architect |
| R3 | New bullet #6 under §7 Wiki Sync Protocol — re-read before `apply_diff` | [`AGENTS.md`](../../AGENTS.md) §7 | ✅ applied by Architect |
| Index timestamp | Bump "Last sync" to 2026-05-10 | [`docs/memory/wiki/index.md`](../memory/wiki/index.md) | ✅ applied by Architect |

**R2 alone is pending — see below.**

---

## R2 — Install instructions (USER ACTION REQUIRED)

### What R2 does

Adds a new section, **"Pattern: Live Re-Invocation First"**, near the top of [`.roo/skill-root-cause-analysis.md`](../../.roo/skill-root-cause-analysis.md) (immediately after `## When to Use`, before `## The 5 Whys`). The pattern codifies a Debug-mode *first move* heuristic for silent-failure / no-op symptom shapes.

### Why it can't be done by an agent

Per AGENTS.md §8, all writes to `.roo/` are reverted by a system hook within minutes — *unless* the write is followed by `git add .roo/ && git commit -m "..."` in the **same atomic `execute_command` chain**. Roo agents cannot reliably guarantee atomicity around `apply_diff` (the diff applies via a separate code path from `execute_command`), so this install must be a single shell command run by the user.

### The exact section to insert

The block below is the new content. It is written so a Python heredoc-based inserter (next subsection) can place it in the right spot without touching the rest of the file.

```markdown
---

## Pattern: Live Re-Invocation First (Silent Failures & No-Ops)

> **Default first move when the symptom is shaped "feature X didn't do Y to data Z" (silent failure, no-op bug):** BEFORE running forensic queries on the result-state Z, instrument logging on X and **re-invoke X against Z inside a `session.rollback()`-guarded REPL**. The resulting log trace pinpoints the failure path in one shot.

### Why this beats forensic-first

Forensic queries on the post-failure state tell you **scope** ("how many rows are stuck?"), but rarely **cause** ("why did the merge no-op?"). The cause is encoded in control-flow you can't see from data alone — `try`/`except` swallow points, early-return guards, conditional branches that didn't fire. A live re-invocation with INFO/DEBUG logging surfaces the missing log line in one round.

### The 5-step pattern

1. **Read the production code path** that *should* have done the thing. Identify the function name and entry point.
2. **Build a minimal rollback-guarded invocation** of that path against the actual production data:
   ```python
   from src.database import session_scope
   from src.dedup import find_and_merge_duplicate
   import logging; logging.basicConfig(level=logging.DEBUG)

   with session_scope() as s:
       try:
           result = find_and_merge_duplicate(s, listing_id=12345)
           print("RESULT:", result)
       finally:
           s.rollback()  # never commit during diagnosis
   ```
3. **Enable INFO/DEBUG logging** on the relevant logger(s). Do this BEFORE the invocation so the very first call is captured.
4. **Read the trace top-down.** The log line *immediately preceding the silent failure* is almost always the cause — usually a logged-but-swallowed exception or a conditional that returned early.
5. **Only then** run forensic queries on the result-state to assess scope ("how many other rows are affected?") — now that you know the cause, scope queries take seconds.

### Worked example: 2026-05-08 cross-source dedup `IntegrityError` silent no-op

**Symptom:** Cross-source dedup scoring correctly identified duplicates, but **zero merges had occurred for ~6 weeks**. No errors in logs. `notification_log` showed no failures.

**Anti-pattern that wasted ~$0.80 / ~4 user clicks / ~3-4 min** (rounds 2, 5, 6 of the 7-round investigation): Debug ran SQL queries against `listings` + `listing_sources` + `dedup_decision_log` looking for the missing merge rows. Found nothing — because the merges had been silently rolled back, leaving no trace.

**The one-shot fix that actually worked** (round 7): Debug invoked `find_and_merge_duplicate(session, listing_id=…)` inside a `session.rollback()`-guarded REPL with `logger.setLevel(DEBUG)`. The trace immediately surfaced:

```
DEBUG src.dedup  Inserting ListingSource(listing_id=42, source='craigslist', external_id='cl-7891') ...
WARNING src.dedup  possible race condition during merge: (sqlite3.IntegrityError) UNIQUE constraint failed: ...uq_ls_source_external_id
```

That single DEBUG → WARNING transition pinpointed the broad `except IntegrityError` block in `_merge_duplicate()` that was masking the bug as a fake race condition. **Total time from REPL start to root cause: ~30 seconds.** Fix was 9 production lines.

### When to skip this pattern

- Symptom is a **crash with stack trace** — read the stack, no re-invocation needed.
- Symptom is **"feature X is slow"** — profile, don't re-invoke.
- Symptom is **a UI rendering bug** — `curl` the page; the rendered HTML is your evidence.
- The data Z required to reproduce X **doesn't exist anymore** (DB pruned, log rotated). Then forensic-first is the only option.

For everything else shaped "X didn't do Y to Z," default to live re-invocation first.

---
```

### The atomic install command

Run this **as a single command** in your terminal (one paste, one Enter). It uses Python to insert the new section at the exact anchor (`## When to Use` block end), then immediately `git add` + `git commit` so the §8 system hook sees a tracked file and leaves it alone.

```bash
cd /Users/mvaturri/Documents/zillow && \
python3 - <<'PYEOF' && \
git add .roo/skill-root-cause-analysis.md && \
git commit -m "R2: add Live Re-Invocation First pattern to skill-root-cause-analysis" && \
echo "✅ R2 installed and committed"
import re, pathlib

path = pathlib.Path(".roo/skill-root-cause-analysis.md")
src = path.read_text()

new_section = '''---

## Pattern: Live Re-Invocation First (Silent Failures & No-Ops)

> **Default first move when the symptom is shaped "feature X didn't do Y to data Z" (silent failure, no-op bug):** BEFORE running forensic queries on the result-state Z, instrument logging on X and **re-invoke X against Z inside a `session.rollback()`-guarded REPL**. The resulting log trace pinpoints the failure path in one shot.

### Why this beats forensic-first

Forensic queries on the post-failure state tell you **scope** ("how many rows are stuck?"), but rarely **cause** ("why did the merge no-op?"). The cause is encoded in control-flow you can't see from data alone — `try`/`except` swallow points, early-return guards, conditional branches that didn't fire. A live re-invocation with INFO/DEBUG logging surfaces the missing log line in one round.

### The 5-step pattern

1. **Read the production code path** that *should* have done the thing. Identify the function name and entry point.
2. **Build a minimal rollback-guarded invocation** of that path against the actual production data:
   ```python
   from src.database import session_scope
   from src.dedup import find_and_merge_duplicate
   import logging; logging.basicConfig(level=logging.DEBUG)

   with session_scope() as s:
       try:
           result = find_and_merge_duplicate(s, listing_id=12345)
           print("RESULT:", result)
       finally:
           s.rollback()  # never commit during diagnosis
   ```
3. **Enable INFO/DEBUG logging** on the relevant logger(s). Do this BEFORE the invocation so the very first call is captured.
4. **Read the trace top-down.** The log line *immediately preceding the silent failure* is almost always the cause — usually a logged-but-swallowed exception or a conditional that returned early.
5. **Only then** run forensic queries on the result-state to assess scope ("how many other rows are affected?") — now that you know the cause, scope queries take seconds.

### Worked example: 2026-05-08 cross-source dedup `IntegrityError` silent no-op

**Symptom:** Cross-source dedup scoring correctly identified duplicates, but **zero merges had occurred for ~6 weeks**. No errors in logs. `notification_log` showed no failures.

**Anti-pattern that wasted ~$0.80 / ~4 user clicks / ~3-4 min** (rounds 2, 5, 6 of the 7-round investigation): Debug ran SQL queries against `listings` + `listing_sources` + `dedup_decision_log` looking for the missing merge rows. Found nothing — because the merges had been silently rolled back, leaving no trace.

**The one-shot fix that actually worked** (round 7): Debug invoked `find_and_merge_duplicate(session, listing_id=...)` inside a `session.rollback()`-guarded REPL with `logger.setLevel(DEBUG)`. The trace immediately surfaced:

```
DEBUG src.dedup  Inserting ListingSource(listing_id=42, source='craigslist', external_id='cl-7891') ...
WARNING src.dedup  possible race condition during merge: (sqlite3.IntegrityError) UNIQUE constraint failed: ...uq_ls_source_external_id
```

That single DEBUG -> WARNING transition pinpointed the broad `except IntegrityError` block in `_merge_duplicate()` that was masking the bug as a fake race condition. **Total time from REPL start to root cause: ~30 seconds.** Fix was 9 production lines.

### When to skip this pattern

- Symptom is a **crash with stack trace** — read the stack, no re-invocation needed.
- Symptom is **"feature X is slow"** — profile, don't re-invoke.
- Symptom is **a UI rendering bug** — `curl` the page; the rendered HTML is your evidence.
- The data Z required to reproduce X **doesn't exist anymore** (DB pruned, log rotated). Then forensic-first is the only option.

For everything else shaped "X didn't do Y to Z," default to live re-invocation first.

'''

# Anchor: insert immediately after the "## When to Use" block,
# i.e., before the next "---" separator that precedes "## The 5 Whys".
anchor = "- Recurring bug (\"we fixed this last week, why is it back?\")\n\n---\n"
if anchor not in src:
    raise SystemExit("ANCHOR NOT FOUND - file may have changed; aborting before write.")
if "Pattern: Live Re-Invocation First" in src:
    raise SystemExit("Section already present - aborting to avoid duplicate insert.")

# Replace the trailing "---\n" with "---\n\n<new_section>" so the new section
# sits between "When to Use" and "The 5 Whys" with proper separator hygiene.
src2 = src.replace(anchor, anchor + "\n" + new_section, 1)

path.write_text(src2)
print(f"INSERTED {len(new_section)} chars; new file length {len(src2)} chars.")
PYEOF
```

#### Why this exact recipe

- **`cd` first, then chain with `&&`** — guarantees we run from the workspace root.
- **Python heredoc** — handles the multi-line insert cleanly without `sed`/`awk` escape gymnastics. `<<'PYEOF'` (single-quoted) prevents shell expansion of `$`, backticks, etc. inside the script body.
- **Anchor-based insert with `if anchor not in src: raise`** — fails loudly if the file has drifted since this spec was authored (rather than corrupting it).
- **`if "Pattern: Live Re-Invocation First" in src: raise`** — idempotent: re-running the command is a no-op instead of a double-insert.
- **`git add .roo/...` + `git commit` in same chain** — beats the §8 hook per the documented `git commit` bypass.
- **Final `echo "✅ R2 installed and committed"`** — visible success signal.

### If the anchor check fails

Means [`.roo/skill-root-cause-analysis.md`](../../.roo/skill-root-cause-analysis.md) has been edited since 2026-05-10. Re-read the file, locate the "When to Use" block, and adjust the `anchor` string in the Python heredoc above to match the new exact text. The rest of the recipe is unchanged.

### If the commit step fails (working tree dirty)

You may have other uncommitted changes. Either commit them first, or change the `git add` line to `git add .roo/skill-root-cause-analysis.md` (path-specific) and the commit will only include R2.

---

## Verification checklist (run after R2 install)

Run all five — each is a single command. The first four verify each rule landed; the fifth confirms cleanup.

```bash
# 1. p3-backlog.md exists with header + 9 entries
cat docs/memory/p3-backlog.md | head -30 && \
  echo "---" && \
  grep -c "^### " docs/memory/p3-backlog.md
# Expected: header is shown, "Open count: 9" visible. Final number printed
# should be ≥9 (the per-row "###" headers; future-ideas section has none).

# 2. R1.a landed in review-cycle.md
grep -A2 "Severity-based fix-cycle scope" docs/memory/wiki/concepts/review-cycle.md
# Expected: section header + the leading blockquote line containing
# "Round-2 fix-task briefs MUST contain ONLY blocking severity items".

# 3. R1.b + R3 landed in AGENTS.md
grep -B1 -A3 "p3-backlog" AGENTS.md
# Expected: TWO matches —
#   (a) bullet #5 under Workflow Sequencing referencing docs/memory/p3-backlog.md,
#   (b) (none in §7 — R3 doesn't reference p3-backlog; verify R3 separately:)
grep -B1 -A2 "Re-read before .apply_diff" AGENTS.md
# Expected: bullet #6 under §7 Wiki Sync Protocol describing the re-read rule.

# 4. R2 landed in .roo/ AND survived the system hook
cat .roo/skill-root-cause-analysis.md | grep -A5 "Live Re-Invocation First"
# Expected: section header + leading blockquote line about "default first move".
# If empty: either install command failed (check terminal output above)
# or the §8 hook reverted the file (check `git log -1 .roo/` —
# should show the R2 commit).

# 5. activeContext.md no longer duplicates the P3 lists
grep -c "P3-1" docs/memory/tasks/default/activeContext.md
grep -c "p3-backlog.md" docs/memory/tasks/default/activeContext.md
# Expected: first count is 0 (no per-P3 detail lines anymore),
# second count is ≥1 (the new pointer line is present).
```

If all five pass, the install is complete. If #4 fails after the install command appeared to succeed, run `git log -1 -- .roo/skill-root-cause-analysis.md` to see whether the R2 commit landed; if yes, the file is intact and the system hook didn't fire (success). If no commit appears, the heredoc may have failed silently — re-run the install command and watch the `INSERTED N chars` output line.

---

## Wiki Impact

- **New entities:** None.
- **Updated entities:** None directly. (The new [`docs/memory/p3-backlog.md`](../memory/p3-backlog.md) is a task-tracking file, not a wiki entity.)
- **New concepts:** None new — R1 extends [`review-cycle.md`](../memory/wiki/concepts/review-cycle.md) (existing concept), R2 extends [`skill-root-cause-analysis.md`](../../.roo/skill-root-cause-analysis.md) (existing skill), R3 extends [`AGENTS.md`](../../AGENTS.md) §7 (existing protocol).
- **Updated concepts:** [`review-cycle.md`](../memory/wiki/concepts/review-cycle.md) gained the "Severity-based fix-cycle scope" section.
