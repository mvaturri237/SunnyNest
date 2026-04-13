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
