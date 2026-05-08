# Skill: Architect Design Review (ADR + Diagram Standards)

> **Tier 1 — Architect mode default skill.** Defines the ADR template, diagram standards, and plan-freshness tagging used in [`plans/`](../plans/) and [`docs/`](../docs/).

## Purpose
Bring rigor to architectural decisions:
- Every significant decision gets an ADR (Architecture Decision Record).
- Every plan diagram follows the same Mermaid conventions.
- Old plans are explicitly tagged so future readers know what's still authoritative.

---

## ADR Template

File location: `plans/adr-NNN-<short-slug>.md` (e.g., `plans/adr-001-launchd-over-apscheduler.md`).

```markdown
# ADR-NNN: <Decision in active voice>

**Status:** Proposed | Accepted | Deprecated | Superseded by [ADR-MMM](adr-MMM-...)
**Date:** YYYY-MM-DD
**Deciders:** <names / roles>
**Tags:** <e.g., scheduling, scraping, notifications>

## Context
<2-4 paragraphs: what problem are we solving? What are the constraints? What's the current state? Cite wiki entities (e.g., [Scheduler (launchd)](../docs/memory/wiki/entities/scheduler-launchd.md)).>

## Options Considered
We evaluated ≥2 options.

### Option A: <name>
- **Pros:** ...
- **Cons:** ...
- **Cost:** <effort, $, risk>

### Option B: <name>
- **Pros:** ...
- **Cons:** ...
- **Cost:** ...

### Option C (if applicable): <name>
- ...

## Decision
We chose **Option <X>**.

## Rationale
<Why X over Y/Z. Reference the constraints from Context. Be explicit about which trade-offs we accepted.>

## Consequences
**Positive:**
- ...

**Negative:** *(MANDATORY — see anti-patterns below)*
- ...

**Neutral:**
- ...

## Dependencies
- Blocks: ADR-NNN, ticket #N
- Blocked by: ADR-MMM
- Related entities: [Entity A](../docs/memory/wiki/entities/a.md), [Entity B](...)

## Review
- **Next review date:** YYYY-MM-DD (typically +180 days)
- **Triggers for early review:** <e.g., "if monthly Zillow API calls exceed 400">
```

---

## ADR Anti-Patterns (avoid these)

| # | Anti-pattern | Why it's bad | SunnyNest fix |
|---|--------------|--------------|---------------|
| 1 | **Single option presented** ("we will use X") | No evidence the decision was actually a decision | Always document ≥2 options, even if one is "do nothing" |
| 2 | **Consequences section all positive** | Every architectural choice has trade-offs; hiding them = future debt | List ≥1 negative consequence; "we accept X cost in exchange for Y benefit" |
| 3 | **Vague status** ("In progress", "Maybe?") | Future readers can't tell if this is authoritative | Use only the 4 statuses: Proposed / Accepted / Deprecated / Superseded |
| 4 | **No review date** | Decisions ossify; nobody re-evaluates | Always include `Next review date` (default +180d) |
| 5 | **Hand-wavy rationale** ("seems best", "industry standard") | Unfalsifiable; can't be challenged | Tie rationale to specific Context constraints |

> Real example: [`plans/cloud-scheduler.md`](../plans/cloud-scheduler.md:1) properly evaluated multiple options (GitHub Actions, Cloud Run, etc.) before recommending GitHub Actions + git-committed DB. Use it as a template for option-comparison structure.

---

## Mermaid Diagram Standards

### ✅ Approved Diagram Types
| Type | Use For | Example |
|------|---------|---------|
| `flowchart TD` | Pipelines, decision trees | Scrape → Normalize → Geocode → Upsert |
| `flowchart LR` | Wide horizontal flows | Source → Adapter → Orchestrator → DB |
| `sequenceDiagram` | Cross-service request flow | User → Web → DB → Render |
| `erDiagram` | DB schema | Listing ⟷ PriceHistory |
| `stateDiagram-v2` | Lifecycle | Listing: Active → Inactive → Deleted |
| `graph LR` | Simple dependency graphs | Module imports |

### ❌ Avoid
- **>15 nodes per diagram** — split into multiple linked diagrams instead
- **Unlabeled edges** — every arrow must say what passes over it (e.g., `JSON`, `listing[]`, `event`)
- **Color-only differentiation** — fails accessibility; pair color with shape or text label
- `gantt`, `pie`, `mindmap` — usually wrong tool; rewrite as a table or flowchart
- Fancy themes / custom CSS — use Mermaid defaults; consistency > prettiness

### Diagram Quality Checklist
- [ ] ≤15 nodes
- [ ] Every edge labeled (data type or trigger)
- [ ] Direction is consistent (TD or LR — don't mix in one diagram)
- [ ] Node names match real code/entity names (not abstract "Service A")
- [ ] If color used, shape or text also conveys the distinction (a11y)
- [ ] Cross-referenced from at least one wiki page or plan
- [ ] Renders correctly in GitHub preview (test before committing)

---

## Plan Freshness Tagging

Files in [`plans/`](../plans/) have a long shelf-life and silently rot. Tag every plan in [`docs/memory/wiki/index.md`](../docs/memory/wiki/index.md:1) with a freshness indicator:

| Tag | Age (since last update) | Action |
|-----|--------------------------|--------|
| 🟢 **Fresh** | <60 days | Trust as authoritative |
| 🟡 **Aging** | 60–180 days | Spot-check against current state before relying on it |
| 🔴 **Expired** | >180 days | Do NOT trust without re-validation. Either: (a) refresh and re-tag, (b) mark `SUPERSEDED`, or (c) move to `plans/archive/` |

Run a freshness audit during quarterly wiki lint per [`skill-wiki-lint.md`](skill-wiki-lint.md:1). Re-tag in the index table.

---

## Design-Bible Cross-Reference

For ANY ADR involving UI/UX or visual design, cross-reference [`docs/design/design-bible.md`](../docs/design/design-bible.md:1):

- Color, typography, spacing decisions → must align with Design Bible tokens, OR explicitly propose updating the Bible.
- Layout decisions (split-pane, card grid, etc.) → check Design Bible's layout patterns first.
- If your ADR proposes a Design Bible change, list "Updates Design Bible: §<section>" under Dependencies.

The UX Designer mode owns the Design Bible. Architect proposes; UX Designer ratifies (via a follow-up task).

---

## Wiki Impact Section (mandatory in every plan)

Every architecture plan MUST end with a Wiki Impact section per [Architect mode rules in `.roomodes`](../.roomodes:246):

```markdown
## Wiki Impact
- **New entities:** <list, or "None">
- **Updated entities:** <list>
- **New concepts:** <list, or "None">
```

This drives the Orchestrator's wiki-sync step after the plan is accepted.

---

## Quick Checklist (before publishing an ADR)

- [ ] ≥2 options evaluated, each with pros/cons/cost
- [ ] Consequences section has ≥1 negative item
- [ ] Status is one of the 4 standard values
- [ ] Review date set
- [ ] Rationale ties back to specific Context constraints
- [ ] All diagrams pass the Diagram Quality Checklist
- [ ] Wiki Impact section included
- [ ] Cross-referenced from [`plans/architecture.md`](../plans/architecture.md:1) (or note why not)
- [ ] If UI/UX-related: Design Bible alignment confirmed
