# Skill: Zero-Trust Execution

> **Tier 1 — applies to ALL modes.** Default posture is distrust: distrust your own assumptions, distrust prior steps, distrust tool output, distrust the user's stated intent until verified.

## Purpose
Prevent trigger-happy mistakes caused by acting on assumptions instead of evidence. Most production-impact bugs in SunnyNest came from skipping a verification step (see [Lessons Learned](../docs/memory/shared/lessonsLearned.md:134) — Jinja2 entities, CSS cache, env vars).

## When to Use
**Every non-trivial task.** Especially when:
- Editing shared config (`.roomodes`, `config.yaml`, templates, CSS)
- Acting on output from another agent
- Repeating a step that just failed
- The user says "just do it" or "should be easy"

---

## The 6-Step Workflow

### 1. THINK
> What is the user actually asking for? What is the success criterion?

Restate the goal in your own words. If you can't, ask via `ask_followup_question`.

### 2. PLAN
> What are the discrete steps? What files/tools does each touch?

Write the plan as an ordered list. Identify the **smallest reversible step** to start with.

### 3. CONSULT
> What do I need to read FIRST before acting?

- Relevant wiki entity pages ([`docs/memory/wiki/index.md`](../docs/memory/wiki/index.md:1))
- Active context ([`activeContext.md`](../docs/memory/tasks/default/activeContext.md:1))
- The actual file I'm about to edit (never assume contents)
- Sibling/parent files that might be coupled (e.g., template + CSS + cache version)

### 4. REPLAN
> Did Step 3 invalidate any of Step 2?

Often yes. Re-order, drop, or add steps based on what you learned.

### 5. VALIDATE
> Will this plan actually work? What could go wrong?

Walk through each step mentally. For each: "What if this fails? What if the file isn't what I expect? What downstream files break?"

### 6. EXECUTE
> One step at a time, smallest first, verify after each.

After each step, **explicitly check** the result before moving to the next. No batching destructive operations.

---

## The 2-Failure Escalation Rule (HARD)

> **After 2 consecutive failures on the same operation, STOP. Do NOT retry a 3rd time.**

### What counts as a failure
- Tool returned an error (non-zero exit, exception, "file not found")
- Tool was blocked (permission denied, file restriction, sandbox error)
- Output was unexpected (wrong content, empty when content expected, malformed)
- The same fix was attempted twice and the symptom persists

### What to do instead of retry #3
1. **STOP execution immediately.**
2. **Report** to the user: what was attempted, what failed, what the output was.
3. **Hypothesize** in writing: 2-3 possible root causes.
4. **Ask** the user how to proceed (or for the missing info), or escalate to a more appropriate mode.

> Retrying a 3rd time without changing approach is the #1 source of wasted tokens and corrupted state. The third retry almost never works — and often makes things worse (e.g., partial writes, half-applied diffs).

---

## The 7 "Never Assume" Principles

| # | Rule | Counter-action |
|---|------|----------------|
| 1 | Never assume **file contents** | Read the file (or relevant slice) before editing |
| 2 | Never assume **tool behavior** | Verify the output of each tool call before acting on it |
| 3 | Never assume **user intent** | Restate the goal; ask if ambiguous |
| 4 | Never assume **the previous step succeeded** | Check exit codes, output text, or re-read the file |
| 5 | Never assume **"small" changes are safe** | A 1-line CSS change still requires cache version bump and curl-verification |
| 6 | Never assume **your first instinct is correct** | Generate ≥2 options; pick with explicit reasoning |
| 7 | Never assume **another agent's output is correct** | Spot-check claims against the actual files (Code's "Wiki Entities Affected" list, Reviewer's severity calls) |

---

## SunnyNest-Specific Triggers (real past failures)

These are real bugs caused by skipping zero-trust steps. Treat them as canaries — if you're about to do anything similar, slow down.

### CSS-Not-Bumped Bug
*[Source: [`lessonsLearned.md` "CSS Cache Versioning"](../docs/memory/shared/lessonsLearned.md:144)]*

500 lines of new CSS were added to `admin.css`, but `?v=5` in `admin/base.html` was not bumped. The browser served stale CSS, the entire admin page rendered unstyled, and the Code Reviewer **approved** the change without loading the page.

**Zero-trust check:** Whenever you touch `web/static/css/*.css`, you MUST also bump the matching `?v=N` in [`web/templates/base.html`](../web/templates/base.html:1) or [`web/templates/admin/base.html`](../web/templates/admin/base.html:1), then `curl` the page to confirm.

### Jinja2-Entity Bug
*[Source: [`lessonsLearned.md` "Jinja2 Auto-Escaping"](../docs/memory/shared/lessonsLearned.md:134)]*

`{{ '&#x2713;' }}` rendered as literal text `&#x2713;` because Jinja2 escaped the `&` to `&amp;`. The whole API Usage page showed broken-looking entity codes instead of checkmarks.

**Zero-trust check:** Never put `&#x...` HTML entities inside `{{ }}` expressions. Use the actual Unicode character (`✓`, `✗`, `📊`). After any template change, `grep` the rendered HTML for `&#x` to confirm none leaked through.

### Silent Env-Var Failure
*[Source: [`lessonsLearned.md` "Silent Failure Pattern"](../docs/memory/shared/lessonsLearned.md:38)]*

`RAPIDAPI_KEY` was unset after a server restart. The scraper returned `[]` every run with no error. Nobody noticed for 5 days.

**Zero-trust check:** When testing anything that depends on env vars or external credentials, FIRST verify the credential is loaded (System Health panel, log line, manual `printenv`). Don't assume "it ran without error" means "it worked."

---

## Integration with Other Skills

- **Pairs with** [`skill-self-reflection.md`](skill-self-reflection.md:1) — REAR's "Evaluate" step uses zero-trust principles to grade your own work.
- **Pairs with** [`skill-code-review.md`](skill-code-review.md:1) — Reviewer applies "never assume another agent's output is correct" to Code's submissions.
- **Pairs with** [`skill-root-cause-analysis.md`](skill-root-cause-analysis.md:1) — Debug mode uses zero-trust before forming hypotheses.

## Quick Checklist (apply to every task)

- [ ] Stated the goal back in my own words
- [ ] Read the relevant wiki + actual files before editing
- [ ] Smallest reversible step planned first
- [ ] Verified each step's output before moving on
- [ ] Have not retried any operation more than 2 times
- [ ] No assumption from the list of 7 was relied upon without evidence
