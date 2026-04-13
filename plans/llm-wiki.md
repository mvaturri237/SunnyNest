# LLM Wiki Implementation Plan

**Date:** 2026-04-06  
**Status:** PLAN — awaiting owner approval  
**Inspired by:** [Karpathy LLM Wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)  
**Estimated effort:** ~3.5 hours (Phase 0: 2h, Phase 1: 1h, Phase 2: 30m)

---

## 1. Architecture Overview

The Karpathy LLM Wiki defines three layers for LLM-maintained knowledge:

```
┌─────────────────────────────────────────────────────────────────┐
│  LAYER 3: THE SCHEMA                                            │
│  AGENTS.md · .roomodes · skill-memory-manager.md                │
│  ─── Tells the LLM HOW to maintain the wiki ───                │
│  (Ingest rules, Query protocol, Lint checks, entity templates)  │
└─────────────────────────────────────────────────────────────────┘
        │ governs ▼
┌─────────────────────────────────────────────────────────────────┐
│  LAYER 2: THE WIKI                    docs/memory/wiki/         │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐           │
│  │ index.md │ │ log.md   │ │ entity/  │ │ concept/ │           │
│  │ (catalog)│ │ (chrono) │ │ pages    │ │ pages    │           │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘           │
│  ─── LLM-generated, LLM-maintained markdown ───                │
│  One page per entity, updated over time (not appended)          │
└─────────────────────────────────────────────────────────────────┘
        │ reads ▼
┌─────────────────────────────────────────────────────────────────┐
│  LAYER 1: RAW SOURCES (immutable — LLM reads, never modifies)  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐           │
│  │ src/     │ │ web/     │ │ plans/   │ │ config/  │           │
│  │ (code)   │ │ (UI)     │ │ (specs)  │ │ (yaml)   │           │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘           │
│  ─── The codebase + git history + architecture plans ───        │
│  No separate raw/ directory needed in a software project        │
└─────────────────────────────────────────────────────────────────┘
```

### Four Operations

| Operation | Trigger | What Happens |
|-----------|---------|--------------|
| **Ingest** | After Code→Review cycle completes, or after Architect creates a plan | Update affected entity pages, append to `log.md`, refresh `index.md` |
| **Query** | At task start (replaces current "read memory" step) | Read `index.md` → drill into relevant entity pages → read only what's needed |
| **Lint** | Manual command (`/wiki-lint`) or every ~10 tasks | Check for contradictions, stale pages, orphans, missing cross-references |
| **Index + Log** | Part of every Ingest | `index.md` = content catalog; `log.md` = chronological append-only record |

### Key Design Decisions (from gap analysis)

1. **No separate Librarian mode** — the Orchestrator handles wiki sync as part of its existing Code→Review workflow
2. **No separate `raw/` directory** — raw sources are the codebase + git history + `plans/`
3. **Entity pages are the core innovation** — one page per entity, updated over time (not chronological entries)
4. **`index.md` + `log.md`** replace the bloated [`activeContext.md`](../docs/memory/tasks/default/activeContext.md) hybrid (currently 436 lines)
5. **Only Code, Architect, and UX Designer feed the wiki** — Debug and Ask are exempt
6. **Simple markdown links** (not Obsidian wiki-links) since we use VS Code

---

## 2. Directory Structure: Before → After

### Before (current)

```
docs/memory/
├── shared/
│   ├── decisionLog.md          # 182 lines, chronological, cross-cutting
│   ├── lessonsLearned.md       # 165 lines, chronological, cross-cutting
│   └── systemPatterns.md       # 89 lines, by-pattern, cross-cutting
└── tasks/
    └── default/
        ├── activeContext.md    # 436 lines — hybrid: focus + recent changes + decisions
        └── progress.md        # 341 lines — chronological completed/planned list
```

**Problems:**
- Knowledge about a single entity (e.g., Realtor scraper) is scattered across 4+ files
- `activeContext.md` is a 436-line append-only blob — agents must read ALL of it to find relevant context
- No way to query "what do we know about the scheduler?" without reading everything
- No entity pages, no index, no lint operation

### After (proposed)

```
docs/memory/
├── wiki/                              # NEW — Layer 2: The Wiki
│   ├── index.md                       # Content catalog — read FIRST on every query
│   ├── log.md                         # Chronological append-only record (replaces progress.md history)
│   ├── entities/                      # One page per system component
│   │   ├── zillow-scraper.md
│   │   ├── craigslist-scraper.md
│   │   ├── realtor-scraper.md
│   │   ├── orchestrator.md
│   │   ├── deduplication.md
│   │   ├── notification-system.md
│   │   ├── scheduler-launchd.md
│   │   ├── database-schema.md
│   │   ├── geocoder.md
│   │   ├── school-districts.md
│   │   ├── filter-bar.md
│   │   ├── map-view.md
│   │   ├── admin-dashboard.md
│   │   ├── api-usage-page.md
│   │   ├── listing-card.md
│   │   └── config-yaml.md
│   └── concepts/                      # Cross-cutting patterns and lessons
│       ├── adapter-pattern.md
│       ├── app-isolation.md
│       ├── css-cache-versioning.md
│       ├── environment-validation.md
│       ├── jinja2-safety.md
│       ├── launchd-patterns.md
│       ├── review-cycle.md
│       ├── security-patterns.md
│       ├── silent-failure-pattern.md
│       └── upsert-exclusion-pattern.md
├── shared/                            # KEPT — cross-cutting shared files (see Open Questions)
│   ├── decisionLog.md                 # Keep as-is (chronological decision record)
│   ├── lessonsLearned.md              # Keep as-is (chronological lesson record)
│   └── systemPatterns.md              # Keep as-is (pattern catalog)
└── tasks/
    └── default/
        ├── activeContext.md           # SLIMMED to ~20 lines (pointer file)
        └── progress.md               # SLIMMED to current sprint only
```

