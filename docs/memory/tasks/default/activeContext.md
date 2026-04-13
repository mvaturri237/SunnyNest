# Active Context

## Current Focus
TCC exit code 78 fix — all launchd agents now writing logs to `/tmp/sunnynest/`, scraper running again.

## Recent Changes (last 3)
- [2026-04-13] TCC exit code 78 fix for all remaining launchd plists — scraper, notify-am/pm, backoffice, log-rotate all moved from `~/Documents/zillow/logs/` to `/tmp/sunnynest/`. Support scripts updated. All 6 agents exit code 0. Scraper confirmed working (39 listings) → [log entry](../../wiki/log.md#tcc-exit-code-78-fix--all-remaining-launchd-plists)
- [2026-04-13] Dashboard cosmetic changes — filter bar left-aligned (removed `max-width`/`margin: 0 auto`), map zoom 13→12, marker clustering removed (`L.markerClusterGroup` → `L.layerGroup`, MarkerCluster CDN removed) → [log entry](../../wiki/log.md#dashboard-cosmetic-changes--left-align-filter-bar-zoom-out-map-remove-clustering)
- [2026-04-12] Dashboard plist migrated to FastAPI/uvicorn — `com.sunnynest.dashboard.plist` updated from `streamlit run app.py` (port 8501) to `uvicorn web.main:app` (port 8000). Log paths moved from `~/Documents/zillow/logs/` to `/tmp/sunnynest/` to fix TCC exit code 78. All stale `localhost:8501` references updated across codebase → [log entry](../../wiki/log.md#dashboard-plist-migrated-to-fastapiuvicorn)

## Action Items
- Update `README.md` dashboard URL from `localhost:8501` to `sunnynest:8000`
- Copy `docs/temp/roo-updates/skill-memory-manager.md` → `.roo/skill-memory-manager.md`
- Copy `docs/temp/roo-updates/skill-wiki-lint.md` → `.roo/skill-wiki-lint.md` (new file)
- Apply edits from `docs/temp/roo-updates/roomodes-edits.md` to `.roomodes`
- Set `SMTP_PASSWORD` in `.env` for email notifications

## Full History
→ See [wiki/log.md](../../wiki/log.md)

## Entity Index
→ See [wiki/index.md](../../wiki/index.md)
