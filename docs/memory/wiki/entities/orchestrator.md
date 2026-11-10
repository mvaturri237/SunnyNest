# Orchestrator

> Coordinates the full scrape→normalize→geocode→enrich→upsert→dedup pipeline, running all scrapers concurrently and processing results through a standardized enrichment chain.

**Status:** Active  
**Owner files:** `src/orchestrator.py`  
**Config:** `config.yaml` → `search`, `filters`, `scraper`  
**Added:** 2026-03-27  
**Last updated:** 2026-06-04

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
  2. Normalize (per-source via `BaseScraper.normalize() -> dict | None`; **`None` return = skip**, e.g. [Zillow Scraper](zillow-scraper.md) Bug A status guard; counted by per-source `normalize_filtered` debug log)
  3. Filter (house-only — skip non-house `property_type`)
  4. Filter (price — skip `None`/`0`/`0.0` prices)
  5. Geocode via [Geocoder](geocoder.md) (Nominatim + LRU cache + circuit breaker)
  6. School assignment via [School Districts](school-districts.md) (step 3b — point-in-polygon)
  7. Sqm conversion (sqft → m²)
  8. Upsert to database
  9. Dedup via [Deduplication](deduplication.md) (only for newly inserted listings)
  10. Price snapshot recording
- **Error isolation:** Each scraper failure is caught independently — other sources continue
- **Mark inactive (two-layer hysteresis, 2026-06-04):** After processing, [`mark_inactive()`](../../../src/database.py:824) increments a `consecutive_misses` counter for listings absent from the current scrape and resets it for listings present. A listing is only flipped `is_active=False` when its counter reaches `MARK_INACTIVE_MISS_THRESHOLD = 3` (≈ 3 daily scrapes). The legacy 30% safety threshold ([`src/orchestrator.py:225-249`](../../../src/orchestrator.py:225)) and `if seen_external_ids:` guard ([`src/orchestrator.py:245`](../../../src/orchestrator.py:245)) remain as defense-in-depth against fully-failed scrapes — see ZILLOW-STALE-P3-1 for cleanup proposal. This pattern hardens against flaky upstream APIs (e.g., the RapidAPI Zillow provider whose index returns a given zpid intermittently).

## Current State

- **Working:** Fully operational with 3 registered scrapers (Zillow, Craigslist, Realtor.com)
- **Trigger:** Daily via launchd (`scripts/run-scraper.py`) + manual via admin sync button
- **Safety:** `mark_inactive()` (a) requires seeing ≥30% of active listings before deactivating unseen ones (outer guard, legacy), AND (b) only flips a listing inactive after `consecutive_misses >= 3` (inner hysteresis counter, 2026-06-04 — see "Mark inactive" in Architecture above).
- **Deprecated `Query.get()`:** All instances replaced with `session.get(Listing, id)` (SQLAlchemy 2.0)

## Key Files

| File | Purpose |
|------|---------|
| `src/orchestrator.py` | Main orchestrator implementation |
| `scripts/run-scraper.py` | Standalone script for launchd execution |
| `config.yaml` → `search`, `filters` | Search parameters and filter criteria |

## History

- [2026-06-04] **Two-layer hysteresis added to `mark_inactive()` (Bug B) + `None` skip handling for `normalize()` (Bug A coordination).** New `consecutive_misses` counter increments per absent scrape, resets on present, deactivates only at threshold `N=3`. Closes a flaky-upstream class of bug where the RapidAPI Zillow provider's index occasionally re-includes a stale zpid in one of N daily scrapes, keeping it permanently "active". Per-source `normalize_filtered` debug log surfaces how many items the scraper's defensive validators rejected per scrape. 15/15 new tests green; reviewer ✅ APPROVED 0 P1/P2, 4 P3s. See [log entry](../log.md#zillow-stale-for-sale-rental-bug-bug-a--bug-b--approved-4-p3s--backlog).
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