### What Changes for Each Existing File

| File | Current Size | Action | New Size |
|------|-------------|--------|----------|
| [`activeContext.md`](../docs/memory/tasks/default/activeContext.md) | 436 lines | Slim to pointer: Current Focus + 3 most recent changes + link to `wiki/index.md` | ~20 lines |
| [`progress.md`](../docs/memory/tasks/default/progress.md) | 341 lines | Archive history into `wiki/log.md`; keep only current sprint items | ~30 lines |
| [`decisionLog.md`](../docs/memory/shared/decisionLog.md) | 182 lines | Keep as-is (see Open Questions §8.1) | 182 lines |
| [`lessonsLearned.md`](../docs/memory/shared/lessonsLearned.md) | 165 lines | Keep as-is (see Open Questions §8.1) | 165 lines |
| [`systemPatterns.md`](../docs/memory/shared/systemPatterns.md) | 89 lines | Keep as-is (see Open Questions §8.1) | 89 lines |

---

## 3. Entity Page Template

Every entity page follows this standard template:

```markdown
# {Entity Name}

> One-sentence summary of what this entity is and does.

**Status:** Active | Deprecated | Planned  
**Owner files:** `path/to/main/file.py`, `path/to/other.py`  
**Config:** `config.yaml` → `section.key`  
**Added:** YYYY-MM-DD  
**Last updated:** YYYY-MM-DD

## Overview
2-3 paragraph description of the entity's purpose, how it fits into the system,
and its key responsibilities.

## Architecture
- Key design decisions and patterns used
- Integration points with other entities (with links to their pages)
- Data flow description

## Current State
- What's implemented and working
- Known limitations or caveats
- Performance characteristics (if relevant)

## Configuration
- Config keys and their meanings
- Environment variables required
- Default values

## Key Files
| File | Purpose |
|------|---------|
| `src/example.py` | Main implementation |
| `web/templates/example.html` | UI template |
| `config.yaml` → `example_api` | Configuration section |

## History
- [YYYY-MM-DD] Most recent change (link to log.md entry)
- [YYYY-MM-DD] Previous change
- [YYYY-MM-DD] Initial implementation

## Related
- [Other Entity](other-entity.md) — how they interact
- [Concept Page](../concepts/relevant-concept.md) — applicable pattern
- [Plan](../../../plans/relevant-plan.md) — architecture plan
```

### Concept Page Template

Concept pages are lighter — they capture cross-cutting patterns and lessons:

```markdown
# {Concept Name}

> One-sentence description of the pattern or lesson.

**Applies to:** [Entity A](../entities/a.md), [Entity B](../entities/b.md)  
**Learned:** YYYY-MM-DD  
**Source:** `docs/memory/shared/lessonsLearned.md` or `systemPatterns.md`

## Pattern
Description of the pattern, why it exists, and when to apply it.

## Rules
1. Concrete rule 1
2. Concrete rule 2

## Examples
- Where this pattern is currently applied in the codebase
- Anti-patterns to avoid

## Related
- [Entity pages that implement this pattern](../entities/example.md)
```

---

## 4. `index.md` Structure

[`index.md`](../docs/memory/wiki/index.md) is the **entry point** for every Query operation. Agents read this FIRST, then drill into relevant pages.

