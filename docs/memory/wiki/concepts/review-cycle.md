# Review Cycle

> All code changes must follow the mandatory Code → Review → Fix cycle. Never use `switch_mode` to Code for code changes — it bypasses the Orchestrator and skips review.

**Applies to:** All code changes across all entities  
**Learned:** 2026-03-28  
**Source:** `docs/memory/shared/lessonsLearned.md` — switch_mode Bypass

## Pattern

Every code change in SunnyNest must go through a mandatory review cycle:

```
💻 Code  ──►  🔍 Code Reviewer  ──►  ✅ Complete
                    │
                    ▼ (P1/P2 issues found)
               💻 Code (fix)  ──►  🔍 Code Reviewer (re-review)
```

This cycle is enforced by the Orchestrator and cannot be skipped. The critical insight is that `switch_mode` to Code mode bypasses this cycle because Code mode can call `attempt_completion` directly — returning to the user without the Orchestrator ever getting a chance to route to Code Reviewer.

## Rules

1. **Always use `new_task(mode: "code", ...)` for any code modifications** — ensures the Orchestrator receives the result and can route to Code Reviewer
2. **`switch_mode` to Code is only acceptable for read-only operations** (e.g., running a database query, checking a file)
3. **Code mode must include "Wiki Entities Affected" in completion messages** — helps Orchestrator perform wiki sync
4. **If Code mode was entered via `switch_mode` and modified files:** Must explicitly recommend switching to `dev-reviewer` mode before completing
5. **Code Reviewer must verify:**
   - CSS version bumped if CSS files were modified (P1 if not)
   - No `&#x` entities inside `{{ }}` Jinja2 expressions (P1 if found)
   - Config.yaml updated when code constants change (P1 if mismatched)
   - Runtime verification for UI changes (curl the page, check HTML output)

## Severity-based fix-cycle scope

> **Round-2 fix-task briefs MUST contain ONLY blocking severity items (P0 / P1 / P2). P3 (non-blocking) and unranked "recommended" items MUST be appended to [`p3-backlog.md`](../../p3-backlog.md) by the Orchestrator with attribution to the source task. The user triggers P3 cleanup on-demand by asking *"fix all open P3s"* or *"fix the [feature] P3s"*.**

**Why:** Bundling a 6-line P2 fix with two "SHOULD-FIX" P3s in a round-2 task brief means Code mode writes ~140 lines of bonus work that the user may interrupt mid-flight ("skip the P3s") — forcing a wasteful revert. Real cost on 2026-05-08 dedup task: ~$1.55 + ~5 min wall-clock spent reverting work the user never wanted bundled. Keeping P3s out of round-2 briefs forces an explicit "yes/no, when?" decision per P3, paid in cheap clicks instead of expensive reverts.

**Mechanics:**
1. After every Code Review cycle, the Orchestrator parses the reviewer's report.
2. P0 / P1 / P2 items → bundle into the round-2 fix brief as today.
3. **Every P3 (and every "recommended" / "nice-to-have" without a severity label)** → append a row to [`p3-backlog.md`](../../p3-backlog.md) using the schema at the bottom of that file. Attribute via the `Source task` field; copy the reviewer's suggested fix verbatim.
4. The Orchestrator's post-cycle `attempt_completion` should mention "N P3s queued in [`p3-backlog.md`](../../p3-backlog.md)" so the user knows they exist without having to scan.
5. The user triggers a sweep with *"fix all open P3s"* or *"fix the dedup P3s"* — Orchestrator spawns a Code task whose brief is the matching subset of open rows.

**Examples:**

| Reviewer report | Round-2 brief contains | `p3-backlog.md` gets |
|---|---|---|
| 1 P2 + 5 P3s (2 tagged "SHOULD FIX") | Just the P2 | All 5 P3s appended |
| 0 P1 + 0 P2 + 5 P3s (the WhatsApp 2026-05-08 case) | **No round-2 needed — task complete** | All 5 P3s appended |
| 2 P1 + 3 P2 + 1 P3 | All 5 blocking items | The 1 P3 appended |
| 1 P2 + 1 P3 tagged `[hardens-against-this-bug-class]` | Just the P2 | The P3 appended **with a note** flagging the hardens-tag, so the next P3 sweep prioritises it |

**One narrow exception (the `[hardens-against-this-bug-class]` tag):** Reviewers MAY tag a P3 with `[hardens-against-this-bug-class]` when it directly hardens against the bug just fixed. Such P3s are still queued in `p3-backlog.md` (per the rule above), but the Orchestrator should explicitly list them in the post-cycle `attempt_completion` and ASK the user *"include now or queue?"* — not auto-bundle. This preserves the user-control invariant while making bug-class hardening visible.

## Examples

- **Bypass incident (2026-03-28):** A pet_friendly extraction feature was implemented via `switch_mode` to Code — the code was written and completed without review
- **Fix:** Updated `.roomodes` and `AGENTS.md` with safeguards; Code mode's custom instructions now include a `MANDATORY REVIEW RULE`
- **P3-bundling incident (2026-05-08):** Round-2 dedup fix brief bundled 2 SHOULD-FIX P3s with the P2; user interrupted; Code mode reverted ~140 lines. Codified the P3-backlog rule above to prevent recurrence.

## Related

- [`p3-backlog.md`](../../p3-backlog.md) — the queue itself
- All entity pages — the review cycle applies to all code changes
- [CSS Cache Versioning](css-cache-versioning.md) — reviewer check item
- [Jinja2 Safety](jinja2-safety.md) — reviewer check item
