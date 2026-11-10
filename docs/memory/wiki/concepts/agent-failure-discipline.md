# Agent Failure Discipline

> When something fails, **stop after 2 attempts** and escalate. Never assume — verify the precondition, then act. These rules prevent trigger-happy execution, retry storms, file corruption, and the common "I think this worked" anti-pattern. Adopted from the IDEX_new project's `skill-zero-trust-execution.md`.

**Applies to:** Every agent mode in [`.roomodes`](../../../../.roomodes) — Orchestrator, Code, Code Reviewer, Architect, UX Designer, Debug
**Learned:** 2026-05-08
**Source:** [`docs/temp/idex-adoption-phase1.md`](../../../temp/idex-adoption-phase1.md) §1 (the canonical content destined for [`.roo/skill-zero-trust-execution.md`](../../../../.roo/skill-zero-trust-execution.md))

## Pattern

Two complementary rules, applied at every step of every task:

### 1. The 2-Failure Escalation Rule (HARD)

After **2 consecutive failures on the same operation**, STOP. Do **not** retry a 3rd time. Instead:

1. Report what failed (with the exact error message).
2. Hypothesize 2-3 plausible root causes.
3. Either ask the user how to proceed OR escalate to a more appropriate mode.

**What counts as a failure:**
- Tool error (`apply_diff` rejected, `write_to_file` denied, `execute_command` exit code ≠ 0)
- Blocked call (system guard, permission denied)
- Unexpected output (the result doesn't match the expected schema/format)
- Repetition limit warning from the platform

**What does NOT count as a failure:**
- A successful operation that revealed unexpected information (that's a finding, not a failure — keep going).
- A planned multi-step operation where step 1 was a probe (the probe's "failure" is data).

### 2. The 7 "Never Assume" Principles

Self-distrust is a feature, not a bug. The agent must verify, not assume:

1. **Never assume file contents** — read the file before editing it. Don't trust the AGENT's memory of what's in a file from earlier in the session; the user may have edited it.
2. **Never assume tool behavior** — verify the output after every tool call. A tool returning "success" is not the same as the operation having the intended effect.
3. **Never assume user intent** — if the request is ambiguous, ask before acting. Don't pattern-match to what a similar request usually means.
4. **Never assume a previous step succeeded** — check the result explicitly. The "DONE" message from a script is not proof; `ls` / `wc` / `cat` is.
5. **Never assume "small" changes are safe** — a 1-line config edit can break the entire app. Verify the impact before executing.
6. **Never assume your first instinct is correct** — think before acting. The first plausible solution often misses an edge case.
7. **Never assume another agent's output is correct** — validate before using it. The Architect's plan, the Code Reviewer's verdict, the user's snippet — all must pass your own technical judgment before you act on them.

## Rules

1. **The 2-failure rule is HARD** — agents must not "try one more time, just in case." That is the failure mode the rule exists to prevent.
2. **Verify-before-act applies recursively** — even a verification step is a step that could fail; if it fails twice, escalate the verification, don't switch to verifying-the-verification.
3. **"It's an emergency" is NOT an exception** — urgency is the signal to escalate FASTER, not to bypass the rule.
4. **All agents include this in their self-reflection** — the REAR template's "Evaluate" step asks "Did I follow the 2-failure rule? Did I verify each precondition?"
5. **Cross-agent application** — Code Reviewer applies these rules when reviewing Code's output (don't assume the diff actually applied — `cat` the file). Architect applies these when consuming domain expert input. Orchestrator applies these when interpreting subtask completion messages.

## Examples

### ✅ Correct — 2-failure rule respected (2026-05-08, Code mode)

Code mode tried `write_to_file` to [`.roo/skill-zero-trust-execution.md`](../../../../.roo/skill-zero-trust-execution.md). System guard denied. Code mode **did not retry the 4 other `.roo/` writes** (would have failed identically), instead reported the blocker and pivoted to applying [`.roomodes`](../../../../.roomodes) (which succeeded). The Orchestrator then routed the `.roo/` work to the user with a copy-paste shell script. → [log entry](../log.md#2026-05-08-idex-mode-improvements--phase-1)

### ❌ Anti-pattern — assumed-previous-step-succeeded (2026-05-08, Orchestrator)

The Orchestrator received "Phase 1b done — all 7 ops succeeded" output from a shell script that *had* succeeded at write time. The Orchestrator routed straight to Code Reviewer without re-verifying the files still existed. By the time the reviewer ran (~10 min later), the `.roo/` files had been silently reverted by a Roo Code lifecycle hook. The reviewer issued 7 P1s for "files don't exist." Lesson: between any subtask boundary, re-verify disk state before acting on prior claims. The reviewer's own self-reflection captured the "Disk-First Review Discipline" pattern from this incident — codified here.

### ❌ Anti-pattern — retry storm (historical, from IDEX_new lessons learned)

5 accidental file deletions and 2 file corruptions traced to `roo_file_editor` repeatedly retried after the first denial in 2026-03. The 2-failure rule was added to prevent recurrence.

## Related

- [Agent Mode Tiering](agent-mode-tiering.md) — sister concept; this discipline is the canonical Tier 1 universal skill that every mode loads
- [Review Cycle](review-cycle.md) — Code → Review → Fix is itself an instance of "never assume your work is correct" (always pair with a reviewer)
- [Silent Failure Pattern](silent-failure-pattern.md) — failures that don't surface as obvious errors are the hardest case for the 2-failure rule (you can fail many times without realising)
- [`.roo/skill-zero-trust-execution.md`](../../../../.roo/skill-zero-trust-execution.md) — the full skill file (⚠️ pending install — see [AGENTS.md Pending Manual Install appendix](../../../../AGENTS.md))
- [`docs/memory/shared/lessonsLearned.md`](../../shared/lessonsLearned.md) — chronological lessons that reinforce these principles
