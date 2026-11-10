# Database Schema

> SQLite database with 5 tables storing listings, price history, source tracking, API call logs, and notification records, using SQLAlchemy ORM with manual migrations.

**Status:** Active  
**Owner files:** `src/database.py`, `src/models.py`  
**Config:** `data/listings.db` (SQLite file)  
**Added:** 2026-03-27  
**Last updated:** 2026-06-04

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
| `listings` | Core listing data | `id`, `source`, `external_id`, `address`, `price`, `bedrooms`, `bathrooms`, `sqft`, `lat`, `lng`, `school_elementary`, `school_middle`, `school_high`, `is_active`, `is_favorite`, `is_disliked`, `notified`, `days_on_market`, `deactivated_at`, `consecutive_misses` (NEW 2026-06-04 — hysteresis counter for `mark_inactive()`; reset on present, incremented on absent, deactivates at `MARK_INACTIVE_MISS_THRESHOLD = 3`) |
| `listing_sources` | Multi-source tracking (1:N from listings) | `id`, `listing_id` (FK), `source`, `external_id`, `url`, `is_active`, `first_seen`, `last_seen`. **`UNIQUE (source, external_id)` constraint (`uq_ls_source_external_id`)** — see "Constraint interactions" below. |
| `price_history` | Daily price snapshots | `id`, `listing_id` (FK), `price`, `date` |
| `api_call_log` | API budget tracking | `id`, `service`, `endpoint`, `status_code`, `timestamp` |
| `notification_log` | Notification dispatch records (any channel) | `id`, `channel`, `sent_at`, `listing_count`, `recipient`, `success`, `error_category`, `error_message` |

### Indexes

- `ix_listings_dedup_candidates` on `(zip_code, is_active)` — dedup candidate narrowing (bedrooms removed from index — comparison moved to scoring phase)
- Standard indexes on FKs and frequently queried columns

### Constraint interactions

- **`uq_ls_source_external_id` ↔ Deduplication merge** (lesson learned 2026-05-08): The `UNIQUE (source, external_id)` constraint on `listing_sources` means **at most one row exists per `(source, external_id)` pair** at any time. Any code path that wants to "attach this source to a different listing" must **reassign the existing row's `listing_id`** — NOT INSERT a second row. The naive INSERT path always raises `IntegrityError`. See [`src/dedup.py:254-275`](../../../src/dedup.py:254) `_merge_duplicate()` for the canonical query-then-reassign-or-fallback pattern. The same rule applies to any future feature that reassigns source records (e.g., manual dedup tools, listing-merge UI, source migration).

### Key Query Functions

- `get_filtered_listings()` — main dashboard query with eager-loaded sources
- `get_source_counts()` — SQL GROUP BY on `listing_sources` table
- `get_listing_stats()` — SQL aggregates for KPIs
- `get_unnotified_listings()` — config-filtered unnotified listings
- `get_today_notification_count()` — counts **successful** sends (`success=True`) for "today" via a UTC-bounded window translated from IST midnight (gates the anti-spam ceiling; inverted 2026-06-03 from the prior "count all attempts" semantics). See "Naive-UTC storage" note below.
- `get_last_successful_notification_at()` — most recent `sent_at` where `success=True`, used by the dashboard silence-detector
- `get_notification_stats()` — admin-page tile: counts ALL today's attempts (success + failure) — **intentionally decoupled** from `get_today_notification_count()` because admin visibility ≠ rate-limit gate
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

### Naive-UTC storage convention (notification_log.sent_at and similar)

`NotificationLog.sent_at` and `Listing.first_seen` are written with `default=lambda: datetime.now(timezone.utc)` (tz-aware UTC) but SQLite **drops the tzinfo on persist** — values come back as naive datetimes whose semantics are UTC. Any "today"-style query against these columns MUST translate the user-facing IST "today" to a UTC half-open window `[start_utc, end_utc)` before comparing — using `func.date(sent_at) == today` compares the **UTC date**, which disagrees with the IST date during the IST 00:00–03:00 window (= UTC 21:00–00:00 the previous day). [`get_today_notification_count()`](../../../src/database.py:1463) shows the canonical pattern; [`get_notification_stats()`](../../../src/database.py:1709) has the same hazard pending P3 sweep (NOTIF-P3-2 in [`p3-backlog.md`](../../p3-backlog.md), tagged `[hardens-against-this-bug-class]`).

