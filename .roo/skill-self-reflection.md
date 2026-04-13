# Skill: Self-Reflection

## Purpose
Enable every agent to evaluate its own performance at the end of each task, identify mistakes, and log lessons learned for continuous improvement.

## When to Use
MANDATORY — at the end of every task, every agent, every session. No exceptions.
Even a 2-minute answer gets a self-reflection.

## The REAR Framework

### R — Review
- What was the task? What was the expected outcome?
- What approach did I take? Was it the most efficient?
- Did I follow all applicable rules and skills?

### E — Evaluate
Rate each dimension:
- Accuracy: Were my outputs correct and complete?
- Efficiency: Did I use the optimal approach and tools?
- Protocol: Did I follow all rules (shared.md, agent-specific rules)?
- Quality: Was my output clear, actionable, and well-structured?

### A — Adapt
- What would I do differently next time?
- What new pattern or insight did I discover?
- Is there a gap in my skills or rules that should be filled?

### R — Report
Write the self-reflection and append it to the session output.

## Self-Reflection Template

Append this block at the end of every task completion:

---
Self-Reflection:
- Accuracy: [pass/warning/fail] — [brief note]
- Efficiency: [pass/warning/fail] — [brief note]
- Protocol: [pass/warning/fail] — [brief note]
- Quality: [pass/warning/fail] — [brief note]
- Lesson learned: [one sentence, or "None" if nothing new]
- Improvement needed: [one sentence, or "None"]
---

## Compact Format (for simple tasks)

For quick tasks (under 5 minutes), use the one-liner format:

Self-Reflection: pass Accuracy | pass Efficiency | pass Protocol | No issues found

## Error Severity Guide

| Severity | When to Use | Action |
|----------|-------------|--------|
| CRITICAL | Wrong output that could break production | Fix immediately, log lesson |
| HIGH | Missed important requirement or edge case | Log lesson, update relevant skill |
| MEDIUM | Suboptimal approach, could have been faster | Note for next time |
| LOW | Minor formatting or communication issue | Note only |

## What to Do with Findings

| Finding | Action |
|---------|--------|
| Factual error | Correct it before completing the task |
| Missing edge case | Add it to the relevant skill checklist (via self-learn proposal) |
| Repeated mistake | Propose a rule addition (via skill-self-learn.md) |
| New pattern | Log it in memory (docs/memory/) for future sessions |
| No issues | Log "No issues found" — still write the reflection |
