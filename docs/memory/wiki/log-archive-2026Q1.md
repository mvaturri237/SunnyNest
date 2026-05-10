# SunnyNest Wiki Log Archive — 2026 Q1 (older entries)

> Entries from 2026-04-01 and earlier. Archived from `log.md` on 2026-05-10
> for context-window efficiency. **Newer entries live in [`log.md`](log.md).**
> Each entry below preserves the original format and links.

---

## 2026-04-01

### Realtor.com Scraper Implemented
- **Result:** APPROVED (0 P1, 0 P2, 8 P3 after fix cycle)
- **Entities updated:** [Realtor Scraper](entities/realtor-scraper.md) (NEW), [Orchestrator](entities/orchestrator.md), [Config (YAML)](entities/config-yaml.md), [API Usage Page](entities/api-usage-page.md)
- **Concepts updated:** [Adapter Pattern](concepts/adapter-pattern.md)
- **Summary:** Third data source. RapidAPI, 150 req/mo free tier. ~580 lines. Admin API Usage refactored to multi-source.
- **Files:** `src/scrapers/realtor_scraper.py` (NEW), `src/orchestrator.py`, `config.yaml`, + 7 more
- **Plan:** `plans/realtor-scraper.md`

### Realtor.com Scraper Architecture Plan
- **Result:** COMPLETE (plan only)
- **Entities updated:** [Realtor Scraper](entities/realtor-scraper.md)
- **Summary:** Comprehensive plan covering API selection, configuration, implementation, integration points.
- **Plan:** `plans/realtor-scraper.md`

---

## 2026-03-31

### Notification + Analytics Config Filter Fix
- **Result:** APPROVED (0 P1, 0 P2, 5 P3)
- **Entities updated:** [Notification System](entities/notification-system.md), [Database Schema](entities/database-schema.md)
- **Summary:** Notifications and analytics now apply config.yaml filters (~10 matching instead of all 39). DRY refactor: `_apply_listing_filters()` eliminates ~90 lines.
- **Files:** `src/database.py`, `src/notifier.py`, `web/routes/admin.py`

### Notification 39-Listing Email Fix
- **Result:** APPROVED (0 P1, 0 P2, 2 P3)
- **Entities updated:** [Database Schema](entities/database-schema.md), [Notification System](entities/notification-system.md)
- **Concepts updated:** [Upsert Exclusion Pattern](concepts/upsert-exclusion-pattern.md)
- **Summary:** Added `notified`, `is_favorite`, `is_disliked` to upsert exclusion tuples.
- **Files:** `src/database.py`

### School Assignment Feature Implemented
- **Result:** APPROVED (0 P1, 0 P2 after 1 fix cycle, 6 P3)
- **Entities updated:** [School Districts](entities/school-districts.md) (NEW), [Orchestrator](entities/orchestrator.md), [Database Schema](entities/database-schema.md), [Listing Card](entities/listing-card.md)
- **Summary:** Shows assigned schools per listing via GeoJSON point-in-polygon. 3 new DB columns. Lazy singleton. 35/38 listings populated.
- **Files:** `src/school_districts.py` (NEW), + 10 more
- **Plan:** `plans/school-assignment.md`

### Filter Bar Redesign Implemented
- **Result:** APPROVED (0 P1, 0 P2 after fix cycle, 4 P3)
- **Entities updated:** [Filter Bar](entities/filter-bar.md)
- **Summary:** All 6 phases: Price dropdown, Beds & Baths combined, More overflow, Sort, mobile responsive, WCAG AA. 669 lines JS, ~400 lines CSS.
- **Files:** `web/routes/__init__.py`, `web/templates/dashboard.html`, `web/static/js/filters.js`, + 4 more
- **Plan:** `plans/filter-bar-redesign.md`

### Manual Sync Button on Admin Dashboard
- **Result:** APPROVED (0 P1, 0 P2, 3 P3 after 1 fix cycle)
- **Entities updated:** [Admin Dashboard](entities/admin-dashboard.md)
- **Summary:** `POST /admin/sync` endpoint with HTMX button, 5-min cooldown, asyncio.Lock, basic auth.
- **Files:** `web/routes/admin.py`, `web/templates/admin/dashboard.html`, + 4 more

