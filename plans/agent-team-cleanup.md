# Agent Team Cleanup Plan

**Date:** 2026-05-08 (drafted)
**Execution date:** 2026-05-09 (planned — pick up tomorrow)
**Status:** PLAN — awaiting kick-off
**Author:** 🪃 Orchestrator (post-IDEX-adoption efficiency audit)
**Estimated effort:** ~30-45 minutes (one focused session)
**Prerequisite:** Read `## Context` section below to refresh memory of what we discovered

---

## Context (what brought us here)

Yesterday (2026-05-08) we adopted 8 mode/skill improvements from the IDEX_new project. Two commits landed (`7cef222` install, `2de426b` post-mortem, `853522d` cleanup). After all that work, an efficiency audit found 4 measurable gaps the IDEX adoption itself created or surfaced. This plan closes them.

**Key data points from yesterday's audit:**

| Metric | Value | Target |
|--------|-------|--------|
| Total skill files in `.roo/` | 28 | — |
| Skill files referenced by any mode | 19 | — |
| **Orphan skill files (on disk, never loaded)** | **9** | ≤2 |
| Modes using Tier 1 / Tier 2 loading | 1 of 6 (debug only) | All 6 |
| Routing-table mode coverage | 3 of 5 (code/debug/architect) | 5 of 5 |
| `activeContext.md` size | 45 lines | ≤30 lines |
| `docs/temp/` `.bak` leftovers | 3 files | 0 |

**Core insight:** We installed two new skills yesterday (`skill-receiving-code-review.md`, `skill-architect-design-review.md`) that **no mode currently loads**. We did the work but didn't wire them up. That's the highest-leverage fix.

---

## 🎯 Goals

1. Wire the 2 newly-installed orphan skills into the modes that should use them
2. Migrate `dev-reviewer` and `ux-designer` from flat skill lists to Tier 1 / Tier 2
3. Decide what to do with the 7 remaining orphan skills (most are IDEX legacy imports)
4. Add `dev-reviewer` and `ux-designer` slugs to the Orchestrator Routing Rules table
5. Trim `activeContext.md` back to its target ≤30 lines
6. Clean up `docs/temp/*.bak` and the 0-byte `apply-phase1.sh`

---

## ⚠️ Non-Goals (explicit out-of-scope)

- Migrating `code`, `architect`, `orchestrator` modes to Tier 1 / Tier 2 — they have fewer skills (3, 4, 3 respectively), the win is smaller, and the changes are more disruptive. Defer to a future task.
- Building any new skills. This is purely wiring + cleanup.
- Touching the existing wiki entity pages or [`design-bible.md`](../docs/design/design-bible.md) — no domain content changes.
- Changing the Mandatory Code → Review cycle or any §1-§8 protocol in [`AGENTS.md`](../AGENTS.md).

---

## 📋 Phases

### Phase 1 — Wire the 2 newly-installed orphan skills (HIGH IMPACT, 5 min)

**Why first:** These skills exist on disk (committed in `7cef222`) but are unreachable. They're 277 total lines of authored content sitting orphan. Wiring them is a 5-minute win that unlocks real value.

#### 1.1 — `code` mode: add `skill-receiving-code-review.md` (Tier 2)

Edit [`.roomodes`](../.roomodes) — find the `code` mode's `customInstructions`. After the existing `SKILLS` block, add:

```yaml
      SKILLS — Tier 2 (load when relevant):
      - .roo/skill-receiving-code-review.md — load when responding to Code Reviewer feedback (after a 🔄 CHANGES REQUESTED verdict); provides the read-all-first rule, 🔴/🟠/🟡/🟢/🔵 categorization, 5-question verification per suggestion, and push-back guidance
```

#### 1.2 — `architect` mode: add `skill-architect-design-review.md` (Tier 1)

Edit [`.roomodes`](../.roomodes) — find the `architect` mode's `customInstructions`. After the existing `SKILLS` block, add:

```yaml
      SKILLS — Tier 1 (load every task):
      - .roo/skill-architect-design-review.md — ADR template (with mandatory negative consequences), 5 ADR anti-patterns, Mermaid diagram standards, plan freshness tagging
```

#### 1.3 — Verify wiring

```bash
cd /Users/mvaturri/Documents/zillow && \
  grep -c 'skill-receiving-code-review' .roomodes && \
  grep -c 'skill-architect-design-review' .roomodes && \
  python3 -c "import yaml; d=yaml.safe_load(open('.roomodes')); print('OK', [m['slug'] for m in d['customModes']])"
```

