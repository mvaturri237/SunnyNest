# Decision Log

## 2026-04-06: Knowledge management — Karpathy-style LLM Wiki (IMPLEMENTED)
- **Problem**: Knowledge about entities (scrapers, UI components, patterns) was scattered across 5 append-only chronological files totaling ~1,100 lines. Agents had to read all files to find relevant context, wasting tokens and risking inconsistency.
- **Evaluated**: (a) Keep current journal-based memory, (b) Karpathy LLM Wiki with entity pages + index + log, (c) Full Obsidian-style wiki with backlinks and graph view
- **Decision**: Karpathy LLM Wiki — entity-centric pages in `docs/memory/wiki/` with `index.md` (content catalog) and `log.md` (chronological record)
- **Rationale**: Entity pages consolidate scattered knowledge into one queryable page per component. Index-first navigation reduces token usage from ~1,000 lines to ~50-100 lines per task start. No separate Librarian mode needed — Orchestrator handles wiki sync as part of existing Code→Review workflow.
- **Key choices**: 16 entity pages, 10 concept pages, shared files (decisionLog, lessonsLearned, systemPatterns) kept as-is as chronological raw sources, plans indexed in wiki, lint every ~10 tasks
- **Trade-off**: Additional maintenance overhead per task (wiki sync step) — acceptable because the Orchestrator already manages the Code→Review cycle
- **Plan**: `plans/llm-wiki.md`
- **Source**: [Karpathy LLM Wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)

## 2026-04-06: Scheduler mechanism — launchd-native replacing APScheduler (PLANNED)
- **Problem**: APScheduler embedded in web servers (Streamlit + FastAPI) is unreliable — 3-day scraping gap (April 3–5) caused by process sleep/idle and duplicate scheduler instances
- **Evaluated**: (a) macOS launchd plist, (b) standalone Python daemon with APScheduler, (c) cron job, (d) keep APScheduler in FastAPI
- **Decision**: macOS launchd with `StartCalendarInterval` — 3 new plists for daily scrape (06:00), morning notify (08:00), evening notify (20:00)
- **Rationale**: Already proven in project (backoffice, log-rotate plists work reliably); OS-native catch-up semantics (fires missed jobs on wake); complete process isolation from web servers; no new dependencies
- **Key choices**: Standalone Python scripts (`scripts/run-scraper.py`, `scripts/run-notify.py`) import orchestrator/notifier directly; Homebrew Python to avoid TCC issues; 4-phase migration with parallel run period
- **Trade-off**: macOS-only solution — acceptable since this is a personal tool running on a single Mac
- **Monitoring**: 30-day calendar heatmap on admin dashboard to detect future gaps
- **Plan**: `plans/scheduler-fix.md`

## 2026-04-01: Third data source — Realtor.com via RapidAPI (IMPLEMENTED)
- **Problem**: Increase listing coverage beyond Zillow and Craigslist for Sunnyvale, CA rentals
- **Evaluated**: Realtor.com (MLS-sourced, RapidAPI), Apartments.com (Playwright scraping), Redfin (stingray API), Facebook Marketplace (auth required), HotPads (95% Zillow overlap)
- **Decision**: Realtor.com via "Realtor Search" by API_Jeeves on RapidAPI, free tier (100 req/month)
- **Rationale**: Fastest to implement (mirrors ZillowScraper httpx pattern), MLS-sourced data catches listings 12-24h before Zillow, ~30% unique listings, free tier sufficient with optimizations
- **Optimizations for free tier**: Search by city (not per-zip) → 1 call/page instead of 4; sync daily instead of every 6h; max 2 pages → ~60 calls/month
- **Key choices**: Shared `RAPIDAPI_KEY` (with optional `REALTOR_RAPIDAPI_KEY` override), `enabled: true` default, source name `"realtor"` in DB
- **Trade-off**: 24h delay for new Realtor.com listings (vs 6h for Zillow) — acceptable since main value is catching listings Zillow misses entirely
- **Next source**: Apartments.com (Playwright-based, ~40-50% unique listings, rich amenity data) recommended as the fourth source