### Startup Environment Validation
- **Result:** APPROVED (0 P1, 0 P2, 3 P3)
- **Entities updated:** [Admin Dashboard](entities/admin-dashboard.md), [Config (YAML)](entities/config-yaml.md)
- **Concepts updated:** [Environment Validation](concepts/environment-validation.md), [Silent Failure Pattern](concepts/silent-failure-pattern.md)
- **Summary:** `_validate_environment()` at startup + System Health panel on admin dashboard.
- **Files:** `web/main.py`, `web/dependencies.py`, `web/routes/admin.py`, + 2 more

### Notification Failure Fix
- **Result:** APPROVED (0 P1, 0 P2, 2 P3)
- **Entities updated:** [Notification System](entities/notification-system.md)
- **Concepts updated:** [Silent Failure Pattern](concepts/silent-failure-pattern.md)
- **Summary:** Anti-spam guard counts all attempts. Pre-flight SMTP check. SMTP warning banner.
- **Files:** `src/database.py`, `src/notifier.py`, `web/routes/admin.py`, `web/templates/admin/notifications.html`

### Zillow API Counter Fix
- **Result:** APPROVED (0 P1, 0 P2 after 1 fix cycle)
- **Entities updated:** [Zillow Scraper](entities/zillow-scraper.md), [API Usage Page](entities/api-usage-page.md)
- **Concepts updated:** [Silent Failure Pattern](concepts/silent-failure-pattern.md), [Environment Validation](concepts/environment-validation.md)
- **Summary:** Added `python-dotenv` for `.env` support. API key warning banner. Staleness indicator.
- **Files:** `web/main.py`, `web/routes/admin.py`, + 5 more

---

## 2026-03-30

### Map Framework Evaluation
- **Result:** RECOMMENDATION (Leaflet.js confirmed)
- **Entities updated:** [Map View](entities/map-view.md)
- **Summary:** Evaluated 6 frameworks against 12 criteria. Leaflet scored highest (168 points). Migration to alternatives would consume 50-80% of budget.
- **Plan:** `plans/map-framework-evaluation.md`

### UI: Move Listing Count into Left Panel
- **Result:** APPROVED (0 P1, 0 P2, 1 P3)
- **Entities updated:** [Listing Card](entities/listing-card.md)
- **Summary:** Moved `#result-count` from header bar into `.left-panel`.
- **Files:** `web/templates/dashboard.html`, `web/static/css/style.css`

### Follow-up Fix: Deprecated Query.get() Removal
- **Result:** APPROVED (0 P1, 0 P2, 0 P3)
- **Entities updated:** [Database Schema](entities/database-schema.md), [Orchestrator](entities/orchestrator.md), [Deduplication](entities/deduplication.md)
- **Summary:** Replaced all 5 `session.query(Listing).get()` → `session.get(Listing, id)` across 4 files.
- **Files:** `src/database.py`, `src/dedup.py`, `src/orchestrator.py`

### Bug Fix Round (Phase 1 Review)
- **Result:** APPROVED (5 P1 + 1 P2 fixed)
- **Entities updated:** [Listing Card](entities/listing-card.md), [Map View](entities/map-view.md)
- **Summary:** Dislike card disappear, favorite toggle, session.get(), boundary 404, OOB result count, image URL parsing.
- **Files:** `web/routes/actions.py`, `web/routes/api.py`, + 4 more

### Phase 2: Backoffice Admin Panel
- **Result:** APPROVED (0 P1, 0 P2)
- **Entities updated:** [Admin Dashboard](entities/admin-dashboard.md) (NEW)
- **Summary:** 5 admin pages at `/admin/`. Dedicated admin CSS. Real DB queries for KPIs.
- **Files:** `web/routes/admin.py`, `web/static/css/admin.css`, `web/templates/admin/*.html`

### Phase 1 Sprint 2: Dashboard Features
- **Result:** IMPLEMENTED
- **Entities updated:** [Map View](entities/map-view.md), [Listing Card](entities/listing-card.md)
- **Summary:** Boundary overlay, functional favorites/dislikes, card-map bidirectional sync, OOB result count.

### Phase 1 Sprint 1: P0 Critical Fixes
- **Result:** IMPLEMENTED
- **Entities updated:** [Map View](entities/map-view.md), [Listing Card](entities/listing-card.md)
- **Summary:** Left panel width 440px, OSM tiles, price pill markers, image fallback, scroll wheel zoom disabled.

