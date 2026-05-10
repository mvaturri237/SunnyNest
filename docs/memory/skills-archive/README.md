# Skills Archive

Skill files that were authored or imported but are not currently loaded by any agent mode in [`.roomodes`](../../../.roomodes). They live here (instead of being deleted) so we can:

1. Mine them for ideas later when extending or rewriting our own skills
2. Reference them from a wiki concept page if a pattern proves useful
3. Re-promote a skill to `.roo/` if a future task makes it relevant

> **Status:** None of these are loaded by any agent. Moving a skill back to `.roo/` requires both the file move AND a `.roomodes` edit to wire it into a mode's `customInstructions`.

## Provenance

These were imported during the IDEX adoption work (commits `7cef222` → `70e9bfe`, May 2026). The 5 SunnyNest-relevant skills we kept and wired into modes are still in `.roo/`. The 7 below are universal/IDEX-platform-specific patterns kept here for reference.

| File | Lines | Notes |
|------|-------|-------|
| [`skill-agent-optimizer.md`](skill-agent-optimizer.md) | 632 | IDEX-specific: optimizes IDEX/ProDex agents themselves. The optimization framework concepts could inspire a future SunnyNest agent-tuning task. |
| [`skill-context-engineering.md`](skill-context-engineering.md) | 155 | Universal token-budget framework. References `.clinerules` (IDEX file). Useful as occasional reference when tuning `.roomodes` or `AGENTS.md` size. |
| [`skill-evidence-based-reasoning.md`](skill-evidence-based-reasoning.md) | 71 | Citation format for code claims. Requires IDEX `repos/<service>/path:line` structure we don't have. SunnyNest equivalent: see [`.roo/skill-code-review.md`](../../../.roo/skill-code-review.md) strict format. |
| [`skill-memory-validator.md`](skill-memory-validator.md) | 485 | Validates IDEX memory bank structure. SunnyNest equivalent: [`.roo/skill-wiki-lint.md`](../../../.roo/skill-wiki-lint.md). The validation-level taxonomy (existence, freshness, quality, compliance) is worth borrowing if we extend our wiki-lint. |
| [`skill-multi-agent-patterns.md`](skill-multi-agent-patterns.md) | ~150 | When-to-delegate decision framework. The "context partition not organizational role" insight is universal and could inform future routing decisions. |
| [`skill-prompt-engineering.md`](skill-prompt-engineering.md) | 212 | Patterns for designing `roleDefinition` and `customInstructions` in `.roomodes`. **High value when authoring or rewriting agent system prompts.** Read this before significant `.roomodes` rewrites. |
| [`skill-tool-design.md`](skill-tool-design.md) | 91 | Designing TypeScript custom tools. SunnyNest explicitly rejected the IDEX custom-tool pattern in the original adoption analysis; kept here for completeness. |

## Restore procedure (if you ever want to wire one back)

```bash
# Move the file back
git mv docs/memory/skills-archive/skill-X.md .roo/skill-X.md

# Edit .roomodes to add the skill reference under the appropriate mode's
# customInstructions (Tier 1 if always-load, Tier 2 with explicit trigger).

# Commit atomically — .roo/ writes survive only when committed.
git add .roo/skill-X.md .roomodes && \
  git commit -m "feat(modes): wire skill-X.md back into <mode> mode"
```

## Related

- [`docs/memory/wiki/concepts/agent-mode-tiering.md`](../wiki/concepts/agent-mode-tiering.md) — Tier 1/Tier 2 loading pattern
- [`AGENTS.md`](../../../AGENTS.md) — protocols, including §8 on `.roo/` system guard
