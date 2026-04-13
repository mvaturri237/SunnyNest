# Orchestrator

> Coordinates the full scrape→normalize→geocode→enrich→upsert→dedup pipeline, running all scrapers concurrently and processing results through a standardized enrichment chain.

**Status:** Active  
**Owner files:** `src/orchestrator.py`  
**Config:** `config.yaml` → `search`, `filters`, `scraper`  
**Added:** 2026-03-27  
**Last updated:** 2026-04-06

## Overview

The `ScraperOrchestrator` is the central coordination point for the data pipeline. It registers all scrapers as `(name, instance)` tuples, runs them concurrently via `asyncio.gather`, and processes each listing through a standardized enrichment chain: normalize → filter (house-only) → geocode → school assignment → sqm conversion → upsert → dedup → price snapshot.

The orchestrator can be triggered in two ways:
1. **Scheduled:** Via launchd plist running `scripts/run-scraper.py` daily at 06:00
2. **Manual:** Via the admin dashboard sync button (`POST /admin/sync`)

## Architecture

- **Scraper registration:** `self._scrapers` list of `(name, instance)` tuples — adding a new source requires only adding one tuple
- **Concurrent execution:** `asyncio.gather(*[s.scrape() for _, s in self._scrapers])` runs all scrapers in parallel
- **Pipeline steps:**
  1. Scrape (concurrent across all sources)
  2. Normalize (per-source via `BaseScraper.normalize()`)
  3. Filter (house-only — skip non-house `property_type`)
  4. Filter (price — skip `None`/`0`/`0.0` prices)
  5. Geocode via [Geocoder](geocoder.md) (Nominatim + LRU cache + circuit breaker)
  6. School assignment via [School Districts](school-districts.md) (step 3b — point-in-polygon)
  7. Sqm conversion (sqft → m²)
  8. Upsert to database
  9. Dedup via [Deduplication](deduplication.md) (only for newly inserted listings)
  10. Price snapshot recording
- **Error isolation:** Each scraper failure is caught independently — other sources continue
- **Mark inactive:** After processing, listings not seen in current run are marked inactive (with 30% safety threshold)

## Current State

- **Working:** Fully operational with 3 registered scrapers (Zillow, Craigslist, Realtor.com)
- **Trigger:** Daily via launchd (`scripts/run-scraper.py`) + manual via admin sync button
- **Safety:** `mark_inactive()` requires seeing ≥30% of active listings before deactivating unseen ones
- **Deprecated `Query.get()`:** All instances replaced with `session.get(Listing, id)` (SQLAlchemy 2.0)

## Key Files

| File | Purpose |
|------|---------|
| `src/orchestrator.py` | Main orchestrator implementation |
| `scripts/run-scraper.py` | Standalone script for launchd execution |
| `config.yaml` → `search`, `filters` | Search parameters and filter criteria |

## History

- [2026-04-06] Scheduler migrated to launchd — orchestrator now invoked via `scripts/run-scraper.py`
- [2026-04-01] Realtor.com scraper registered as third source
- [2026-03-31] School assignment enrichment added as step 3b
- [2026-03-30] Deprecated `Query.get()` replaced with `session.get()`
- [2026-03-28] Deduplication step added (step 6 — after upsert, for new listings only)
- [2026-03-28] Post-normalization filter added to skip non-house property types
- [2026-03-27] Price filter added (skip None/0/0.0 prices)
- [2026-03-27] Initial implementation

## Related

- [Zillow Scraper](zillow-scraper.md) — primary data source
- [Craigslist Scraper](craigslist-scraper.md) — secondary data source
- [Realtor Scraper](realtor-scraper.md) — third data source
- [Geocoder](geocoder.md) — step 5 in pipeline
- [School Districts](school-districts.md) — step 3b in pipeline
- [Deduplication](deduplication.md) — step 9 in pipeline
- [Database Schema](database-schema.md) — upsert target
- [Adapter Pattern](../concepts/adapter-pattern.md) — BaseScraper ABC pattern
