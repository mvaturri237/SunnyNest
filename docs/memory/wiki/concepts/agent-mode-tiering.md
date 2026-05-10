# Agent Mode Tiering

> Skills referenced by an agent mode are split into **Tier 1 (load every task)** and **Tier 2 (load on demand)**, instead of a flat "always load everything" list. Adopted from the IDEX_new project during the 2026-05-08 IDEX adoption work.

**Applies to:** All agent modes defined in [`.roomodes`](../../../../.roomodes), all skills in [`.roo/`](../../../../.roo/)
**Learned:** 2026-05-08
**Source:** [`docs/temp/idex-adoption-phase1.md`](../../../temp/idex-adoption-phase1.md) (Architect-authored Phase 1 deliverables)

## Pattern

A flat skill list ("load and follow these for relevant tasks: A, B, C, D, E…") forces the agent to consider every skill on every task. This wastes context and dilutes focus. The Tier 1 / Tier 2 split makes the load explicit:

```
SKILLS — Tier 1 (load every task start):
- skill-X.md   (universal discipline, loaded unconditionally)

SKILLS — Tier 2 (load when relevant):
- skill-Y.md   (load when … specific trigger condition)
- skill-Z.md   (load when … specific trigger condition)
```

The agent reads the Tier 1 list at every task start. Tier 2 entries are read only when the trigger condition is met (e.g., "load `skill-log-analysis-patterns.md` whenever you need to read logs").

## Rules

1. **Tier 1 is for universal discipline only** — skills that apply to every task in the mode (e.g., zero-trust execution, self-reflection). Adding too much to Tier 1 defeats the purpose.
2. **Tier 2 entries MUST include the trigger condition** in the bullet text — `skill-X.md — load when …`. Without a trigger, the agent has to guess and will either always load it (back to flat) or never load it.
3. **Each skill should be self-contained** — Tier 2 skills should not depend on each other in ways that force the agent to load multiple at once.
4. **The mode's customInstructions block lists both tiers explicitly** under labelled headings, not as a flat bullet list.
5. **Modes that have NO Tier 1 skills** (e.g., a thin built-in mode) can omit the Tier 1 heading; they MUST still have at least one Tier 2 entry or the skill list is empty by definition.

## Examples

### Debug mode (added 2026-05-08, see [`.roomodes`](../../../../.roomodes:209))

```
SKILLS — Tier 1 (load every task):
- .roo/skill-zero-trust-execution.md — distrust-by-default workflow, 2-failure
  escalation rule, 7 "never assume" principles

SKILLS — Tier 2 (load when relevant):
- .roo/skill-root-cause-analysis.md — load when investigating any bug;
  provides 5 Whys, hypothesis-evidence pattern, differential diagnosis table
- .roo/skill-log-analysis-patterns.md — load whenever you need to read logs;
  provides SunnyNest log file locations, triage pattern, error-signature table
```

### Anti-pattern (the old flat style — avoid)

```
SKILLS (load and follow these for relevant tasks):
- .roo/skill-A.md
- .roo/skill-B.md
- .roo/skill-C.md
- .roo/skill-D.md
- .roo/skill-E.md
```

The agent has no signal about which to read first or when to skip one. Result: either all five are loaded every time (context bloat) or the agent guesses inconsistently.

## Migration status

| Mode | Status | Tier 1 count | Tier 2 count | Migrated |
|------|--------|-------------|-------------|----------|
| `debug` | ✅ Migrated | 1 | 2 | 2026-05-08 (commit `7cef222`) |
| `code` | ✅ Migrated | 1 | 4 | 2026-05-09 (this commit) |
| `architect` | ✅ Migrated | 1 | 6 | 2026-05-09 (this commit) |
| `dev-reviewer` | ✅ Migrated | 2 | 6 | 2026-05-09 (this commit) |
| `ux-designer` | ✅ Migrated | 2 | 8 | 2026-05-09 (this commit) |
| `orchestrator` | ⏸ Deferred | 0 | 0 | — (3 flat skills; smaller win, defer) |

**Status update (2026-05-09):** 5 of 6 modes migrated. The `orchestrator` mode is intentionally deferred — its 3 skills (`memory-manager`, `self-reflection`, `wiki-lint`) are all genuinely Tier 1 (loaded every task), so a flat list is correct for it. A "Tier 1: all 3" migration would be cosmetic only.

### Pattern recap (for future migrations)

When a 6th mode is added or an existing mode gains skills:

- **Tier 1** is for skills that are loaded *unconditionally* every task (universal discipline + role-defining methodology). Cap at 2-3 entries.
- **Tier 2** entries MUST include the trigger condition in the bullet text (e.g., "load when touching `src/scrapers/`"). Without a trigger the agent loads it always = back to flat.
- **Cross-cutting skills** (`self-reflection`, `self-learn`, `memory-manager`) appear in many modes; they're Tier 1 if mandatory, Tier 2 if conditional.

## Related

- [Review Cycle](review-cycle.md) — every mode change still flows through Code → Review
- [`.roomodes`](../../../../.roomodes) — where all mode definitions live
- [`AGENTS.md`](../../../../AGENTS.md) — Active Roles table that documents the current Tier 1 / Tier 2 sets per mode
- [Agent Failure Discipline](agent-failure-discipline.md) — sister concept; the Tier 1 universal skill ([`skill-zero-trust-execution`](../../../../.roo/skill-zero-trust-execution.md)) embodies the failure-discipline rules
