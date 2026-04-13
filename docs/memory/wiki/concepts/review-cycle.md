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

## Examples

- **Bypass incident (2026-03-28):** A pet_friendly extraction feature was implemented via `switch_mode` to Code — the code was written and completed without review
- **Fix:** Updated `.roomodes` and `AGENTS.md` with safeguards; Code mode's custom instructions now include a `MANDATORY REVIEW RULE`

## Related

- All entity pages — the review cycle applies to all code changes
- [CSS Cache Versioning](css-cache-versioning.md) — reviewer check item
- [Jinja2 Safety](jinja2-safety.md) — reviewer check item
