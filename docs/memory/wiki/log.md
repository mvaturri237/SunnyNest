# SunnyNest Wiki Log

> Chronological record of all changes. Newest entries at top.
> Each entry links to affected entity/concept pages.

---

## 2026-04-13

### TCC Exit Code 78 Fix — All Remaining Launchd Plists
- **Result:** APPROVED (0 P1, 0 P2 after fix round)
- **Entities updated:** [Scheduler (launchd)](entities/scheduler-launchd.md)
- **Concepts updated:** [launchd Patterns](concepts/launchd-patterns.md) (no changes needed — already documented)
- **Summary:** Scraper and 4 other launchd agents were failing with exit code 78 (TCC permission denied) because `StandardOutPath`/`StandardErrorPath` pointed to `~/Documents/zillow/logs/`. Moved all 5 remaining plists to `/tmp/sunnynest/` (matching the dashboard plist fix from 2026-04-12). Also differentiated notify-am/pm log filenames (were both `notify-stdout.log`), fixed log-rotate stderr pointing to stdout file, and updated support scripts (`rotate-logs.sh`, `install-service.sh`, `uninstall-service.sh`).
- **Files:** `com.sunnynest.scraper.plist`, `com.sunnynest.notify-am.plist`, `com.sunnynest.notify-pm.plist`, `com.sunnynest.backoffice.plist`, `com.sunnynest.log-rotate.plist`, `scripts/install-service.sh`, `scripts/rotate-logs.sh`, `scripts/uninstall-service.sh`
- **Verification:** All 6 agents exit code 0. Manual scraper trigger succeeded (39 listings scraped).
- **Pre-existing issue noted:** `sqlite3.IntegrityError` on `price_history` UNIQUE constraint — unrelated to this fix.

### Dashboard Cosmetic Changes — Left-Align Filter Bar, Zoom Out Map, Remove Clustering
- **Result:** APPROVED (0 P1, 0 P2, 2 P3)
- **Entities updated:** [Map View](entities/map-view.md), [Filter Bar](entities/filter-bar.md)
- **Summary:** Three cosmetic UI changes: (1) Filter bar left-aligned by removing `max-width: 1920px` and `margin: 0 auto` from `.filter-bar-inner`. (2) Map default zoom changed from 13 → 12 for a wider area view. (3) Marker clustering removed — `L.markerClusterGroup` replaced with `L.layerGroup`, MarkerCluster CDN (2 CSS + 1 JS) removed from `base.html`.
- **Files:** `web/static/css/style.css`, `web/static/js/map.js`, `web/templates/base.html`
- **P3 notes:** (1) Orphaned `.cluster-icon` CSS block (~16 lines) is now dead code. (2) Comment "Marker Cluster Group (1.1)" in map.js is stale.

---

## 2026-04-12

### Dashboard Plist Migrated to FastAPI/uvicorn
- **Result:** APPROVED (0 P1, 0 P2 after fix round)
- **Entities updated:** [Scheduler (launchd)](entities/scheduler-launchd.md), [Config (YAML)](entities/config-yaml.md), [Notification System](entities/notification-system.md)
- **Concepts updated:** [launchd Patterns](concepts/launchd-patterns.md)
- **Summary:** Dashboard was down because `com.sunnynest.dashboard.plist` still ran the old Streamlit app (`streamlit run app.py` on port 8501) after the FastAPI migration. Updated to `uvicorn web.main:app --host 127.0.0.1 --port 8000`. Also discovered the root cause of exit code 78 on ALL launchd agents: `StandardOutPath`/`StandardErrorPath` pointed to TCC-protected `~/Documents/zillow/logs/` — moved to `/tmp/sunnynest/`. Updated `config.yaml` `dashboard_url` and all stale `localhost:8501` fallback defaults in code.
- **Files:** `com.sunnynest.dashboard.plist`, `scripts/start-dashboard.sh`, `config.yaml`, `src/notifier.py`, `backoffice.py`, `scripts/install-service.sh`, `scripts/test_email_notification.py`
- **Follow-up needed:** Other 5 launchd agents (`backoffice`, `scraper`, `notify-am`, `notify-pm`, `log-rotate`) still need the same `StandardOutPath`/`StandardErrorPath` fix (move from `~/Documents/zillow/logs/` to `/tmp/sunnynest/`).