```markdown
# SunnyNest Wiki Index

> Last updated: YYYY-MM-DD | Entities: 16 | Concepts: 10

## Entity Pages

### Data Pipeline
| Entity | Status | Summary | Last Updated |
|--------|--------|---------|-------------|
| [Zillow Scraper](entities/zillow-scraper.md) | Active | RapidAPI source, 500 req/mo, primary data source | 2026-03-31 |
| [Craigslist Scraper](entities/craigslist-scraper.md) | Active | HTML scraping via Playwright, free, secondary source | 2026-03-28 |
| [Realtor Scraper](entities/realtor-scraper.md) | Active | RapidAPI source, 150 req/mo, third data source | 2026-04-01 |
| [Orchestrator](entities/orchestrator.md) | Active | Coordinates scrape→normalize→geocode→enrich→upsert→dedup pipeline | 2026-04-01 |
| [Deduplication](entities/deduplication.md) | Active | Cross-source dedup via multi-signal scoring, threshold ≥75 | 2026-03-28 |
| [Geocoder](entities/geocoder.md) | Active | Nominatim + LRU cache + circuit breaker | 2026-03-27 |

### User-Facing UI
| Entity | Status | Summary | Last Updated |
|--------|--------|---------|-------------|
| [Filter Bar](entities/filter-bar.md) | Active | Price/Beds/Baths/More dropdowns, HTMX-driven | 2026-03-31 |
| [Map View](entities/map-view.md) | Active | Leaflet.js, price pills, clustering planned | 2026-03-30 |
| [Listing Card](entities/listing-card.md) | Active | Horizontal card with image, price, schools, source pills | 2026-03-31 |

### Admin / Backend
| Entity | Status | Summary | Last Updated |
|--------|--------|---------|-------------|
| [Admin Dashboard](entities/admin-dashboard.md) | Active | System health, sync button, scrape heatmap | 2026-04-06 |
| [API Usage Page](entities/api-usage-page.md) | Active | Donut charts, success trends, sparklines | 2026-04-06 |
| [Notification System](entities/notification-system.md) | Active | Email channel, config-filtered, anti-spam guard | 2026-03-31 |
| [Scheduler (launchd)](entities/scheduler-launchd.md) | Active | 3 plists: scraper, notify-am, notify-pm | 2026-04-06 |
| [Database Schema](entities/database-schema.md) | Active | SQLite, 5 tables, manual migrations | 2026-03-31 |
| [School Districts](entities/school-districts.md) | Active | GeoJSON boundaries, shapely point-in-polygon | 2026-03-31 |
| [Config (YAML)](entities/config-yaml.md) | Active | Central config: filters, API keys, notification settings | 2026-04-06 |

## Concept Pages

| Concept | Applies To | Summary |
|---------|-----------|---------|
| [Adapter Pattern](concepts/adapter-pattern.md) | Scrapers, Notifications | BaseScraper ABC, source-agnostic orchestrator |
| [App Isolation](concepts/app-isolation.md) | Dashboard, Backoffice | Separate Streamlit apps, no st.sidebar in app.py |
| [CSS Cache Versioning](concepts/css-cache-versioning.md) | All CSS files | Bump ?v=N on every CSS change |
| [Environment Validation](concepts/environment-validation.md) | Startup, Admin | Validate env vars at boot, show in System Health |
| [Jinja2 Safety](concepts/jinja2-safety.md) | All templates | Unicode chars only, no HTML entities in {{ }} |
| [launchd Patterns](concepts/launchd-patterns.md) | Scheduler, Dashboard | macOS process management, TCC, Homebrew Python |
| [Review Cycle](concepts/review-cycle.md) | All code changes | Code→Review→Fix mandatory cycle |
| [Security Patterns](concepts/security-patterns.md) | XSS, TLS, secrets | html.escape, verify=True, env vars for secrets |
| [Silent Failure Pattern](concepts/silent-failure-pattern.md) | Scrapers, SMTP | Credential-dependent features fail silently |
| [Upsert Exclusion Pattern](concepts/upsert-exclusion-pattern.md) | Database | User-managed flags excluded from scraper updates |

## Quick Reference

- **Log:** [log.md](log.md) — chronological record of all changes
- **Shared files:** [decisionLog](../shared/decisionLog.md) · [lessonsLearned](../shared/lessonsLearned.md) · [systemPatterns](../shared/systemPatterns.md)
- **Plans:** [plans/](../../plans/) — 17 architecture plan files
- **Design Bible:** [design-bible.md](../design/design-bible.md)
```

---

## 5. `log.md` Format Specification

[`log.md`](../docs/memory/wiki/log.md) is a **chronological, append-only** record. It replaces the historical sections of [`activeContext.md`](../docs/memory/tasks/default/activeContext.md) and [`progress.md`](../docs/memory/tasks/default/progress.md).

```markdown
# SunnyNest Wiki Log

> Chronological record of all changes. Newest entries at top.
> Each entry links to affected entity/concept pages.

---

## 2026-04-06

### Admin API Usage Page Redesigned
- **Result:** APPROVED (0 P1, 0 P2 after 1 fix cycle, 9 P3)
- **Entities updated:** [API Usage Page](entities/api-usage-page.md), [Admin Dashboard](entities/admin-dashboard.md), [Database Schema](entities/database-schema.md)
- **Summary:** Complete overhaul — donut charts, success trends, sparklines. ~500 lines new CSS.
- **Files:** `src/database.py`, `web/routes/admin.py`, `web/templates/admin/api-usage.html`, `web/static/css/admin.css`

### Scheduler Fix Implemented
- **Result:** APPROVED (0 P1, 0 P2, 7 P3)
- **Entities updated:** [Scheduler](entities/scheduler-launchd.md), [Admin Dashboard](entities/admin-dashboard.md)
- **Concepts updated:** [launchd Patterns](concepts/launchd-patterns.md)
- **Summary:** APScheduler replaced with macOS launchd. 3 new plists, 2 standalone scripts.

### Cloud Scheduler Evaluation
- **Result:** COMPLETE (plan only)
- **Entities updated:** [Scheduler](entities/scheduler-launchd.md)
- **Summary:** Evaluated 3 options. Recommended GitHub Actions + git-committed DB for immediate use.
- **Plan:** `plans/cloud-scheduler.md`

---

## 2026-04-01

### Realtor.com Scraper Implemented
- **Result:** APPROVED (0 P1, 0 P2, 8 P3 after fix cycle)
- **Entities updated:** [Realtor Scraper](entities/realtor-scraper.md) (NEW), [Orchestrator](entities/orchestrator.md), [Config](entities/config-yaml.md)
- **Concepts updated:** [Adapter Pattern](concepts/adapter-pattern.md)
- **Summary:** Third data source. RapidAPI, 150 req/mo free tier.

(... historical entries migrated from progress.md ...)
```

