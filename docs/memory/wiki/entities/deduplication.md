# Deduplication

> Cross-source deduplication system using multi-signal scoring to detect and merge duplicate listings from different sources (Zillow, Craigslist, Realtor.com).

**Status:** Active  
**Owner files:** `src/dedup.py`, `src/database.py`, `src/models.py`  
**Config:** N/A (threshold hardcoded at ≥75)
**Added:** 2026-03-28
**Last updated:** 2026-05-08

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

- **Working:** Fully operational with 3 sources (Zillow, Craigslist, Realtor.com) — verified end-to-end after the 2026-05-08 IntegrityError fix.
- **Performance:** Candidate narrowing via ZIP-only index keeps dedup < 100ms per run. Candidate pool is ~8-12 per ZIP at current scale.
- **Migration:** `_migrate_to_listing_sources()` backfilled 23 existing Zillow listings idempotently
- **Re-insert prevention:** `upsert_listing()` checks `listing_sources` table for previously merged listings
- **Critical invariant:** `_merge_duplicate()` must NOT INSERT a new `ListingSource` row — it would collide with the row `upsert_listing()` already created on the duplicate listing (`uq_ls_source_external_id` UNIQUE constraint). Instead, it queries the existing row by `(source, external_id)` and reassigns `listing_id` to the canonical. A defensive fallback creates a new row only when none exists (backfill / out-of-band path).
- **Loud-failure semantics:** any `IntegrityError` during merge is logged via `logger.exception(...)` with the full traceback, NOT as a `WARNING` "possible race condition" (the old wording masked the IntegrityError bug for ~6 weeks).
- **Backfill tool:** [`scripts/backfill_dedup.py`](../../../../scripts/backfill_dedup.py) — one-shot retroactive merger for clusters left behind by historical bugs. Default `--dry-run`; `--apply` to commit. **One transaction per merge** (not per cluster) — partial cluster failures recover via idempotent re-run.

## Key Files

| File | Purpose |
|------|---------|
| `src/dedup.py` | `normalize_address()`, `compute_duplicate_score()`, `find_and_merge_duplicate()`, `_merge_duplicate()` (reassigns existing `ListingSource` instead of INSERTing) |
| `src/models.py` | `ListingSource` model with FK to `Listing` |
| `src/database.py` | `upsert_listing()` with source tracking, `_migrate_to_listing_sources()` |
| `src/orchestrator.py` | Dedup call in pipeline step 6 |
| `scripts/backfill_dedup.py` | One-shot retroactive merger for historical unmerged clusters; `--dry-run` default |
| `scripts/test_dedup_merge.py` | Reproducer tests for the IntegrityError bug + no-match sanity |

## History

- [2026-05-08] **APPROVED (P2-only fix shipped; P3s deferred)** — Fixed the cross-source dedup `IntegrityError` silent-no-op bug. Root cause: `_merge_duplicate()` was INSERTing a new `ListingSource(source, external_id)` row that collided with the row `upsert_listing()` had just created → `uq_ls_source_external_id` UNIQUE violation → broad `except IntegrityError` swallowed it as a fake "race condition" → **zero cross-source merges occurred for ~6 weeks** despite the algorithm correctly *detecting* duplicates (scores 90–100). Fix: query-then-reassign existing row in `_merge_duplicate()` ([`src/dedup.py:254-275`](../../../../src/dedup.py:254)); `session.flush()` + `session.refresh(dup)` before the defensive `dup.sources` deletion loop ([`src/dedup.py:430-435`](../../../../src/dedup.py:430)); replaced misleading `logger.warning("…possible race condition")` with `logger.exception("…investigate")` ([`src/dedup.py:437-448`](../../../../src/dedup.py:437)). New reproducer test ([`scripts/test_dedup_merge.py`](../../../../scripts/test_dedup_merge.py)) — 2/2 passing. New backfill script ([`scripts/backfill_dedup.py`](../../../../scripts/backfill_dedup.py)) — dry-run identified **6 clusters / 8 unmerged rows** in production (Ormsby Dr ×3 sources, Hollenbeck Ave ×3, Timberpine Ct, Fair Oaks Ave, Santa Rosa St, San Simeon St). Triggered by user-reported "dedup isn't working" screenshot showing 1426 Ormsby Dr appearing as 3 separate cards. **Follow-ups deferred:** cascade-interaction hardening (`assert not dup.sources` + comment), additional tests (3-way merge, defensive fallback, IntegrityError regression, image_urls/price_history merge), canonical-picker rule (earliest `first_seen` may pick leaner record over richer Zillow), 3 minor nits in backfill script.
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