### Light Mode Switch
- **Result:** IMPLEMENTED
- **Entities updated:** [Listing Card](entities/listing-card.md), [Map View](entities/map-view.md)
- **Summary:** Entire website converted to light theme. CSS custom properties updated.

### Phase 1 UX Spec
- **Result:** COMPLETE (plan only)
- **Summary:** Visual audit of Phase 0 dashboard. 3 P0, 12 P1, 6 P2 fixes identified. 5-sprint plan.
- **Plan:** `plans/phase1-ux-spec.md`

---

## 2026-03-29

### Frontend Migration Architecture Review
- **Result:** COMPLETE (plan only)
- **Entities updated:** [Map View](entities/map-view.md), [Config (YAML)](entities/config-yaml.md)
- **Summary:** 9 key decisions: keep SQLAlchemy, Leaflet.js (drop Folium), single Uvicorn, custom CSS. Owner selected `sunnynest-dashboard.html` as template.
- **Plan:** `plans/frontend-migration-arch-review.md`

### Frontend Migration UX Review
- **Result:** COMPLETE (plan only)
- **Summary:** Reviewed migration plan across 6 UX dimensions. Critical: wrong mockup referenced. 15 prioritized recommendations.
- **Plan:** `plans/frontend-migration-ux-review.md`

### Frontend Framework Migration Evaluation
- **Result:** PROPOSAL → IMPLEMENTED
- **Summary:** Evaluated 6 frameworks. FastAPI + HTMX + Jinja2 recommended (4.70/5). 25-33h estimated effort.
- **Plan:** `plans/frontend-migration.md`

### DOM-Informed CSS Fix
- **Result:** APPROVED (0 P1, 0 P2, 2 P3)
- **Summary:** Added `stLayoutWrapper` selectors alongside `stVerticalBlockBorderWrapper` in 3 CSS regions.
- **Files:** `app.py`

### Removed Pagination
- **Result:** APPROVED (0 P1, 0 P2, 1 P3)
- **Summary:** All listings render in scrollable container. 99 lines removed.
- **Files:** `app.py`

### Layout Fix: Full Viewport Height
- **Result:** APPROVED (0 P1, 0 P2)
- **Summary:** Added `height: calc(100vh - 100px)` on 3 CSS selectors.
- **Files:** `app.py`

### Map Tiles Changed: CartoDB Positron → OpenStreetMap
- **Result:** APPROVED (0 P1, 0 P2)
- **Entities updated:** [Map View](entities/map-view.md)
- **Summary:** One-line change. Map now shows parks, transit, POIs.
- **Files:** `app.py`

### Map Improvement UX Consultation
- **Result:** COMPLETE (plan only)
- **Entities updated:** [Map View](entities/map-view.md)
- **Summary:** Tile layer recommendations, POI feature design, 5-phase plan.
- **Plan:** `plans/map-improvement.md`

### Port Cleanup + launchd Service Installation
- **Result:** IMPLEMENTED
- **Entities updated:** [Scheduler (launchd)](entities/scheduler-launchd.md)
- **Summary:** Killed rogue instances. Installed launchd agents for dashboard (8501), backoffice (8502), log-rotate.

---

## 2026-03-28

### Sidebar Regression Fix — App Isolation Enforced
- **Result:** APPROVED (0 P1, 0 P2, 2 P3)
- **Concepts updated:** [App Isolation](concepts/app-isolation.md)
- **Summary:** Removed ALL `st.sidebar` from `app.py`. New rule: app.py must NEVER use st.sidebar.
- **Files:** `app.py`

### Scrape Interval → 6h + Craigslist API Logging
- **Result:** APPROVED (0 P1, 0 P2, 0 P3)
- **Entities updated:** [Craigslist Scraper](entities/craigslist-scraper.md), [Config (YAML)](entities/config-yaml.md)
- **Summary:** Interval 24h→6h. Craigslist API call logging added on 3 code paths.
- **Files:** `config.yaml`, `src/scrapers/craigslist_scraper.py`

### Backoffice UI Mockup
- **Result:** COMPLETE (mockup only)
- **Summary:** 5 pages, dark theme, SVG charts, WCAG AA. Realistic sample data.
- **Files:** `docs/temp/mockups/backoffice.html`