### WhatsApp Notification Channel Added
- **Result:** APPROVED (0 P1, 0 P2, 3 P3)
- **Entities updated:** [Notification System](entities/notification-system.md), [Config (YAML)](entities/config-yaml.md)
- **Summary:** Added `WhatsAppChannel` class to the notification system, implementing the `BaseNotificationChannel` adapter pattern. Uses Meta WhatsApp Business Cloud API via `httpx` (no new dependencies). Sends concise text messages (4096-char limit) with listing summaries. Same conditions as email: same config filters, same anti-spam guard, same launchd schedule. Pre-flight check in `NotificationService.run()` changed from SMTP-only to channel-agnostic — each channel validates its own credentials independently. Admin UI updated with WhatsApp status on Settings page and credential warning on Notifications page. WhatsApp disabled by default in config (`whatsapp.enabled: false`).
- **Files:** `src/notifier.py`, `config.yaml`, `.env.example`, `scripts/run-notify.py`, `src/utils.py`, `web/templates/admin/settings.html`, `web/templates/admin/notifications.html`, `web/routes/admin.py`
- **P3 notes:** (1) Duplicate `_get()` helper in both channels — extract to module-level in future. (2) WhatsApp env vars not in `get_env_status()` System Health panel. (3) No phone number format validation on recipient.

---

## 2026-04-10

### Default Days Listed Filter Set to 30 Days
- **Result:** APPROVED (0 P1, 0 P2, 0 P3)
- **Entities updated:** [Filter Bar](entities/filter-bar.md)
- **Summary:** Changed default "📅 Days Listed" filter from "Any" (empty string) to ≤30 days. `_DROPDOWN_DEFAULTS["filter_max_days"]` in `web/routes/dashboard.py` set to `"30"`. Hides old listings (e.g., 500+ day Realtor.com listings) by default. Users can still select "Any" or enter a custom value (e.g., 90 days) via the existing Days Listed dropdown UI.
- **Files:** `web/routes/dashboard.py`

---

## 2026-04-06

### Listing Lifecycle Analytics & Days-on-Market Filter (Implementation)
- **Result:** IMPLEMENTED & APPROVED (Phase 1: 0 P1, 1 P2 fixed; Phase 2: 0 P1, 0 P2, 2 P3 fixed)
- **Entities updated:** [Database Schema](entities/database-schema.md), [Filter Bar](entities/filter-bar.md), [Admin Dashboard](entities/admin-dashboard.md)
- **Summary:** Full implementation of listing lifecycle feature: (1) `deactivated_at` DateTime column on `listings` table with idempotent migration, set by `mark_inactive()`, cleared on re-activation, added to upsert exclusion tuples. (2) "📅 Days Listed" dashboard filter dropdown between Source and More — radio presets (Any/≤7d/≤14d/≤30d/≤60d) + custom input, filters by `days_on_market` column, full snapshot/revert/apply/reset pattern with HTMX. (3) "⏱️ Listing Lifecycle" analytics section on admin analytics page — 3 KPI cards (avg/median lifespan, total removed) + 2 bar charts (lifespan by bedrooms, lifespan by price range). Uses `COALESCE(deactivated_at, last_seen)` for backward compatibility with legacy data.
- **Files:** `src/models.py`, `src/database.py`, `web/routes/__init__.py`, `web/routes/listings.py`, `web/routes/dashboard.py`, `web/routes/admin.py`, `web/templates/dashboard.html`, `web/static/js/filters.js`, `web/templates/admin/analytics.html`, `web/static/css/style.css`, `web/static/css/admin.css`, `web/templates/base.html`, `web/templates/admin/base.html`