Expected: 1, 1, OK + 6 modes.

---

### Phase 2 — Migrate `dev-reviewer` and `ux-designer` to Tier 1 / Tier 2 (HIGH IMPACT, 15 min)

**Why:** `dev-reviewer` lists 8 skills "for relevant tasks" and `ux-designer` lists 10 — vague triggers mean they're effectively all considered every task. The `agent-mode-tiering` concept page documents this exact migration; we just need to apply it.

#### 2.1 — `dev-reviewer` migration

Current state ([`.roomodes:91-101`](../.roomodes:91)) — flat list of 8 skill references:
- skill-api-endpoint-review.md
- skill-code-review.md
- skill-data-scraping.md
- skill-notification-system.md
- skill-self-learn.md
- skill-memory-manager.md
- skill-self-reflection.md
- skill-deliverable-scoring.md

Target state — Tier 1 / Tier 2 split:
```yaml
      SKILLS — Tier 1 (load every task):
      - .roo/skill-code-review.md — strict [P1]/[P2]/[P3] + ✅/🔄 verdict format (ALWAYS use this format)
      - .roo/skill-self-reflection.md — REAR template at task end (ALWAYS perform)

      SKILLS — Tier 2 (load when relevant):
      - .roo/skill-api-endpoint-review.md — load when reviewing FastAPI/Flask endpoints (web/routes/*.py)
      - .roo/skill-data-scraping.md — load when reviewing changes under src/scrapers/ or src/orchestrator.py
      - .roo/skill-notification-system.md — load when reviewing src/notifier.py or notification_log changes
      - .roo/skill-deliverable-scoring.md — load before scoring a deliverable's quality (PRDs, ADRs, plans)
      - .roo/skill-memory-manager.md — load only if reviewing wiki/memory file changes (rare for dev-reviewer)
      - .roo/skill-self-learn.md — load at session end if a new pattern was discovered worth proposing
```

#### 2.2 — `ux-designer` migration

Current state ([`.roomodes:140-150`](../.roomodes:140)) — flat list of 10 skill references. Target:
```yaml
      SKILLS — Tier 1 (load every task):
      - .roo/skill-design-system-patterns.md — design tokens, component architecture (ALWAYS reference)
      - .roo/skill-self-reflection.md — REAR template at task end

      SKILLS — Tier 2 (load when relevant):
      - .roo/skill-frontend-design.md — load when implementing responsive layouts or HTML/CSS mockups
      - .roo/skill-ui-ux-pro-max.md — load when picking color palettes, font pairings, or designing complex components
      - .roo/skill-ui-audit.md — load when running a UI audit (7-dimension review)
      - .roo/skill-map-ui.md — load when working on map view, markers, or geospatial UI
      - .roo/skill-filter-search-ux.md — load when working on filter bar or search UX
      - .roo/skill-notification-system.md — load when designing notification preferences UI
      - .roo/skill-memory-manager.md — load only if updating wiki design entries (rare for ux-designer)
      - .roo/skill-self-learn.md — load at session end if a new pattern was discovered
```

#### 2.3 — Update wiki concept page

Update [`agent-mode-tiering.md`](../docs/memory/wiki/concepts/agent-mode-tiering.md) "Migration plan" section — mark `dev-reviewer` and `ux-designer` as ✅ migrated; keep `code`, `architect`, `orchestrator` as pending.

#### 2.4 — Verify

```bash
python3 -c "
import yaml, re
d = yaml.safe_load(open('.roomodes'))
for slug in ('dev-reviewer','ux-designer','debug'):
    m = next(m for m in d['customModes'] if m['slug']==slug)
    ci = m.get('customInstructions') or ''
    t1 = ci.count('SKILLS — Tier 1')
    t2 = ci.count('SKILLS — Tier 2')
    print(f'{slug}: Tier 1 sections={t1}, Tier 2 sections={t2}')
"
```

Expected: each mode shows `Tier 1 sections=1, Tier 2 sections=1`.

---

### Phase 3 — Audit the 7 remaining orphan skills (MEDIUM IMPACT, 10 min)

**The 7 orphans (after Phase 1 wires the 2 we just installed):**

```
skill-agent-optimizer.md       (15 KB — large, possibly important?)
skill-context-engineering.md   (8 KB)
skill-evidence-based-reasoning.md (3 KB)
skill-memory-validator.md      (10 KB)
skill-multi-agent-patterns.md  (7 KB)
skill-prompt-engineering.md    (8 KB)
skill-tool-design.md           (4 KB)
```

