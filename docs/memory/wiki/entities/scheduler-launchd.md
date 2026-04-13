# Scheduler (launchd)

> macOS launchd-native scheduling system with 3 plists for daily scraping and twice-daily notifications, replacing the unreliable APScheduler-in-web-server approach.

**Status:** Active  
**Owner files:** `com.sunnynest.scraper.plist`, `com.sunnynest.notify-am.plist`, `com.sunnynest.notify-pm.plist`, `scripts/run-scraper.py`, `scripts/run-notify.py`  
**Config:** Schedule defined in plist files (not `config.yaml`)  
**Added:** 2026-04-06  
**Last updated:** 2026-04-13

## Overview

The scheduler manages all background jobs (scraping and notifications) using macOS launchd Launch Agents. This replaced APScheduler which was embedded in web server processes (both Streamlit and FastAPI) and proved unreliable — a 3-day scraping gap (April 3–5) went undetected because APScheduler's in-memory timer missed fire times when the host process went idle or the laptop slept.

launchd is OS-native, survives reboots, and catches up on missed jobs when the Mac wakes from sleep via `StartCalendarInterval`.

## Architecture

- **3 launchd plists:**
  - `com.sunnynest.scraper.plist` — daily scrape at 06:00
  - `com.sunnynest.notify-am.plist` — morning notifications at 08:00
  - `com.sunnynest.notify-pm.plist` — evening notifications at 20:00
- **2 standalone scripts:**
  - `scripts/run-scraper.py` — imports and runs `ScraperOrchestrator.run_sync()` directly
  - `scripts/run-notify.py` — imports and runs `NotificationService.run()` directly
- **Complete process isolation:** Scripts are independent of web server lifecycle
- **Homebrew Python:** Plists use Homebrew Python binary to avoid TCC issues with `~/Documents/` (see [launchd Patterns](../concepts/launchd-patterns.md))
- **Monitoring:** 30-day calendar heatmap on admin dashboard with per-source gap detection (green/yellow/red cells)

## Current State

- **Working:** All 6 plists installed and active, all exit code 0 (requires `scripts/install-service.sh` to activate)
- **Dashboard plist migrated:** `com.sunnynest.dashboard.plist` now runs `uvicorn web.main:app` on port 8000 (was Streamlit on 8501)
- **TCC log path fix complete:** ALL plists now write logs to `/tmp/sunnynest/` instead of `~/Documents/zillow/logs/` to avoid TCC write denial (exit code 78). Support scripts (`rotate-logs.sh`, `install-service.sh`, `uninstall-service.sh`) also updated.
- **Notify AM/PM logs differentiated:** Previously both wrote to `notify-stdout.log`; now `notify-am-stdout.log` and `notify-pm-stdout.log`
- **APScheduler removed:** Removed from both `web/main.py` (FastAPI) and `app.py` (Streamlit)
- **`src/scheduler.py` deprecated:** Contains deprecation notice; manual sync button (`POST /admin/sync`) still works
- **macOS-only:** Acceptable since this is a personal tool running on a single Mac

## Configuration

Schedule is defined in plist files, not `config.yaml`. The `config.yaml` schedule section is documentation only:

| Plist | Schedule | Script |
|-------|----------|--------|
| `com.sunnynest.scraper` | Daily 06:00 | `scripts/run-scraper.py` |
| `com.sunnynest.notify-am` | Daily 08:00 | `scripts/run-notify.py` |
| `com.sunnynest.notify-pm` | Daily 20:00 | `scripts/run-notify.py` |

Additional launchd services:
| Plist | Purpose |
|-------|---------|
| `com.sunnynest.dashboard` | FastAPI dashboard via uvicorn (port 8000) |
| `com.sunnynest.backoffice` | Backoffice process (port 8502) |
| `com.sunnynest.log-rotate` | Weekly log rotation |

## Key Files

| File | Purpose |
|------|---------|
| `com.sunnynest.scraper.plist` | Scraper schedule definition |
| `com.sunnynest.notify-am.plist` | Morning notification schedule |
| `com.sunnynest.notify-pm.plist` | Evening notification schedule |
| `scripts/run-scraper.py` | Standalone scraper runner |
| `scripts/run-notify.py` | Standalone notification runner |
| `scripts/install-service.sh` | Install all launchd agents |
| `scripts/uninstall-service.sh` | Uninstall all launchd agents |
| `src/scheduler.py` | Deprecated APScheduler module |

## History

- [2026-04-13] TCC exit code 78 fix applied to ALL remaining plists (scraper, notify-am, notify-pm, backoffice, log-rotate). All `StandardOutPath`/`StandardErrorPath` moved from `~/Documents/zillow/logs/` to `/tmp/sunnynest/`. Notify AM/PM logs differentiated. Support scripts (`rotate-logs.sh`, `install-service.sh`, `uninstall-service.sh`) updated. Log-rotate stderr bug fixed (was pointing to stdout file). All 6 agents now exit code 0. Manual scraper trigger confirmed working (39 listings).
- [2026-04-12] Dashboard plist migrated from Streamlit (port 8501) to FastAPI/uvicorn (port 8000). Log paths moved to `/tmp/sunnynest/` to fix TCC exit code 78. Install script messages updated.
- [2026-04-06] Cloud scheduler evaluation complete — GitHub Actions + git-committed DB recommended for cloud
- [2026-04-06] APScheduler replaced with launchd — 3 new plists, 2 standalone scripts
- [2026-04-06] Admin monitoring: 30-day calendar heatmap added to detect scraping gaps
- [2026-03-29] Port cleanup — killed rogue instances, installed launchd services for dashboard/backoffice
- [2026-03-27] Initial launchd setup for dashboard persistence (`com.sunnynest.dashboard.plist`)

## Related

- [Orchestrator](orchestrator.md) — `run_sync()` called by scraper script
- [Notification System](notification-system.md) — `run()` called by notify script
- [Admin Dashboard](admin-dashboard.md) — scrape activity heatmap monitoring
- [Config (YAML)](config-yaml.md) — schedule section (documentation only)
- [launchd Patterns](../concepts/launchd-patterns.md) — TCC, Homebrew Python, process management
- [Plan: Scheduler Fix](../../../../plans/scheduler-fix.md) — migration plan
- [Plan: Cloud Scheduler](../../../../plans/cloud-scheduler.md) — cloud deployment evaluation