## 2026-03-31: School assignment data source — NCES SABS + local GeoJSON (IMPLEMENTED)
- **Problem**: Show actual assigned schools (elementary, middle, high) per listing address, not just district name
- **Evaluated**: NCES SABS (free federal), GreatSchools API, Zillow/Realtor.com (not exposed), Google Places (proximity only), Maponics ($5K+/yr), ATTOM/CoreLogic ($500+/mo), CDE, district websites
- **Decision**: NCES SABS attendance zone polygons + `shapely` point-in-polygon lookups
- **Rationale**: Free, authoritative, offline (no API calls), sub-ms lookups, covers all 3 Sunnyvale districts
- **Implementation**: Approximate GeoJSON boundary polygons stored in `data/school-boundaries/`, loaded by lazy singleton `_SchoolBoundaryStore`
- **Trade-off**: Current boundaries are simplified rectangles (approximate) — should be replaced with official SABS data for production accuracy
- **Future**: Consider adding GreatSchools ratings (1-10) as a supplement, filter-by-school feature

## 2026-03-30: Map framework evaluation — Stay with Leaflet.js (RECOMMENDATION)
- **Problem**: Verify Leaflet.js is the right map framework before investing ~14h in map makeover implementation
- **Evaluation**: Compared 6 frameworks against 12 weighted criteria:
  - Leaflet.js: **168 points** 🥇 (current — zero migration cost, best plugins, lightest bundle)
  - Google Maps: 147 points 🥈 (best UX but requires billing account + API key)
  - MapLibre GL JS: 143 points 🥉 (best open-source alternative — vector tiles, smooth zoom)
  - Mapbox GL JS: 134 points (proprietary, vendor lock-in)
  - OpenLayers: 127 points (enterprise GIS — overkill)
  - Deck.gl: 104 points (WebGL data viz — wrong tool)
- **Key insight**: 75% of the "Zillow look" comes from custom overlays (price pills, popups, interactions), not the base map library — and we already have most of these
- **Migration cost**: Switching to any alternative would consume 50-80% of the 14h budget (7-11h for MapLibre, 6-9h for Google Maps)
- **Reconsider trigger**: Need for vector tiles, dark mode tile switching, 500+ markers, 3D terrain, or adding a bundler
- **Tile upgrade**: OSM Standard is adequate; Stadia Outdoors recommended as optional upgrade in Sprint 3 (1-line change)
- **Status**: RECOMMENDATION — awaiting product owner decision
- **Document**: `plans/map-framework-evaluation.md`

## 2026-03-29: Frontend migration architecture review — 9 key decisions (REVIEW)
- **Template choice**: Owner selected `sunnynest-dashboard.html` (1,324-line dark-theme mockup) — NOT `sunnynest-v4.html` or `user-dashboard.html`
- **Project structure**: New `web/` directory for all FastAPI code (routes/, templates/, static/); `src/` backend unchanged
- **Database**: Keep SQLAlchemy + manual migrations (no Alembic) — 5 tables, infrequent schema changes don't justify migration tooling
- **Scheduler**: APScheduler in FastAPI lifespan event — cleaner lifecycle than Streamlit session_state, single instance guaranteed
- **Map**: Client-side Leaflet.js directly (drop Folium) — eliminates triple abstraction layer (Python → Folium → HTML → streamlit-folium → iframe → Leaflet)
- **Deployment**: Single Uvicorn process (no Gunicorn) — local single-user app; multi-worker would create duplicate schedulers
- **CSS**: Custom CSS (no Tailwind/Bootstrap) — mockup already has production-quality CSS with design tokens
- **Backend integration**: Direct Python imports (no REST API layer) — zero overhead, type-safe; API layer unnecessary for single-user local app
- **Dependencies**: Remove 6 (streamlit, folium, plotly, pandas, playwright, streamlit-folium), add 5 (fastapi, uvicorn, jinja2, python-multipart, sse-starlette)
- **Phase plan revised**: Responsive breakpoints + map-card sync moved to Phase 1 (from Phase 3) per UX review
- **Status**: REVIEW — awaiting owner approval on 6 open questions