Total: ~55 KB of skill content not loaded by any mode.

#### 3.1 — Triage protocol

For each of the 7, run:
```bash
head -20 .roo/skill-NAME.md
```

Then categorize as one of:
- **WIRE** — should be loaded by mode X as Tier Y. Apply the wiring in this same session.
- **MOVE** — useful reference but not for routine task injection. Move to `docs/memory/skills-archive/` (create dir).
- **DELETE** — IDEX-only content irrelevant to SunnyNest. `git rm` it.

#### 3.2 — Apply triage decisions

Make all the WIRE/MOVE/DELETE decisions in one batch, then:
1. Stage all changes (`git add .roo/ docs/memory/`)
2. Commit with message listing each decision (e.g., "skill-prompt-engineering.md: MOVE to archive (useful reference, not per-task)")

#### 3.3 — Update wiki

Add the orphan-triage results to [`docs/memory/wiki/log.md`](../docs/memory/wiki/log.md) under today's date.

---

### Phase 4 — Fix routing rule blind spots (MEDIUM IMPACT, 2 min)

#### 4.1 — Edit AGENTS.md routing table

Edit [`AGENTS.md`](../AGENTS.md:40) — the "Orchestrator Routing Rules" table. Add explicit slug mentions to the existing rows:

```markdown
| review, code review, API review, "check my code" | 🔍 **dev-reviewer** | Quality, security, performance checks |
| mockup, wireframe, UI design, UX review, design system, color palette, typography, accessibility audit, component design, dark mode, responsive design, prototype, "look and feel", "visual" | 🎨 **ux-designer** | Any request mentioning UI/UX/design concepts |
```

