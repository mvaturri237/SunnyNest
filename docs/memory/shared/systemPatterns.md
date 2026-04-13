# System Patterns

## Config-Driven Filtering Pattern
- **Date:** 2026-03-31
- **Context:** Notifications and analytics were showing all 39 active listings instead of the ~10 matching the user's `config.yaml` search criteria
- **Pattern:** `config.yaml` `filters` section (min_price, max_price, min_bedrooms, max_bedrooms, property_types) is the single source of truth for the user's search preferences. All user-facing data views (notifications, analytics) must apply these filters.
- **Implementation:** `_apply_listing_filters(query, filters)` in `src/database.py` is the shared helper that applies filter criteria to any SQLAlchemy query. Used by `get_filtered_listings()`, `get_source_counts()`, and `get_unnotified_listings()`.
- **Key rule:** Non-matching listings stay `notified=False` — if the user broadens their filters later, those listings will appear in the next notification.

## School Boundary Lookup Pattern (Lazy Singleton + Point-in-Polygon)
- **Added:** 2026-03-31
- **Location:** `src/school_districts.py` → `_SchoolBoundaryStore`, `get_assigned_schools()`
- **Pattern:** Load GeoJSON boundary files once via lazy singleton, cache `shapely` geometries, perform point-in-polygon lookups per listing lat/lng. Thread-safe with double-checked locking.
- **Key design decisions:**
  - Guarded `shapely` import (`_HAS_SHAPELY` flag) — module works without shapely, existing `get_school_district()` unaffected
  - Lazy loading: GeoJSON parsed on first call, not at import time
  - Graceful degradation: missing files → log warning, return None for all levels
  - GeoJSON coordinate order: `Point(lng, lat)` matches GeoJSON convention
  - Separate files per school level: `elementary.geojson`, `middle.geojson`, `high.geojson`
- **Enrichment pipeline position:** Step 3b (after geocoding, before sqm conversion)

## Startup Environment Validation Pattern
- **Added:** 2026-03-31
- **Location:** `web/main.py` → `_validate_environment()`, `web/dependencies.py` → `get_env_status()`
- **Pattern:** At FastAPI startup (lifespan), validate all required/recommended env vars and log clear warnings. Provide a runtime `get_env_status()` function for the admin dashboard to show a "System Health" panel with green/red indicators.
- **Key design decisions:**
  - Non-blocking: app starts even with missing vars (warnings only, no crash)
  - Conditional checks: SMTP_PASSWORD only warns when email is enabled in config
  - Dual-layer feedback: startup logs + admin dashboard UI
  - No credential values in logs or templates — only presence/absence

## App Isolation (Dashboard vs Backoffice)
- **Two separate Streamlit apps**: `app.py` (dashboard, port 8501) and `backoffice.py` (admin, port 8502)
- **Shared backend**: Both apps share `src/database.py`, `src/models.py`, and `data/listings.db`
- **Independent UI**: Each app has its own CSS, layout, and Streamlit configuration — changes to one must NOT affect the other
- **Dashboard constraint**: `app.py` hides `stHeader` via CSS for a clean header-only layout. This means `st.sidebar` is architecturally forbidden in `app.py` (the sidebar toggle lives inside `stHeader`)
- **Cross-app navigation**: "Admin →" link in `app.py` uses `st.markdown()` in the main content area (not `st.sidebar`)
- **Backoffice uses sidebar freely**: `backoffice.py` does NOT hide `stHeader`, so it can use `st.sidebar` normally

## Process Management
- **Dashboard hosting**: Streamlit app (`app.py`) served via macOS `launchd` Launch Agent
- **Plist files**: `com.sunnynest.dashboard.plist` (dashboard) and `com.sunnynest.log-rotate.plist` (weekly log rotation)
- **Auto-restart**: `KeepAlive: true` ensures the dashboard restarts after crashes or sleep/wake cycles
- **Log rotation**: Weekly script (`scripts/rotate-logs.sh`) archives logs >50MB and deletes archives >30 days old
- **Binding**: Dashboard binds to `localhost` only (port 8501) for security — no authentication layer exists

## Background Jobs
- **Scrape scheduler**: `src/scheduler.py` uses APScheduler `BackgroundScheduler(daemon=True)` — runs inside the Streamlit process
- **Notification scheduler**: Cron-based via APScheduler at configurable hours (default: 8:00 AM / 8:00 PM Asia/Jerusalem)
- Both schedulers are daemon threads — they die when the Streamlit process exits, so persistent process management (launchd) is essential