## 2026-03-29: Frontend framework migration — FastAPI + HTMX recommended (PROPOSAL)
- **Problem**: Streamlit's DOM structure makes precise CSS layout control extremely difficult. 530 lines of CSS hacks in `app.py` (lines 63–531) fight injected wrapper divs (`stLayoutWrapper`, `stVerticalBlockBorderWrapper`, `stElementContainer`). 5 CSS fix iterations in a single day for spacing issues. Framework injects unpredictable wrapper elements that vary by version.
- **Evaluation**: Compared 6 frameworks against 10 weighted requirements:
  - FastAPI + HTMX: 4.70/5 ⭐ (recommended)
  - Flask + Jinja2 + JS: 4.45/5
  - NiceGUI: 3.90/5
  - React + FastAPI: 3.85/5
  - Dash (Plotly): 3.10/5
  - Gradio: 2.30/5
- **Decision (proposed)**: Migrate to FastAPI + HTMX + Jinja2
- **Rationale**:
  - 100% HTML/CSS control — eliminates all 530 lines of CSS hacks
  - Existing HTML mockups (`user-dashboard.html`, `backoffice.html`) become Jinja2 templates directly
  - HTMX replaces 90% of JavaScript with HTML attributes (14KB, zero build step)
  - Backend (`src/`) has zero Streamlit imports — 100% reusable
  - FastAPI is async-native — SSE for real-time listing updates, auto-generated API docs
  - Dashboard + backoffice merge into one server (eliminates separate process + launchd plist)
  - Leaflet.js native — no wrapper library, full API access for price pills and clustering
- **Migration effort**: 25–33 hours across 4 phases
- **Risk mitigation**: Parallel running (Streamlit on 8501, FastAPI on 8000) during development; Streamlit backups for instant rollback
- **Status**: PROPOSAL — awaiting owner confirmation on framework choice, migration scope, port, theme, and priority
- **Plan**: [`plans/frontend-migration.md`](../../plans/frontend-migration.md)

## 2026-03-28: Dashboard sidebar removed — app isolation enforced
- **Problem**: Adding an "Admin →" link and "More Filters" to `app.py`'s sidebar required un-hiding Streamlit's `stHeader` element (which contains the sidebar toggle button). This broke the clean header-only layout — the `»` sidebar toggle appeared in the top-left corner.
- **Decision**: Remove ALL `st.sidebar` usage from `app.py`. Move "More Filters" to a main-area `st.expander()` with 4-column layout. Move "Admin →" link to a subtle `st.markdown()` at the bottom of the page. Restore `stHeader` hiding CSS.
- **Rationale**: `app.py` uses CSS to hide `stHeader` for a clean, full-width header. The sidebar toggle lives inside `stHeader`, making `st.sidebar` architecturally incompatible with this design. The sidebar was never visible to users (it was collapsed and hidden), so moving its content to the main area is a UX improvement.
- **New rule**: `app.py` must NEVER use `st.sidebar`. All filter/navigation UI must be in the main content area. This rule is documented in `lessonsLearned.md`, `shared.md`, and `AGENTS.md`.
- **Files modified**: `app.py` (CSS restored, sidebar removed, expander added, admin link moved)
- **Validation**: Code review APPROVED (0 P1, 0 P2, 2 P3 cleanup items fixed)

## 2026-03-28: Backoffice plan revised — user feedback incorporated
- **Context**: User reviewed the backoffice plan and provided decisions on open questions + a new requirement.
- **Decisions made**:
  1. **launchd auto-start: YES** — `com.sunnynest.backoffice.plist` is required (not optional). Moved from Phase 3 to Phase 1. Always available at `http://localhost:8502`.
  2. **Admin link in dashboard: YES, minimal** — Small "Admin →" text link at bottom of `app.py` sidebar. Not a button, not prominent.
  3. **Historical data in analytics: YES** — Listing Analytics queries include both active and inactive listings. `include_inactive` parameter added to relevant queries.
  4. **NEW: Settings page** — Notification settings management from backoffice UI (enable/disable toggle + recipient email input).
