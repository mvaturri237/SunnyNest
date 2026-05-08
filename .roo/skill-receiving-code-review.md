# Skill: Receiving a Code Review

> **Tier 2 — loaded by Code mode when responding to feedback from `dev-reviewer`.** Don't dive into individual comments before reading the whole review. Don't accept every suggestion uncritically.

## Purpose
Code mode often gets a list of issues from the Code Reviewer. The natural urge is to start fixing the first comment immediately. That leads to:
- Conflicting fixes (fixing comment 1 invalidates comment 5)
- Accepting a wrong suggestion that would introduce a new bug
- Missing the bigger pattern across multiple comments

This skill enforces a structured response cycle.

---

## Hard Rule: Read EVERYTHING Before Acting

> **Read the entire review end-to-end before responding to any individual comment.**

Why: a P3 style comment at the bottom may be the same root issue as a P1 correctness comment at the top. A "minor" suggestion may conflict with another reviewer recommendation. You can only see the pattern by reading all of it first.

---

## Categorize Each Piece of Feedback

| Icon | Category | Examples | Response Priority |
|------|----------|----------|-------------------|
| 🔴 | **Correctness** | Logic bug, security flaw, data loss risk, broken build, race condition | **MUST fix** before re-review (P1 territory) |
| 🟠 | **Design** | Wrong abstraction, leaky module boundary, scalability concern | **SHOULD fix** before re-review (P2 territory) |
| 🟡 | **Maintainability** | Misleading name, missing docstring, duplicated logic | **SHOULD fix** if cheap; defer to follow-up if not |
| 🟢 | **Style** | Formatting, comment wording, import ordering | **MAY fix**; reviewer's call |
| 🔵 | **Question** | "Why this approach?" | **MUST respond** (with explanation, not necessarily code change) |

Process all 🔴 first, then 🟠, then 🟡, then 🟢. **Never** start with 🟢 — you'll waste time you may need on 🔴.

---

## Verification Checklist (per accepted suggestion)

Before applying ANY suggestion, ask all 5 questions. If any answer is "no" or "not sure," push back instead of applying.

1. **Does it actually fix the issue?** — Re-read the issue description, then trace the suggested fix. Does it remove the root cause or just paper over the symptom?
2. **Does it introduce new problems?** — New edge cases? New dependencies? New performance regression?
3. **Is it consistent with the rest of the codebase?** — Does it follow existing patterns? Or is it a one-off that increases maintenance burden?
4. **Is it aligned with architectural decisions?** — Check [`docs/memory/wiki/concepts/`](../docs/memory/wiki/concepts/) and relevant entity pages. Does the suggestion contradict an existing pattern (e.g., adapter pattern, app isolation)?
5. **Have I verified it works?** — Tested or traced through? "Looks right" is not "works right."

---

## When to Push Back

You **should** push back when:

- The suggestion is technically incorrect (would introduce a bug)
- The suggestion contradicts a documented architectural decision
- The suggestion is style preference disguised as correctness (e.g., "use `Optional[X]` instead of `X | None`" when the project uses `|` syntax everywhere)
- The reviewer misread the code (it already does what they're asking)

How to push back:

1. Quote the exact code line(s) that demonstrate why the suggestion is wrong.
2. Cite the file and line: `[path/to/file.py:42]`
3. Reference the contradicting pattern (wiki concept, sibling file, lessons-learned entry).
4. Propose an alternative if applicable, OR explain why the current code is already correct.
5. Stay technical and brief — no defensiveness.

---

## Response Format Template

Use this format when posting your response back to `dev-reviewer` (via the Orchestrator):

```
## Response to Code Review

### Issues Fixed (🔴 / 🟠)
- [path/to/file.py:line] <issue title> — Fixed by <one-line summary of fix>. Diff: <commit/branch ref>.
- ...

### Issues Deferred (🟡 / 🟢)
- [path/to/file.py:line] <issue title> — Deferring as <reason: out-of-scope, follow-up ticket #N, etc.>.

### Issues Disputed (push back)
- [path/to/file.py:line] <issue title> — I disagree because <evidence>. Cited: [other/file.py:line]. Proposing instead: <alternative or "leave as-is">.

### Questions Answered (🔵)
- "<reviewer's question>" — <your answer, 1-2 sentences>.

### Re-review Requested
- All 🔴 issues addressed. Ready for re-review.
```

End the response with a clear ASK: "Re-review please" OR "These deferrals OK?" — never leave it ambiguous whether you expect another round.

---

## Integration With Other Skills

- **Pairs with** [`skill-zero-trust-execution.md`](skill-zero-trust-execution.md:1) — Principle #7: never assume another agent's output is correct (applies to reviewers too).
- **Triggered by** [`skill-code-review.md`](skill-code-review.md:1) — that skill produces the review you'll receive.
- **Honors** [`AGENTS.md` review-cycle rule](../AGENTS.md:1) — only the Orchestrator's `dev-reviewer` round-trip can mark a code task complete.

## Quick Checklist

- [ ] Read the entire review before fixing anything
- [ ] Categorized each comment (🔴/🟠/🟡/🟢/🔵)
- [ ] Processed 🔴 → 🟠 → 🟡 → 🟢 in that order
- [ ] Ran 5-question verification on each accepted suggestion
- [ ] Pushed back on incorrect suggestions with cited evidence
- [ ] Posted response in the standard template
- [ ] Explicit re-review request at the end