### Log Entry Format

Each entry follows this structure:
```
### {Title}
- **Result:** {APPROVED | COMPLETE | IMPLEMENTED} ({P1/P2 counts})
- **Entities updated:** [links to affected entity pages]
- **Concepts updated:** [links to affected concept pages] (if any)
- **Summary:** 1-2 sentence description
- **Files:** key files changed (optional, for code changes)
- **Plan:** link to plan file (optional, for architecture work)
```

---

## 6. Phase 0: Bootstrap (~2h)

### Step 0.1: Create Directory Structure

```bash
mkdir -p docs/memory/wiki/entities
mkdir -p docs/memory/wiki/concepts
```

### Step 0.2: Create Entity Pages (16 pages)

Extract knowledge from existing memory files into entity pages. Each entity page consolidates information currently scattered across [`activeContext.md`](../docs/memory/tasks/default/activeContext.md), [`progress.md`](../docs/memory/tasks/default/progress.md), [`decisionLog.md`](../docs/memory/shared/decisionLog.md), [`lessonsLearned.md`](../docs/memory/shared/lessonsLearned.md), and [`systemPatterns.md`](../docs/memory/shared/systemPatterns.md).

**Entity decomposition map** — where each entity's knowledge currently lives:

| Entity Page | activeContext.md | progress.md | decisionLog.md | lessonsLearned.md | systemPatterns.md |
|-------------|:---:|:---:|:---:|:---:|:---:|
| `zillow-scraper.md` | ✓ (API key issue) | ✓ | ✓ (code review) | ✓ (silent failure, env vars) | ✓ (adapter, budget guard) |
| `craigslist-scraper.md` | ✓ | ✓ | ✓ (renewal dates) | ✓ (renewal dates) | ✓ (adapter) |
| `realtor-scraper.md` | ✓ (lines 43-56) | ✓ (lines 40-52) | ✓ (lines 13-21) | — | ✓ (adapter, budget) |
| `orchestrator.md` | ✓ (pipeline refs) | ✓ | — | — | ✓ (adapter pattern) |
| `deduplication.md` | — | — | ✓ (lines 121-131) | — | ✓ (dedup patterns) |
| `notification-system.md` | ✓ (39-listing fix) | ✓ (filter fix) | — | ✓ (silent failure) | ✓ (config-driven) |
| `scheduler-launchd.md` | ✓ (lines 25-34) | ✓ (lines 20-30) | ✓ (lines 1-11) | ✓ (APScheduler, launchd) | ✓ (background jobs) |
| `database-schema.md` | ✓ (school cols) | ✓ | ✓ (analytics) | ✓ (upsert exclusion) | ✓ (monotonic dates) |
| `geocoder.md` | — | — | ✓ (code review) | — | ✓ (singleton, cache, circuit) |
| `school-districts.md` | ✓ (lines 72-86) | ✓ (lines 62-77) | ✓ (lines 23-30) | — | ✓ (lazy singleton) |
| `filter-bar.md` | ✓ (lines 96-100) | ✓ (lines 78-89) | — | — | — |
| `map-view.md` | ✓ (Leaflet confirmed) | — | ✓ (framework eval) | — | — |
| `listing-card.md` | ✓ (school display) | ✓ | — | ✓ (CSS card layout) | — |
| `admin-dashboard.md` | ✓ (sync button, heatmap) | ✓ (lines 91-99) | — | — | — |
| `api-usage-page.md` | ✓ (lines 7-18) | ✓ (lines 4-14) | — | ✓ (CSS cache, config override) | — |
| `config-yaml.md` | ✓ (filter refs) | — | ✓ (settings persistence) | ✓ (config override) | ✓ (config-driven filtering) |

### Step 0.3: Create Concept Pages (10 pages)

Extract cross-cutting patterns from [`lessonsLearned.md`](../docs/memory/shared/lessonsLearned.md) and [`systemPatterns.md`](../docs/memory/shared/systemPatterns.md):

| Concept Page | Source File | Source Section |
|-------------|------------|----------------|
| `adapter-pattern.md` | systemPatterns.md | Multi-Source Scraper Pattern |
| `app-isolation.md` | lessonsLearned.md + systemPatterns.md | App Isolation sections |
| `css-cache-versioning.md` | lessonsLearned.md | CSS Cache Versioning |
| `environment-validation.md` | lessonsLearned.md + systemPatterns.md | Silent Failure + Startup Validation |
| `jinja2-safety.md` | lessonsLearned.md | Jinja2 Auto-Escaping |
| `launchd-patterns.md` | lessonsLearned.md | Streamlit process manager + TCC + APScheduler |
| `review-cycle.md` | lessonsLearned.md | switch_mode bypass |
| `security-patterns.md` | systemPatterns.md + lessonsLearned.md | Security Patterns + Code Review Patterns |
| `silent-failure-pattern.md` | lessonsLearned.md | Silent Failure Pattern |
| `upsert-exclusion-pattern.md` | lessonsLearned.md + systemPatterns.md | User-Managed Flags + Monotonic Dates |

### Step 0.4: Create `index.md`

Use the structure from §4 above. Populate with all 16 entities and 10 concepts.

### Step 0.5: Create `log.md`