### Backoffice Plan Revised
- **Result:** COMPLETE (plan only)
- **Entities updated:** [Admin Dashboard](entities/admin-dashboard.md), [Config (YAML)](entities/config-yaml.md)
- **Summary:** launchd auto-start required. Settings page added. Config.yaml persistence.
- **Plan:** `plans/backoffice.md`

### Cross-Source Deduplication Implemented
- **Result:** APPROVED (0 P1, 0 P2 after fix cycle)
- **Entities updated:** [Deduplication](entities/deduplication.md) (NEW), [Database Schema](entities/database-schema.md), [Orchestrator](entities/orchestrator.md), [Listing Card](entities/listing-card.md)
- **Concepts updated:** [Upsert Exclusion Pattern](concepts/upsert-exclusion-pattern.md)
- **Summary:** `listing_sources` table, multi-signal scoring (threshold ≥75), address normalization, merge strategy. 23 listings migrated.
- **Files:** `src/dedup.py` (NEW), `src/models.py`, `src/database.py`, `src/orchestrator.py`, + more
- **Plan:** `plans/deduplication.md`

### Email Notification End-to-End Test
- **Result:** SUCCESS
- **Entities updated:** [Notification System](entities/notification-system.md)
- **Summary:** Gmail App Password created. Test email sent and received successfully.

### Remove House Type Filter
- **Result:** APPROVED (0 P1, 0 P2 after fix cycle)
- **Entities updated:** [Zillow Scraper](entities/zillow-scraper.md), [Craigslist Scraper](entities/craigslist-scraper.md), [Config (YAML)](entities/config-yaml.md)
- **Summary:** Hardcoded house-only ingestion. Default property type changed from "apartment" to "house".
- **Files:** `app.py`, `src/scrapers/zillow_scraper.py`, `src/scrapers/craigslist_scraper.py`, `config.yaml`

---

## 2026-03-27

### Comprehensive Code Review + Fix Cycle
- **Result:** APPROVED (0 P1, 0 P2 after 2 fix cycles)
- **Entities updated:** [Zillow Scraper](entities/zillow-scraper.md), [Geocoder](entities/geocoder.md), [Notification System](entities/notification-system.md), [Database Schema](entities/database-schema.md)
- **Concepts updated:** [Security Patterns](concepts/security-patterns.md)
- **Summary:** 3 P1 + 12 P2 + 14 P3 found. Key fixes: env vars for secrets, TLS verification, XSS escaping, SQL aggregates, singleton geocoder, bounded cache, circuit breaker auto-reset.
- **Files:** `app.py`, `config.yaml`, `src/database.py`, `src/geocoder.py`, `src/notifier.py`, `src/orchestrator.py`, `src/scheduler.py`

### Database Analytics Improvements
- **Result:** APPROVED (0 P1, 0 P2 after fix cycle)
- **Entities updated:** [Database Schema](entities/database-schema.md)
- **Summary:** `days_on_market` column, price history gap-filling (MAX_GAP_DAYS=30), scraper price validation.
- **Files:** `src/models.py`, `src/database.py`, `src/orchestrator.py`, `src/scrapers/craigslist_scraper.py`, `src/scrapers/zillow_scraper.py`

### Dashboard Persistence via launchd
- **Result:** IMPLEMENTED
- **Entities updated:** [Scheduler (launchd)](entities/scheduler-launchd.md)
- **Concepts updated:** [launchd Patterns](concepts/launchd-patterns.md)
- **Summary:** macOS launchd Launch Agent for persistent dashboard. KeepAlive, log rotation, localhost binding.
- **Files:** `com.sunnynest.dashboard.plist`, `scripts/start-dashboard.sh`, `scripts/install-service.sh`, + more

### UX Mockups Created
- **Result:** COMPLETE (mockups only)
- **Summary:** `sunnynest-dashboard.html` (faithful reproduction), `sunnynest-modern-saas.html` (modern redesign). Design bible updated.
- **Files:** `docs/temp/mockups/sunnynest-dashboard.html`, `docs/temp/mockups/sunnynest-modern-saas.html`

### Initial System Setup
- **Result:** IMPLEMENTED
- **Summary:** Core system: Zillow scraper, Craigslist scraper, orchestrator, geocoder, database, notification system, Streamlit dashboard.
