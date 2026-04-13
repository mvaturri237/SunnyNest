# Deduplication

> Cross-source deduplication system using multi-signal scoring to detect and merge duplicate listings from different sources (Zillow, Craigslist, Realtor.com).

**Status:** Active  
**Owner files:** `src/dedup.py`, `src/database.py`, `src/models.py`  
**Config:** N/A (threshold hardcoded at ≥75)
**Added:** 2026-03-28
**Last updated:** 2026-04-06

## Overview

The deduplication system solves the problem of the same physical property appearing on multiple listing sources with different `external_id` values. It uses a `listing_sources` table (1:N relationship from `listings`) to track which sources have seen each listing, and a multi-signal scoring algorithm to detect cross-source duplicates.

When a duplicate is detected, the existing listing is kept as canonical — the new duplicate's source record is added, NULL fields are gap-filled, and the duplicate row is deleted.

## Architecture

- **Schema:** `listing_sources` table with `(source, external_id)` unique constraint, FK to `listings`
- **Scoring algorithm:** Multi-signal with weighted components:
  - Normalized address match: 40 points
  - ZIP code match: 10 points
  - Price within 5%: 15 points
  - Bedrooms match: 15 points
  - Bathrooms match: 10 points
  - Sqft within 10%: 10 points
  - **Threshold:** ≥75 = duplicate
- **Address normalization:** Lowercase, strip trailing city/state, remove periods, collapse whitespace, map street type abbreviations (Drive→dr), map directionals (North→n), remove unit/apt designators
- **Candidate narrowing:** Filter by `zip_code` only before scoring to avoid O(N²). Composite index `ix_listings_dedup_candidates` on `(zip_code, is_active)`. Bedrooms comparison is handled in the scoring function (15 points), not as a hard pre-filter — this allows detecting duplicates even when sources report different bedroom counts.
- **Merge strategy:** Existing listing is canonical. Gap-fill NULL fields from duplicate. Merge image URLs (union). Transfer `price_history` records. Never overwrite user preferences (favorites, dislikes)
- **Pipeline position:** Step 6 in [Orchestrator](orchestrator.md) — after upsert, only for newly inserted listings
- **Error isolation:** Dedup failures are caught independently — listing is kept even if dedup fails

## Current State

- **Working:** Fully operational with 3 sources (Zillow, Craigslist, Realtor.com)
- **Performance:** Candidate narrowing via ZIP-only index keeps dedup < 100ms per run. Candidate pool is ~8-12 per ZIP at current scale.
- **Migration:** `_migrate_to_listing_sources()` backfilled 23 existing Zillow listings idempotently
- **Re-insert prevention:** `upsert_listing()` checks `listing_sources` table for previously merged listings

## Key Files

| File | Purpose |
|------|---------|
| `src/dedup.py` | `normalize_address()`, `compute_duplicate_score()`, `find_and_merge_duplicate()` |
| `src/models.py` | `ListingSource` model with FK to `Listing` |
| `src/database.py` | `upsert_listing()` with source tracking, `_migrate_to_listing_sources()` |
| `src/orchestrator.py` | Dedup call in pipeline step 6 |

## History

- [2026-04-06] APPROVED (0 P1, 0 P2) — Relaxed candidate narrowing from `zip_code + bedrooms` to `zip_code` only. Fixed bug where cross-source duplicates with different bedroom counts were missed. Merged existing duplicate (370 Cypress Ave: Craigslist listing 107 → Zillow listing 111). Updated index from `(zip_code, bedrooms, is_active)` to `(zip_code, is_active)`.
- [2026-03-28] Re-review APPROVED — 0 P1, 0 P2 remaining after fix cycle
- [2026-03-28] Code review fixes: price_history transfer, defensive existence check, IntegrityError handling, INSERT OR IGNORE migration
- [2026-03-28] Initial implementation (Phases 1-4 of rollout plan)
- [2026-03-28] Architecture plan created (`plans/deduplication.md`)

## Related

- [Orchestrator](orchestrator.md) — calls dedup as pipeline step 6
- [Database Schema](database-schema.md) — `listing_sources` table, `ix_listings_dedup_candidates` index
- [Zillow Scraper](zillow-scraper.md), [Craigslist Scraper](craigslist-scraper.md), [Realtor Scraper](realtor-scraper.md) — data sources
- [Upsert Exclusion Pattern](../concepts/upsert-exclusion-pattern.md) — user-managed flags excluded from updates
- [Plan: Deduplication](../../../../plans/deduplication.md) — architecture plan