- **Settings persistence: config.yaml (not SQLite)**:
  - Rationale: `src/notifier.py` already reads from config.yaml — no pipeline changes needed. Single source of truth. Simpler than new SQLite table + migration.
  - Trade-off: File writes from web app are unusual, but acceptable for local single-user admin tool.
  - Safety: Backup config.yaml → config.yaml.bak before every write. Only 2 fields writable (email.enabled, email.recipient_email). SMTP credentials NOT editable from UI.
- **Security update**: Backoffice is no longer read-only — Settings page writes to config.yaml. Risk assessment added. Input validation + backup + limited write scope mitigate risks.
- **Impact**: Plan updated at `plans/backoffice.md`. New utility functions in `src/utils.py`. Minor change to `app.py` (admin link). `com.sunnynest.backoffice.plist` now Phase 1.

## 2026-03-28: Backoffice app — separate Streamlit app on port 8502
- **Problem**: Need an admin/backoffice app for listing analytics, API budget monitoring, and notification audit — separate from the user-facing dashboard.
- **Decision**: Create a separate Streamlit app (`backoffice.py`) running on port 8502, sharing the same SQLite database and `src/database.py` module.
- **Alternatives considered**:
  - Same app with `st.navigation` page routing (rejected: `app.py` already 1500+ lines, mixes admin and user concerns, user could accidentally navigate to admin pages)
  - Flask admin panel (rejected: adds Flask dependency, different tech stack, more code to write)
- **Key design choices**:
  - No authentication (local single-user app, localhost-only binding)
  - Read-only access to shared database (no write conflicts with scraper)
  - Auto-start via launchd (always available — user decision)
  - 5 pages: Dashboard KPIs, Listing Analytics, API Usage, Notifications, Settings
  - API counter was never in `app.py` — backoffice is the first and only UI for it
- **Impact**: New files: `backoffice.py`, `scripts/start-backoffice.sh`, `com.sunnynest.backoffice.plist`. Modified: `src/database.py` (10 new query functions), `src/utils.py` (settings persistence), `app.py` (admin link).
- **Plan**: [`plans/backoffice.md`](../../plans/backoffice.md)

## 2026-03-28: Cross-source deduplication — separate `listing_sources` table
- **Problem**: Same physical property appears on both Zillow and Craigslist with different `external_id` values. Current `(source, external_id)` unique constraint only prevents same-source duplicates, not cross-source duplicates.
- **Decision**: Create a new `listing_sources` table with a 1:N relationship from `listings`. Each source record (source, external_id, url) becomes a row in `listing_sources` instead of columns on `listings`.
- **Alternatives considered**:
  - JSON field on Listing (rejected: violates 1NF, hard to query/index)
  - `canonical_id` self-referential FK (rejected: ambiguous canonical selection, complex queries)
- **Matching algorithm**: Multi-signal scoring — normalized address (40pts) + ZIP (10) + price within 5% (15) + bedrooms (15) + bathrooms (10) + sqft within 10% (10). Threshold ≥ 75 = duplicate.
- **Merge strategy**: Existing listing is always canonical. New duplicate adds its source record and gap-fills NULL fields. User preferences (favorites, dislikes) are never overwritten.
- **Integration**: Step 6 in orchestrator pipeline, runs only for newly inserted listings. Candidate narrowing via ZIP + bedrooms index keeps it fast (< 100ms per run).
- **Impact**: `src/models.py` (new model), `src/database.py` (migration + queries), `src/orchestrator.py` (pipeline step), `app.py` (multi-source pills), `src/notifier.py` (email template). New file `src/dedup.py` recommended.
- **Plan**: [`plans/deduplication.md`](../../plans/deduplication.md)

## 2026-03-28: Remove house type filter — ingest only "house" type listings
- **Problem**: Users only care about house-type rentals; the property type filter dropdown added UI clutter and non-house listings polluted results
- **Decision**: Hardcode the system to only ingest "house" type listings at multiple layers:
  - Zillow API: restrict `homeType` parameter to `"Houses"` only (was `"Houses, Townhomes, Multi-family, Condos/Co-ops, Apartments"`)
  - Orchestrator: add post-normalization filter to skip any listing where `property_type != "house"` (defense-in-depth for Craigslist and future sources)
  - UI: remove the property type selectbox from the filter bar entirely
  - Config: reduce `property_types` list to `[house]` only