Migrate the chronological history from [`progress.md`](../docs/memory/tasks/default/progress.md) (341 lines) into `log.md` using the format from §5. Group by date, link to entity pages.

### Step 0.6: Slim `activeContext.md` to ~20 Lines

Replace the current 436-line [`activeContext.md`](../docs/memory/tasks/default/activeContext.md) with a pointer file:

```markdown
# Active Context

## Current Focus
Frontend migration complete. Map makeover implementation next (`plans/map-makeover-impl.md`).
User must run `scripts/install-service.sh` to activate launchd agents.

## Recent Changes (last 3)
- [2026-04-06] Admin API Usage page redesigned — [log entry](../wiki/log.md#admin-api-usage-page-redesigned)
- [2026-04-06] Scheduler fix (launchd) — [log entry](../wiki/log.md#scheduler-fix-implemented)
- [2026-04-06] Cloud scheduler evaluation — [log entry](../wiki/log.md#cloud-scheduler-evaluation)

## Action Items
- Run `scripts/install-service.sh` to activate launchd agents
- Set `SMTP_PASSWORD` in `.env` for email notifications
- Subscribe to "Realtor Search" API on RapidAPI

## Full History
→ See [wiki/log.md](../wiki/log.md)

## Entity Index
→ See [wiki/index.md](../wiki/index.md)
```

### Step 0.7: Slim `progress.md` to Current Sprint

Replace the current 341-line [`progress.md`](../docs/memory/tasks/default/progress.md) with current-sprint-only:

```markdown
# Progress

## In Progress
- [ ] Map makeover implementation (`plans/map-makeover-impl.md`)

## Planned
- [ ] Price history tracking (`plans/price-history.md`)
- [ ] Cloud scheduler setup (`plans/cloud-scheduler.md`)

## Completed (this sprint)
- [x] [2026-04-06] Admin API Usage page redesign
- [x] [2026-04-06] Scheduler fix (launchd)
- [x] [2026-04-06] Cloud scheduler evaluation

## Full History
→ See [wiki/log.md](../wiki/log.md)
```

---

## 7. Phase 1: Schema Updates (~1h)

### 7.1 Changes to [`AGENTS.md`](../AGENTS.md)

#### §1 — Memory Protocol (replace existing section)

**Current text (lines 102-105):**
```markdown
### §1 — Memory Protocol
All agents read memory at task start and write memory at task end.  
📍 Memory location: [`docs/memory/`](docs/memory/)  
📖 See [`.roo/skill-memory-manager.md`](.roo/skill-memory-manager.md)
```

**New text:**
```markdown
### §1 — Memory Protocol (Wiki-Based)
All agents use the LLM Wiki for knowledge management.  
📍 Wiki location: [`docs/memory/wiki/`](docs/memory/wiki/)  
📖 See [`.roo/skill-memory-manager.md`](.roo/skill-memory-manager.md)

**Query (task start):**
1. Read [`wiki/index.md`](docs/memory/wiki/index.md) to find relevant entity pages
2. Read only the entity pages relevant to the current task
3. Read [`activeContext.md`](docs/memory/tasks/default/activeContext.md) for current focus and action items

**Ingest (task end — Code, Architect, UX Designer only):**
1. Update affected entity pages in `docs/memory/wiki/entities/`
2. Update affected concept pages in `docs/memory/wiki/concepts/` (if patterns changed)
3. Append entry to [`wiki/log.md`](docs/memory/wiki/log.md)
4. Update [`wiki/index.md`](docs/memory/wiki/index.md) "Last Updated" dates
5. Update [`activeContext.md`](docs/memory/tasks/default/activeContext.md) (keep only 3 most recent changes)

**Exempt modes:** Debug and Ask do not write to the wiki.

**Lint:** Run periodically per [`.roo/skill-wiki-lint.md`](.roo/skill-wiki-lint.md)
```

#### Add §7 — Wiki Sync Protocol (new section, after §6)

```markdown
### §7 — Wiki Sync Protocol
After the Code → Review cycle completes, the Orchestrator performs wiki sync:

1. **Identify affected entities** — from the Code mode's completion message (which must list affected entities)
2. **Update entity pages** — modify `docs/memory/wiki/entities/{entity}.md` with new state
3. **Update concept pages** — if a cross-cutting pattern was learned or changed
4. **Append to log** — add entry to `docs/memory/wiki/log.md`
5. **Refresh index** — update "Last Updated" dates in `docs/memory/wiki/index.md`

The Orchestrator may delegate wiki sync to Architect mode via `new_task` if the changes are complex.
```

### 7.2 Changes to [`.roo/skill-memory-manager.md`](.roo/skill-memory-manager.md)

**Replace the entire file** with the updated version below. Key changes:
- Add Wiki directory structure
- Replace "At Task Start (READ)" with Query protocol
- Replace "At Task End (WRITE)" with Ingest protocol
- Add Lint section
- Keep backward-compatible references to shared files