## Multi-Source Scraper Pattern (Adapter + Orchestrator)
- **Added:** 2026-04-01
- **Pattern:** All scrapers extend `BaseScraper(ABC)` with `async scrape() -> list[dict]` and `normalize(raw: dict) -> dict`. Registered in `ScraperOrchestrator.__init__` as `(name, instance)` tuples. All run concurrently via `asyncio.gather`.
- **Adding a new source requires:**
  1. Create `src/scrapers/<source>_scraper.py` with `<Source>Scraper(BaseScraper)`
  2. Add `(name, instance)` to `self._scrapers` in `src/orchestrator.py`
  3. Add `<source>_api` section to `config.yaml` with `enabled`, `monthly_budget`, `budget_threshold`
  4. Extend `_validate_environment()` in `web/main.py` and `get_env_status()` in `web/dependencies.py`
  5. Add source to `API_BUDGET_LIMITS` dict in `web/routes/admin.py`
- **Admin UI is source-agnostic:** API Usage page uses `{% for source in sources %}` loop and `_build_budget_data()` helper — zero template changes needed for new sources
- **Source filter auto-populates:** Dashboard source dropdown queries `listing_sources` table with `GROUP BY source` — new sources appear automatically
- **Budget guard pattern:** Each scraper checks `get_api_call_count(source)` against configurable `budget_threshold` before making API calls. Log API calls via `log_api_call(source, endpoint, status_code)` — log AFTER `raise_for_status()` to avoid double-counting on error responses.
- **API key resolution:** Source-specific env var → shared `RAPIDAPI_KEY` fallback → config.yaml fallback

## Security Patterns
- **Secrets management**: API keys and passwords stored in environment variables (RAPIDAPI_KEY, REALTOR_RAPIDAPI_KEY, SMTP_PASSWORD, NOTIFICATION_RECIPIENT), with config.yaml fallback for non-sensitive defaults
- **XSS prevention**: All scraped listing data (titles, URLs, addresses, images) escaped with `html.escape()` before HTML rendering in both card templates and Folium map popups
- **TLS verification**: All HTTP clients use default `verify=True` — never disable certificate verification
- **Bulk operation safety**: `mark_inactive()` requires seeing ≥30% of active listings before deactivating unseen ones

## Performance Patterns
- **SQL aggregates**: Stats queries (`get_source_counts`, `get_listing_stats`) use `func.count()`, `func.avg()`, `GROUP BY` instead of loading ORM objects
- **Geocoder singleton**: Single `Nominatim` instance at module level, reused across all geocode calls
- **Bounded LRU cache**: Geocode cache uses `OrderedDict` with max 1024 entries and LRU eviction
- **Circuit breaker with auto-reset**: Geocoder circuit breaker trips after 3 failures, auto-resets after 30 minutes

## Deduplication Patterns
- **Cross-source dedup**: `listing_sources` table (1:N from listings) stores source/external_id/url per source. Multi-signal scoring algorithm with address normalization, threshold ≥ 75
- **Address normalization**: Lowercase, strip trailing city/state, remove periods, collapse whitespace, map street type abbreviations (Drive→dr), map directionals (North→n), remove unit/apt designators
- **Candidate narrowing**: Filter by zip_code + bedrooms before scoring to avoid O(N²). Composite index `(zip_code, bedrooms, is_active)` recommended
- **Merge strategy**: Existing listing is canonical. Gap-fill NULL fields from duplicate. Merge image URLs (union). Never overwrite user preferences (favorites, dislikes)
- **Pipeline position**: Step 6 in orchestrator — after upsert, before price snapshots. Only runs for newly inserted listings

## Code Quality Patterns
- **Timezone-aware datetimes**: All timestamps use `datetime.now(timezone.utc)` — no `datetime.utcnow()`
- **Deprecation delegation**: Legacy functions (`send_notification`, `_build_html_body`) delegate to new class-based implementations with `DeprecationWarning`
- **Monotonic date protection**: Date fields representing "earliest known" events (like `listed_date`, `first_seen`) must never be overwritten with a later value. In `upsert_listing()`, these fields are excluded from the generic update loop and handled separately with `min(old, new)` logic. This prevents external source renewal dates from resetting the listing age.