- **What was preserved**: `_PROPERTY_TYPE_MAP` dicts in scrapers (still normalize types correctly), `property_type` filter logic in `src/database.py` (useful for direct DB queries)
- **P2 fix**: Changed default property type in both scraper normalizers from `"apartment"` to `"house"` — prevents silent data loss for listings without explicit type metadata
- **Files modified**: app.py, src/scrapers/zillow_scraper.py, src/scrapers/craigslist_scraper.py, src/orchestrator.py, config.yaml, README.md
- **Validation**: Two-round review cycle — first review found 1 P2 (scraper default type causes silent data loss), fixed and re-validated. Final review: APPROVED, zero P1/P2 issues.

## 2026-03-27: Dashboard persistence via macOS launchd
- **Problem**: Dashboard (Streamlit on port 8501) died every night when laptop went to sleep
- **Root cause**: No process manager — app was started manually in a terminal
- **Decision**: Use macOS `launchd` Launch Agent (not systemd, pm2, or supervisor) because:
  - Native to macOS — no extra dependencies
  - Survives sleep/wake cycles and reboots
  - Auto-restarts on crash via `KeepAlive`
  - Runs as user-level agent (no root required)
- **Security**: Bind to `localhost` only (not `0.0.0.0`) since there's no authentication
- **Log rotation**: Weekly launchd job rotates logs >50MB to prevent unbounded disk growth
- **Files created**: `com.sunnynest.dashboard.plist`, `com.sunnynest.log-rotate.plist`, `scripts/start-dashboard.sh`, `scripts/install-service.sh`, `scripts/uninstall-service.sh`, `scripts/rotate-logs.sh`

## 2026-03-27: Comprehensive code review remediation
- **Problem**: Full codebase review revealed 3 critical, 12 major, and 14 minor issues
- **Key decisions**:
  - Move all secrets to environment variables (RAPIDAPI_KEY, SMTP_PASSWORD, NOTIFICATION_RECIPIENT)
  - Restore TLS certificate verification (was disabled with verify=False)
  - Apply html.escape() to all scraped data rendered in HTML (cards + map popups)
  - Rewrite stats queries to use SQL aggregates instead of loading all ORM objects
  - Add safety threshold (30% minimum) to mark_inactive() to prevent mass deactivation
  - Add time-based auto-reset (30 min) to geocoder circuit breaker
  - Bound geocode cache to 1024 entries with LRU eviction
  - Replace all datetime.utcnow() with datetime.now(timezone.utc)
  - Legacy notification functions delegate to EmailChannel with DeprecationWarning
- **Files modified**: app.py, config.yaml, src/database.py, src/geocoder.py, src/notifier.py, src/orchestrator.py, src/scheduler.py, scripts/insert_test_data.py, src/scrapers/zillow_scraper.py
- **Validation**: Two-round review cycle — first review found 1 remaining P2 (map popup XSS), fixed and re-validated. Final review: APPROVED, zero P1/P2 issues.

## 2026-03-27: Database analytics improvements — schema + data quality
- **Problem**: Listings DB lacked `days_on_market` field, price history had gaps when scraper didn't run daily, 33% of listings had NULL `listed_date`, and 3 listings had $0 prices polluting analytics.
- **Key decisions**:
  - Add `days_on_market` INTEGER column to listings table (computed after upsert from `listed_date` or `first_seen` fallback)
  - Implement price history gap-filling: carry-forward last known price for missing days, capped at MAX_GAP_DAYS=30
  - Scrapers return `None` for unparseable prices (not `0.0`); orchestrator filters out `None`/`0`/`0.0` before upsert
  - Removed `listed_date = date.today()` fallback from Craigslist scraper (was overwriting real dates on re-scrape)
  - Non-destructive schema migration via `ALTER TABLE ADD COLUMN` with try/except for idempotency
- **Files modified**: src/models.py, src/database.py, src/orchestrator.py, src/scrapers/craigslist_scraper.py, src/scrapers/zillow_scraper.py
- **Validation**: Two-round review cycle — first review found 3 P1 + 4 P2, all fixed and re-validated. Final review: APPROVED, zero P1/P2 issues.