```markdown
# Skill: Memory Manager — Wiki-Based Knowledge Management

## Purpose
Enable agents to persist and retrieve knowledge across chat sessions using the
LLM Wiki (`docs/memory/wiki/`). The wiki uses entity pages (one page per system
component) instead of chronological logs, making knowledge queryable and maintainable.

## When to Use
- At TASK START: **Query** — read index, drill into relevant entity pages
- At TASK END: **Ingest** — update affected entity/concept pages, append to log
- Periodically: **Lint** — check wiki health (see skill-wiki-lint.md)

## Directory Structure

docs/memory/
├── wiki/                          # LLM-maintained knowledge base
│   ├── index.md                   # Content catalog — READ FIRST
│   ├── log.md                     # Chronological append-only record
│   ├── entities/                  # One page per system component
│   │   ├── {entity-name}.md       # Entity page (see template below)
│   │   └── ...
│   └── concepts/                  # Cross-cutting patterns and lessons
│       ├── {concept-name}.md      # Concept page (see template below)
│       └── ...
├── shared/                        # Cross-cutting shared files (legacy, still maintained)
│   ├── decisionLog.md             # Chronological decision record
│   ├── lessonsLearned.md          # Chronological lesson record
│   └── systemPatterns.md          # Pattern catalog
└── tasks/
    └── default/
        ├── activeContext.md       # Slim pointer: current focus + 3 recent changes
        └── progress.md            # Current sprint only

## Entity Page Template

# {Entity Name}

> One-sentence summary.

**Status:** Active | Deprecated | Planned
**Owner files:** `path/to/file.py`
**Config:** `config.yaml` → `section.key`
**Added:** YYYY-MM-DD
**Last updated:** YYYY-MM-DD

## Overview
## Architecture
## Current State
## Configuration
## Key Files
## History
## Related

## Concept Page Template

# {Concept Name}

> One-sentence description.

**Applies to:** [Entity A](../entities/a.md), [Entity B](../entities/b.md)
**Learned:** YYYY-MM-DD

## Pattern
## Rules
## Examples
## Related

## Query Protocol (Task Start)

1. Read `docs/memory/wiki/index.md` — scan the entity table to find pages relevant to your task
2. Read only the relevant entity pages (typically 1-3 pages, not all 16+)
3. If the task involves a cross-cutting concern, read the relevant concept page
4. Read `docs/memory/tasks/default/activeContext.md` for current focus and action items
5. If you need historical context, check `docs/memory/wiki/log.md`

**Key principle:** Read selectively. The index tells you what exists — you don't need to read everything.

## Ingest Protocol (Task End)

Only Code, Architect, and UX Designer modes perform Ingest. Debug and Ask are exempt.

1. **Identify affected entities** — which entity pages need updating based on what changed
2. **Update entity pages** — modify the relevant sections (Overview, Current State, History)
   - Update the `**Last updated:**` date
   - Add a History entry linking to the log
   - Update Current State with new information
3. **Update concept pages** — if a cross-cutting pattern was learned or changed
4. **Append to log.md** — add a new entry at the top with:
   - Title, Result, Entities updated, Summary, Files changed
5. **Update index.md** — refresh "Last Updated" dates for modified entity pages
6. **Update activeContext.md** — keep only the 3 most recent changes; update Current Focus if needed
7. **Update progress.md** — mark completed items, add new planned items

### Ingest Rules
- Entity pages are UPDATED, not appended — rewrite sections with current truth
- Log entries are APPENDED (newest first) — never modify old entries
- Index is REFRESHED — update dates, add new entities/concepts
- activeContext.md stays under 30 lines — it's a pointer, not a journal
- If a new entity emerges (new scraper, new UI component), create a new entity page

## Shared Files (Legacy)

The shared files (`decisionLog.md`, `lessonsLearned.md`, `systemPatterns.md`) are still
maintained as chronological records. When making a key decision, append to `decisionLog.md`.
When learning a lesson, append to `lessonsLearned.md`. These serve as the "raw source"
for concept pages — the concept page is the synthesized, queryable version.

## Rules
- ALWAYS Query before starting work (prevents redoing completed work)
- ALWAYS Ingest before ending a session (prevents losing context)
- Entity pages reflect CURRENT TRUTH — not historical narrative
- Log entries are immutable — never edit old entries
- Keep activeContext.md under 30 lines
- Use simple markdown links: `[text](relative/path.md)` — not Obsidian wiki-links
- If wiki contradicts current file state, trust the files (wiki may be stale)
- New entities get their own page — don't cram multiple entities into one page
```

### 7.3 Changes to [`.roomodes`](.roomodes) — Orchestrator `customInstructions`

**Add after the existing `WORKFLOW SEQUENCING RULES:` block (after line 55):**

```yaml
      WIKI SYNC: After the Code→Review cycle completes (approved, no P1/P2), perform wiki sync:
      1. Read the Code mode's completion message for the list of affected entities
      2. Update the affected entity pages in docs/memory/wiki/entities/
      3. Append an entry to docs/memory/wiki/log.md
      4. Update "Last Updated" dates in docs/memory/wiki/index.md
      5. Update docs/memory/tasks/default/activeContext.md (keep only 3 most recent changes)
      If the wiki sync is complex (many entities, new concepts), delegate to Architect mode via new_task.
```

### 7.4 Changes to [`.roomodes`](.roomodes) — Code mode `customInstructions`

**Add after the existing `MANDATORY REVIEW RULE:` block (after line 188):**

```yaml
      WIKI ENTITY REPORTING: In your completion message, always include a "Wiki Entities Affected" section listing which entity pages need updating. Format:
      **Wiki Entities Affected:** zillow-scraper, orchestrator, database-schema
      This helps the Orchestrator perform wiki sync after the review cycle.
```