### Listing Lifecycle Analytics & Days-on-Market Filter (Architecture Plan)
- **Result:** PLANNED (architecture plan created)
- **Entities updated:** [Database Schema](entities/database-schema.md), [Filter Bar](entities/filter-bar.md), [Admin Dashboard](entities/admin-dashboard.md)
- **Summary:** Architecture plan for 3 features: (1) `deactivated_at` timestamp column on `listings` table with idempotent migration and `mark_inactive()` update, (2) "Max Days Listed" dashboard filter using existing `days_on_market` column with radio presets (7/14/30/60 days) + custom input, (3) Listing Lifecycle analytics section on admin analytics page with KPI cards (avg/median lifespan, total removed) and bar charts (lifespan by bedrooms, lifespan by price range). 2-phase plan: Phase 1 = backend, Phase 2 = frontend.
- **Plan:** [`plans/listing-lifecycle.md`](../../../plans/listing-lifecycle.md)

### Source Filter HTMX Race Condition Fix
- **Result:** APPROVED (0 P1, 0 P2, 2 P3)
- **Entities updated:** [Filter Bar](entities/filter-bar.md)
- **Summary:** Fixed race condition where HTMX read hidden input values before JS `applyFilter()` updated them, causing source filter to always send `filter_source=all`. Fix: changed all 4 Apply buttons from default click trigger to `hx-trigger="apply"` (custom event). JS now dispatches `CustomEvent("apply")` after committing hidden input values, ensuring HTMX reads correct values. Also updated `resetAllFilters()` to use the same custom event pattern.
- **Files:** `web/templates/dashboard.html`, `web/static/js/filters.js`

### Realtor Property Type Filter + API Usage Status Fix
- **Result:** APPROVED (0 P1, 0 P2, 3 P3)
- **Entities updated:** [Realtor Scraper](entities/realtor-scraper.md), [API Usage Page](entities/api-usage-page.md)
- **Summary:** (1) Added `propertyType=single_family` to Realtor API params — API was returning 171 mixed-type listings but orchestrator only accepts houses; now fetches 17 single-family listings directly. Correct API param is `propertyType` (camelCase), not `type` or `property_type`. (2) Fixed API Usage page status badge showing "Last call OK" (green) when `status_code=None` (connection errors) — added `else` branch to set `last_call_status="error"` and `last_call_status_text="Connection Error"`.
- **Files:** `src/scrapers/realtor_scraper.py`, `web/routes/admin.py`

### SSL Certificate Verification Fix for RapidAPI Scrapers
- **Result:** APPROVED (0 P1, 0 P2, 3 P3)
- **Entities updated:** [Realtor Scraper](entities/realtor-scraper.md), [Zillow Scraper](entities/zillow-scraper.md)
- **Concepts updated:** [Security Patterns](concepts/security-patterns.md)
- **Summary:** Fixed SSL certificate verification failure caused by two compounding issues: (1) Palo Alto Networks GlobalProtect firewall performing TLS decryption with a root CA not in Python's certifi bundle, and (2) OpenSSL 3.6.0 strict X.509 validation rejecting leaf certs missing the Authority Key Identifier (AKI) extension. Fix: added `_build_ssl_context()` static method to `BaseScraper` that loads certifi + PANW root CA and clears `VERIFY_X509_STRICT` while preserving `CERT_REQUIRED` and `check_hostname=True`. Both scrapers now pass `verify=ssl_ctx` to `httpx.AsyncClient()`.
- **Files:** `src/scrapers/base.py`, `src/scrapers/realtor_scraper.py`, `src/scrapers/zillow_scraper.py`, `data/certs/panw-root-ca.pem` (new)

