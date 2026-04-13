# Database Schema

> SQLite database with 5 tables storing listings, price history, source tracking, API call logs, and notification records, using SQLAlchemy ORM with manual migrations.

**Status:** Active  
**Owner files:** `src/database.py`, `src/models.py`  
**Config:** `data/listings.db` (SQLite file)  
**Added:** 2026-03-27  
**Last updated:** 2026-04-06

## Overview

The database is a single SQLite file (`data/listings.db`) accessed via SQLAlchemy ORM. It stores all listing data, price history, source tracking for deduplication, API call logs for budget monitoring, and notification records. Schema migrations are manual (`ALTER TABLE ADD COLUMN` with try/except for idempotency) — no Alembic, as the 5-table schema changes infrequently.

## Architecture

- **ORM:** SQLAlchemy with `declarative_base()`, session management via `get_session()` context manager
- **Thread safety:** `check_same_thread=False` for SQLite (sufficient for single-user app)
- **Migrations:** Manual `ALTER TABLE ADD COLUMN` in `init_db()` with try/except for idempotency
- **Key patterns:**
  - `upsert_listing()` — insert or update with exclusion tuples for user-managed fields (see [Upsert Exclusion Pattern](../concepts/upsert-exclusion-pattern.md))
  - `_apply_listing_filters()` — shared DRY helper for applying config filters to any query
  - SQL aggregates for stats queries (`func.count()`, `func.avg()`, `GROUP BY`)
  - `selectinload(Listing.sources)` for eager loading of source relationships

## Current State

### Tables

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `listings` | Core listing data | `id`, `source`, `external_id`, `address`, `price`, `bedrooms`, `bathrooms`, `sqft`, `lat`, `lng`, `school_elementary`, `school_middle`, `school_high`, `is_active`, `is_favorite`, `is_disliked`, `notified`, `days_on_market`, `deactivated_at` |
| `listing_sources` | Multi-source tracking (1:N from listings) | `id`, `listing_id` (FK), `source`, `external_id`, `url`, `is_active`, `first_seen`, `last_seen` |
| `price_history` | Daily price snapshots | `id`, `listing_id` (FK), `price`, `date` |
| `api_call_log` | API budget tracking | `id`, `service`, `endpoint`, `status_code`, `timestamp` |
| `notification_log` | Email notification records | `id`, `listing_id`, `sent_at`, `success` |

### Indexes

- `ix_listings_dedup_candidates` on `(zip_code, is_active)` — dedup candidate narrowing (bedrooms removed from index — comparison moved to scoring phase)
- Standard indexes on FKs and frequently queried columns

### Key Query Functions

- `get_filtered_listings()` — main dashboard query with eager-loaded sources
- `get_source_counts()` — SQL GROUP BY on `listing_sources` table
- `get_listing_stats()` — SQL aggregates for KPIs
- `get_unnotified_listings()` — config-filtered unnotified listings
- `get_api_call_count()` — budget tracking per source
- `get_scrape_activity_grid()` — 30-day heatmap data
- `get_api_success_rate_by_day()` — 7-day success rate trend
- `get_api_call_count_for_period()` — monthly comparison data
- `get_lifecycle_stats()` — avg/median/min/max lifespan for inactive listings
- `get_lifecycle_by_bedrooms()` — lifespan breakdown by bedroom count
- `get_lifecycle_by_price_range()` — lifespan breakdown by price bucket

## Configuration

| Setting | Value | Description |
|---------|-------|-------------|
| Database file | `data/listings.db` | SQLite file path |
| Thread safety | `check_same_thread=False` | Required for web server access |
| Migration approach | Manual `ALTER TABLE` | No Alembic — schema changes are infrequent |

## Key Files

| File | Purpose |
|------|---------|
| `src/models.py` | `Listing`, `ListingSource`, `PriceHistory` SQLAlchemy models |
| `src/database.py` | All DB operations, migrations, query functions |
| `data/listings.db` | SQLite database file |

## History

- [2026-04-06] `deactivated_at` column added; `mark_inactive()` sets timestamp on deactivation; `deactivated_at` cleared on re-activation; added to upsert exclusion tuples
- [2026-04-06] `max_days_listed` filter added to `_apply_listing_filters()` — filters by `days_on_market <= X`
- [2026-04-06] Lifecycle analytics functions: `get_lifecycle_stats()`, `get_lifecycle_by_bedrooms()`, `get_lifecycle_by_price_range()`
- [2026-04-06] Dedup index `ix_listings_dedup_candidates` changed from `(zip_code, bedrooms, is_active)` to `(zip_code, is_active)` — bedrooms filter moved to scoring phase
- [2026-04-06] New DB functions: `get_api_success_rate_by_day()`, `get_api_call_count_for_period()` for API Usage page redesign
- [2026-04-06] `get_scrape_activity_grid()` added for admin heatmap
- [2026-03-31] School columns added: `school_elementary`, `school_middle`, `school_high`
- [2026-03-31] `_apply_listing_filters()` DRY helper created, eliminating ~90 lines of duplicated filter logic
- [2026-03-31] `notified`, `is_favorite`, `is_disliked` added to upsert exclusion tuples
- [2026-03-28] `listing_sources` table and `ListingSource` model added for deduplication
- [2026-03-28] Dedup candidate index added
- [2026-03-27] `days_on_market` column added; price history gap-filling with MAX_GAP_DAYS=30
- [2026-03-27] Stats queries rewritten with SQL aggregates (no more full ORM load)
- [2026-03-27] Initial schema

## Related

- [Deduplication](deduplication.md) — uses `listing_sources` table
- [Orchestrator](orchestrator.md) — calls `upsert_listing()` in pipeline
- [Notification System](notification-system.md) — queries `notified` flag
- [API Usage Page](api-usage-page.md) — queries `api_call_log` table
- [Admin Dashboard](admin-dashboard.md) — queries stats functions
- [Upsert Exclusion Pattern](../concepts/upsert-exclusion-pattern.md) — user-managed flags protection