(The existing rows already have the right keywords; we're just adding the explicit slug as bold text so the Orchestrator can grep for them.)

#### 4.2 — Verify

```bash
grep -c 'dev-reviewer\|ux-designer' AGENTS.md
```

Expected: at least 2 mentions in the routing table region.

---

### Phase 5 — Trim activeContext.md (LOW IMPACT, 2 min)

Current state: 45 lines (target ≤30, per [`agent-mode-tiering.md`](../docs/memory/wiki/concepts/agent-mode-tiering.md) and the memory manager rules).

#### 5.1 — Specific trim

In [`docs/memory/tasks/default/activeContext.md`](../docs/memory/tasks/default/activeContext.md):
- **Remove** the IDEX adoption "Recent Changes" entry (it's locked in commit history; the wiki log has the full record). Replace with a 1-line: `[2026-05-08] IDEX adoption Phase 1 + agent team cleanup → see wiki/log.md`.
- **Consolidate** the 5 P3 follow-up bullets in Action Items into a single line: `Address 5 P3 follow-ups from WhatsApp Code Review → see [log.md](../../wiki/log.md#whatsapp-token-expiry-detection--visible-failure-surfacing)`.
- **Keep** the WhatsApp token-regeneration warning and the launchd-log investigation (those are LIVE issues).

#### 5.2 — Verify

```bash
wc -l docs/memory/tasks/default/activeContext.md
```

Expected: ≤30 lines.

---

### Phase 6 — Clean up docs/temp/ leftovers (LOW IMPACT, 1 min)

```bash
cd /Users/mvaturri/Documents/zillow && \
  ls -la docs/temp/*.bak docs/temp/apply-phase1.sh 2>&1 && \
  rm -f docs/temp/apply-phase1.sh docs/temp/roomodes.bak docs/temp/skill-code-review.md.bak && \
  echo "removed 3 leftovers" && \
  ls -la docs/temp/
```

The remaining files in `docs/temp/` (the spec, the install script, the post-mortem doc) are intentional historical artifacts — keep them.

---

## 🚀 Execution recipe (single atomic commit)

After Phases 1, 2, 4, 5, 6 are done, commit them all together:

```bash
cd /Users/mvaturri/Documents/zillow && \
  git status --short && \
  git add .roomodes AGENTS.md docs/memory/tasks/default/activeContext.md docs/memory/wiki/concepts/agent-mode-tiering.md docs/memory/wiki/log.md && \
  git commit -m "feat(modes): wire orphan skills, migrate to Tier 1/Tier 2, trim memory

Phase 1: Wire 2 newly-installed skills
- code mode now loads .roo/skill-receiving-code-review.md (Tier 2)
- architect mode now loads .roo/skill-architect-design-review.md (Tier 1)

Phase 2: Migrate dev-reviewer + ux-designer to Tier 1/Tier 2 loading
- dev-reviewer: 2 Tier 1 (code-review + self-reflection) + 6 Tier 2
- ux-designer: 2 Tier 1 (design-system-patterns + self-reflection) + 8 Tier 2

Phase 4: AGENTS.md routing table now explicitly mentions
  **dev-reviewer** and **ux-designer** slugs

Phase 5: activeContext.md trimmed back to ≤30 lines (was 45)

Phase 6: docs/temp/*.bak + apply-phase1.sh removed (committed already)

Net effect: orphan skill count drops 9 → 7 (Phase 1)
           tier-migrated mode count rises 1 → 3 (Phase 2)
           routing table coverage 3/5 → 5/5 (Phase 4)
           activeContext.md size 45 → ≤30 lines (Phase 5)"
```

Phase 3 (orphan triage) commits separately because the decisions per-skill might warrant separate commits or different handling (e.g., `git rm` vs. `git mv`).

---

## ✅ Success criteria

- [ ] `grep -c 'skill-receiving-code-review' .roomodes` returns ≥1
- [ ] `grep -c 'skill-architect-design-review' .roomodes` returns ≥1
- [ ] `dev-reviewer` mode in `.roomodes` has both `Tier 1` and `Tier 2` headings
- [ ] `ux-designer` mode in `.roomodes` has both `Tier 1` and `Tier 2` headings
- [ ] `agent-mode-tiering.md` "Migration plan" updated with ✅ markers for the 2 migrated modes
- [ ] AGENTS.md routing table includes literal `**dev-reviewer**` and `**ux-designer**`
- [ ] `wc -l docs/memory/tasks/default/activeContext.md` ≤ 30
- [ ] `ls docs/temp/*.bak 2>/dev/null | wc -l` returns 0
- [ ] After Phase 3: orphan skill count ≤ 2 (or all 7 categorized)
- [ ] All changes in a single commit (Phases 1-2-4-5-6); Phase 3 may be separate
- [ ] YAML still parses; `.roomodes` still has 6 modes

---

## 📐 Quality gate (apply [`skill-deliverable-scoring.md`](../.roo/skill-deliverable-scoring.md))

Before `attempt_completion`:

| Dimension | Target | How to score |
|-----------|--------|--------------|
| Accuracy | 5/5 | All 8 success criteria above pass |
| Completeness | 4-5/5 | All 6 phases done OR explicit reason for skipping |
| Clarity | 4-5/5 | Commit message lists what changed in each mode |

Threshold: weighted score ≥ 0.85.

---

## 🪞 What could go wrong

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| `.roomodes` YAML breaks (indent/quote issue) | MEDIUM | Validate with `python3 -c "import yaml; yaml.safe_load(open('.roomodes'))"` after each edit |
| Phase 3 over-deletes a skill that's actually wired indirectly | LOW | Triage uses `head -20` not `rm`; review heading + first few sentences before deciding |
| The IDE/Roo lifecycle hook reverts `.roomodes` after edits | LOW | We learned the `git commit` bypass yesterday — chain edits + add + commit |
| activeContext.md trim removes information someone needs | LOW | The wiki log preserves everything; activeContext is meant to be a short-term pointer |

---

## 📚 References (read these if you need to refresh memory)

- [`agent-mode-tiering`](../docs/memory/wiki/concepts/agent-mode-tiering.md) — Tier 1/Tier 2 pattern + migration plan
- [`agent-failure-discipline`](../docs/memory/wiki/concepts/agent-failure-discipline.md) — 2-failure rule + 7 "never assume"
- [`AGENTS.md §8`](../AGENTS.md) — `.roo/` system guard + `git commit` bypass
- [`AGENTS.md §9`](../AGENTS.md) — Agent Execution Discipline (canonical: `.roo/rules/shared.md` §14)
- [`docs/memory/wiki/log.md`](../docs/memory/wiki/log.md) — yesterday's IDEX adoption entry (commit `7cef222`)

---

## ⏰ When to revisit

After this plan executes, the next agent-team-tuning session should consider:
- Migrating `code`, `architect`, `orchestrator` to Tier 1 / Tier 2 (deferred from Phase 2)
- Pruning `agent-mode-tiering.md` "Migration plan" section once all 6 modes are migrated
- Re-auditing skill orphan count quarterly

That's a future task, not part of this plan.