### 7.5 Changes to [`.roomodes`](.roomodes) — Architect mode `customInstructions`

**Add after the existing `OUTPUT:` line (after line 225):**

```yaml
      WIKI ENTITY IDENTIFICATION: When creating architecture plans, identify which wiki entities are affected or newly created. Include a "Wiki Impact" section in your plan output:
      ## Wiki Impact
      - **New entities:** {list of new entity pages to create}
      - **Updated entities:** {list of existing entity pages to update}
      - **New concepts:** {list of new concept pages, if any}
```

### 7.6 Changes to [`.roomodes`](.roomodes) — UX Designer `customInstructions`

**Add after the existing `ACCESSIBILITY:` line (after line 152):**

```yaml
      WIKI ENTITY REPORTING: In your completion message, include which wiki entity pages are affected by your design work. Format:
      **Wiki Entities Affected:** filter-bar, listing-card, map-view
```

### 7.7 Changes to [`AGENTS.md`](../AGENTS.md) — Pre-flight Checklist

**Replace step 1 (line 15):**

**Current:**
```markdown
1. **Read memory files** — [`docs/memory/tasks/<task-name>/activeContext.md`](docs/memory/tasks/default/activeContext.md) and [`progress.md`](docs/memory/tasks/default/progress.md)
```

**New:**
```markdown
1. **Query the wiki** — Read [`docs/memory/wiki/index.md`](docs/memory/wiki/index.md), then drill into relevant entity pages. Also read [`activeContext.md`](docs/memory/tasks/default/activeContext.md) for current focus.
```

---

## 8. Phase 2: Lint Operation (~30m)

### 8.1 Create [`.roo/skill-wiki-lint.md`](.roo/skill-wiki-lint.md)

```markdown
# Skill: Wiki Lint — Knowledge Base Health Check

## Purpose
Periodic health check of the LLM Wiki to detect contradictions, stale pages,
orphans, and missing cross-references. Keeps the wiki accurate and navigable.

## When to Run
- **Manual trigger:** User says "/wiki-lint" or "lint the wiki"
- **Suggested cadence:** Every ~10 completed tasks, or when an agent notices
  inconsistencies during a Query

## Lint Checks

### L1: Stale Pages (WARNING)
- Compare each entity page's `**Last updated:**` date against `wiki/log.md`
- If an entity page hasn't been updated in 14+ days but `log.md` mentions it
  in recent entries → the page is stale and needs refresh
- **Fix:** Update the entity page with current state from the codebase

### L2: Orphan Pages (WARNING)
- Check that every page in `entities/` and `concepts/` is listed in `index.md`
- Check that every entry in `index.md` has a corresponding file
- **Fix:** Add missing entries to index, or delete orphan pages

### L3: Broken Links (ERROR)
- Scan all wiki markdown files for `[text](path)` links
- Verify each linked file exists
- **Fix:** Update or remove broken links

### L4: Missing Cross-References (INFO)
- For each entity page, check that its "Related" section links to entities
  it interacts with (based on "Owner files" overlap or shared config sections)
- **Fix:** Add missing cross-references

### L5: Contradictions (ERROR)
- Compare entity page "Current State" against actual codebase:
  - Does the entity page say a feature is "Planned" but it's already implemented?
  - Does the entity page reference a file that no longer exists?
  - Does the config section match actual `config.yaml` values?
- **Fix:** Update entity page to match codebase truth

### L6: Index Freshness (WARNING)
- Compare `index.md` "Last Updated" dates against entity page `**Last updated:**` dates
- If they disagree → index is stale
- **Fix:** Refresh index dates

### L7: Log Completeness (INFO)
- Check that recent git commits (last 7 days) have corresponding `log.md` entries
- **Fix:** Add missing log entries

### L8: activeContext.md Size (WARNING)
- If `activeContext.md` exceeds 30 lines → it's growing back into a journal
- **Fix:** Trim to pointer format (current focus + 3 recent changes + links)

## Output Format

After running lint, produce a report:

# Wiki Lint Report — YYYY-MM-DD

## Summary
- Errors: N
- Warnings: N
- Info: N

## Findings

### ❌ L5: Contradiction — scheduler-launchd.md
- Page says "APScheduler still active as fallback"
- Reality: APScheduler fully removed in 2026-04-06
- **Fix:** Update Current State section

### ⚠️ L1: Stale — geocoder.md
- Last updated: 2026-03-27 (10 days ago)
- Recent log entries mention geocoder changes
- **Fix:** Review and refresh

### ℹ️ L4: Missing cross-reference — realtor-scraper.md
- Does not link to deduplication.md (but shares orchestrator pipeline)
- **Fix:** Add to Related section

## How to Trigger

Tell any agent: "Run wiki lint" or "/wiki-lint"

The agent should:
1. Read all files in `docs/memory/wiki/`
2. Run each check (L1-L8)
3. Produce the report in the chat
4. Optionally fix issues directly (if in a mode with edit permissions)
```

### 8.2 Register the Lint Skill

**Add to [`AGENTS.md`](../AGENTS.md) Orchestrator row in the Active Roles table:**

Add `skill-wiki-lint` to the Orchestrator's Key Skills column.

**Add to [`.roomodes`](.roomodes) Orchestrator `customInstructions`:**