## Key Files

| File | Purpose |
|------|---------|
| `src/models.py` | `Listing`, `ListingSource`, `PriceHistory` SQLAlchemy models |
| `src/database.py` | All DB operations, migrations, query functions |
| `data/listings.db` | SQLite database file |

## History

- [2026-06-04] **`consecutive_misses` column added to `listings` (lifecycle hysteresis for `mark_inactive()`).** New `_ensure_consecutive_misses_column()` migration in [`init_db()`](../../../src/database.py:205) idempotently adds `consecutive_misses INTEGER NOT NULL DEFAULT 0`. All 278 pre-existing rows backfilled to 0. Column added to **both** upsert exclusion tuples ([`database.py:442`](../../../src/database.py:442), [`database.py:501`](../../../src/database.py:501)) so scrapers cannot clobber it — see [Upsert Exclusion Pattern](../concepts/upsert-exclusion-pattern.md). [`mark_inactive()`](../../../src/database.py:824) rewritten: Step 1 resets counter for listings present in the scrape, Step 2 increments counter for absent listings (cross-source isolated), Step 3 flips `is_active=False` + sets `deactivated_at` only for listings whose counter reaches `MARK_INACTIVE_MISS_THRESHOLD = 3` (≈ 3 daily scrapes for flaky upstreams). `ListingSource.is_active` mirror only flips on threshold crossing. 15/15 new tests in [`scripts/test_mark_inactive_counter.py`](../../../scripts/test_mark_inactive_counter.py). 4 P3s for backlog (ZILLOW-STALE-P3-1..4). Companion to [Zillow Scraper](zillow-scraper.md) Bug A. See [log entry](../log.md#zillow-stale-for-sale-rental-bug-bug-a--bug-b--approved-4-new-p3s--backlog).
- [2026-06-03] **`get_today_notification_count()` semantics inverted + tz-correctness hardened; new `get_last_successful_notification_at()` helper.** (a) Filter changed from "all rows" to `success == True` only — closes the 2026-06-03 silent-Telegram regression where transient morning failures consumed the daily cap. (b) Comparison switched from `func.date(sent_at) == today` (UTC-day compare) to `sent_at >= start_utc AND sent_at < end_utc` where bounds are translated from IST midnight. Eliminates a near-midnight off-by-one and removes a docstring claim that previously overpromised tz-awareness. (c) New `get_last_successful_notification_at()` helper powers the dashboard silence-detector banner. Regression test: [`scripts/test_anti_spam_guard.py:test_ist_day_boundary_not_utc_day`](../../../scripts/test_anti_spam_guard.py:155). `get_notification_stats()` deliberately retains "count all attempts" semantics for the admin "Notifications Today" tile — its same-shape `func.date()` UTC-day bug is logged as P3 NOTIF-P3-2 (tagged `[hardens-against-this-bug-class]`).
- [2026-05-08] **Documented `uq_ls_source_external_id` ↔ dedup interaction** — added "Constraint interactions" section after a 6-week silent dedup bug ([`deduplication.md`](deduplication.md)) was traced to `_merge_duplicate()` doing INSERT instead of query-then-reassign. No schema change; the constraint itself is correct. The fix was in [`src/dedup.py`](../../../src/dedup.py).
- [2026-05-08] `notification_log` extended with `error_category TEXT` and `error_message TEXT` columns (additive migration `_ensure_notification_error_columns`). Failed sends are now classified (`token_expired`, `auth`, `rate_limited`, etc.) so the admin UI can surface specific warnings. New `get_last_channel_failure()` helper returns the most recent failure for a channel within a lookback window.
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