### Dedup Candidate Narrowing Fix
- **Result:** APPROVED (0 P1, 0 P2, 2 P3)
- **Entities updated:** [Deduplication](entities/deduplication.md), [Database Schema](entities/database-schema.md)
- **Summary:** Fixed bug where cross-source duplicates with different bedroom counts were missed. Root cause: `find_duplicate_candidates()` filtered by `zip_code + bedrooms`, preventing candidates with mismatched bedroom counts from being scored. Fix: removed `bedrooms` from candidate narrowing (now ZIP-only), moved bedroom comparison to scoring phase (15 points). Updated index from `(zip_code, bedrooms, is_active)` to `(zip_code, is_active)`. Merged existing duplicate at 370 Cypress Ave (Craigslist listing 107 → Zillow listing 111).
- **Files:** `src/dedup.py`, `src/models.py`

### LLM Wiki Schema Updates (Phase 1)
- **Result:** APPROVED (0 P1, 0 P2, 7 P3)
- **Summary:** Updated AGENTS.md (Pre-flight, Active Roles, §1 Memory Protocol, §7 Wiki Sync). Prepared skill-memory-manager.md (full rewrite), skill-wiki-lint.md (new), and .roomodes edits (4 modes) for manual copy to protected .roo/ folder.
- **Files:** `AGENTS.md`, `docs/temp/roo-updates/skill-memory-manager.md`, `docs/temp/roo-updates/skill-wiki-lint.md`, `docs/temp/roo-updates/roomodes-edits.md`
- **Plan:** `plans/llm-wiki.md` §7-§8

### LLM Wiki Bootstrap (Phase 0)
- **Result:** IMPLEMENTED
- **Entities updated:** All 16 entity pages (NEW), all 10 concept pages (NEW)
- **Summary:** Created wiki directory structure, 16 entity pages, 10 concept pages, index.md, log.md. Slimmed activeContext.md and progress.md.
- **Plan:** `plans/llm-wiki.md`

### Admin API Usage Page Redesigned
- **Result:** APPROVED (0 P1, 0 P2 after 1 fix cycle, 9 P3)
- **Entities updated:** [API Usage Page](entities/api-usage-page.md), [Admin Dashboard](entities/admin-dashboard.md), [Database Schema](entities/database-schema.md)
- **Summary:** Complete overhaul — CSS-only donut quota charts, success rate trends, monthly comparison, daily sparklines. ~500 lines new CSS. Realtor.com budget updated 100→150.
- **Files:** `src/database.py`, `web/routes/admin.py`, `web/templates/admin/api-usage.html`, `web/static/css/admin.css`

### Cloud Scheduler Evaluation
- **Result:** COMPLETE (plan only)
- **Entities updated:** [Scheduler (launchd)](entities/scheduler-launchd.md)
- **Summary:** Evaluated 3 options. Recommended GitHub Actions + git-committed DB for immediate use (~2h effort), Turso for long-term.
- **Plan:** `plans/cloud-scheduler.md`

### Scheduler Fix Implemented
- **Result:** APPROVED (0 P1, 0 P2, 7 P3)
- **Entities updated:** [Scheduler (launchd)](entities/scheduler-launchd.md), [Admin Dashboard](entities/admin-dashboard.md), [Orchestrator](entities/orchestrator.md)
- **Concepts updated:** [launchd Patterns](concepts/launchd-patterns.md)
- **Summary:** APScheduler replaced with macOS launchd. 3 new plists, 2 standalone scripts. 30-day calendar heatmap added.
- **Files:** 5 created, 9 modified
- **Plan:** `plans/scheduler-fix.md`

### Multi-Select Source Filter Verified + CSS Fix
- **Result:** APPROVED (0 P1, 0 P2 after 1 fix cycle, 6 P3)
- **Entities updated:** [Filter Bar](entities/filter-bar.md), [Listing Card](entities/listing-card.md)
- **Summary:** Source filter converted to multi-select checkbox dropdown. Added missing `.source-realtor` CSS class.
- **Files:** `dashboard.html`, `filters.js`, `web/routes/__init__.py`, `src/database.py`, `listing-card.html`, `style.css`

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