```yaml
      WIKI LINT: When the user says "/wiki-lint" or "lint the wiki", run the checks defined in .roo/skill-wiki-lint.md. Produce a lint report and fix any issues you can (you can edit .md files).
```

---

## 9. Migration Checklist

Execute in order. Each step should be a separate task delegated to Code mode (since it involves creating files).

- [ ] **M1:** Create directory structure (`docs/memory/wiki/entities/`, `docs/memory/wiki/concepts/`)
- [ ] **M2:** Create entity page template as a reference file
- [ ] **M3:** Create all 16 entity pages by extracting from existing memory files
- [ ] **M4:** Create all 10 concept pages by extracting from existing memory files
- [ ] **M5:** Create [`wiki/index.md`](../docs/memory/wiki/index.md) with full catalog
- [ ] **M6:** Create [`wiki/log.md`](../docs/memory/wiki/log.md) by migrating history from [`progress.md`](../docs/memory/tasks/default/progress.md)
- [ ] **M7:** Slim [`activeContext.md`](../docs/memory/tasks/default/activeContext.md) to ~20 lines (pointer format)
- [ ] **M8:** Slim [`progress.md`](../docs/memory/tasks/default/progress.md) to current sprint only
- [ ] **M9:** Update [`.roo/skill-memory-manager.md`](.roo/skill-memory-manager.md) with new Query/Ingest/Lint protocols
- [ ] **M10:** Update [`AGENTS.md`](../AGENTS.md) §1 Memory Protocol + add §7 Wiki Sync + update Pre-flight
- [ ] **M11:** Update [`.roomodes`](.roomodes) — Orchestrator, Code, Architect, UX Designer `customInstructions`
- [ ] **M12:** Create [`.roo/skill-wiki-lint.md`](.roo/skill-wiki-lint.md)
- [ ] **M13:** Run initial wiki lint to verify health
- [ ] **M14:** Test Query protocol — start a new task and verify agents read wiki correctly

### Rollback Plan

If the wiki approach doesn't work well after 1 week of use:
1. The old memory files are NOT deleted — `shared/decisionLog.md`, `shared/lessonsLearned.md`, `shared/systemPatterns.md` remain intact
2. `activeContext.md` and `progress.md` history is preserved in `wiki/log.md`
3. Revert [`.roo/skill-memory-manager.md`](.roo/skill-memory-manager.md) to the pre-wiki version (git history)
4. Revert [`AGENTS.md`](../AGENTS.md) and [`.roomodes`](.roomodes) changes (git history)

---

## 10. Open Questions for Owner

### 10.1 Shared Files: Keep or Decompose?

Should [`decisionLog.md`](../docs/memory/shared/decisionLog.md), [`lessonsLearned.md`](../docs/memory/shared/lessonsLearned.md), and [`systemPatterns.md`](../docs/memory/shared/systemPatterns.md) be:

**Option A (recommended): Keep as-is** — They serve as chronological "raw sources" that feed concept pages. Concept pages are the synthesized, queryable version. Keeping both provides redundancy and a chronological audit trail.

**Option B: Decompose into entity/concept pages** — Stop maintaining the shared files entirely. All new decisions go directly into entity pages. Risk: lose the chronological narrative that's useful for understanding "why" decisions were made.

### 10.2 Plans Directory: Index or Separate?

Should the 17 files in [`plans/`](../plans/) be indexed in [`wiki/index.md`](../docs/memory/wiki/index.md)?

**Option A (recommended): Add a "Plans" section to index.md** — Lists all plan files with status (IMPLEMENTED, PLANNED, SUPERSEDED). Makes plans discoverable through the wiki.

**Option B: Keep separate** — Plans are "raw sources" (Layer 1) and shouldn't be in the wiki index (Layer 2). Agents already know to look in `plans/`.

### 10.3 Lint Cadence

How often should wiki lint run?

**Option A: On-demand only** — User triggers with "/wiki-lint" when they notice issues. Lowest overhead.

**Option B (recommended): Every ~10 tasks** — Orchestrator tracks a task counter and suggests lint when it reaches 10. Catches drift before it compounds.

**Option C: Weekly** — Scheduled lint regardless of activity. May be wasteful during slow periods.

### 10.4 Entity Granularity

The proposed 16 entities match the current system components. As the project grows:

- Should new UI components (e.g., a future "Saved Searches" feature) get their own entity page?
- Or should they be subsections of existing pages (e.g., added to `filter-bar.md`)?

**Recommendation:** New features that have their own files, config, and lifecycle get their own entity page. Minor UI tweaks go into existing pages.

---

## 11. Success Metrics

After 2 weeks of wiki usage, evaluate:

| Metric | Current State | Target |
|--------|--------------|--------|
| Lines read at task start | ~1,000+ (all memory files) | ~50-100 (index + 1-2 entity pages) |
| Time to find "what do we know about X?" | Scan 4+ files manually | Read 1 entity page |
| `activeContext.md` size | 436 lines | <30 lines |
| `progress.md` size | 341 lines | <40 lines |
| Knowledge about entity X in one place | Scattered across 4+ files | 1 entity page |
| Stale/contradictory information | Unknown (no lint) | Detected by lint |

---

*This plan is documentation only — no production code. Implementation should be delegated to Code mode via the Orchestrator.*
