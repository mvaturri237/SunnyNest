# Reliable Daily Scheduler + Admin API Call Monitoring — Implementation Plan

## Problem Statement

The SunnyNest scraper scheduler is unreliable. A **3-day gap** (April 3–5, 2026) was discovered where no scraping ran at all. Root causes:

1. **Duplicate scheduler instances** — Both [`app.py`](../app.py:548) (old Streamlit) and [`web/main.py`](../web/main.py:119) (new FastAPI) create their own [`ScrapeScheduler`](../src/scheduler.py:26) instances via APScheduler's `BackgroundScheduler`
2. **Process sleep/idle** — When the host process (Streamlit or Uvicorn) goes idle or the laptop sleeps, APScheduler's in-memory scheduler misses fire times and logs "Run time was missed" errors
3. **No gap detection** — The admin dashboard has no way to visualize which days had successful scrapes vs. gaps
4. **Embedded scheduler anti-pattern** — Scheduling logic is coupled to web server lifecycle; if the web server restarts, the scheduler restarts; if it crashes, scraping stops

---

## Architecture Decision: launchd-Native Scheduling

### Options Evaluated

| Option | Pros | Cons | Verdict |
|--------|------|------|---------|
| **(a) macOS launchd plist** | OS-native, survives reboots, runs even when no web server is up, catches up on missed jobs (`StartCalendarInterval`), already proven in project (log-rotate, backoffice) | macOS-only, no cross-platform | ✅ **Selected** |
| **(b) Standalone Python daemon** | Cross-platform, can use APScheduler with persistent job store | Still an in-process scheduler — same sleep/idle problem unless using a job store; adds complexity | ❌ Rejected |
| **(c) cron job** | Simple, well-understood | macOS deprecated cron in favor of launchd; no built-in catch-up for missed jobs; env var handling is awkward | ❌ Rejected |
| **(d) Keep APScheduler in FastAPI** | No new infrastructure | Current approach — proven unreliable; same root cause | ❌ Rejected |

### Why launchd Wins

1. **Already proven** — [`com.sunnynest.backoffice.plist`](../com.sunnynest.backoffice.plist) and [`com.sunnynest.log-rotate.plist`](../com.sunnynest.log-rotate.plist) already use launchd successfully
2. **Catch-up semantics** — `StartCalendarInterval` with no `KeepAlive` means launchd fires the job at the scheduled time; if the Mac was asleep, it fires as soon as it wakes up
3. **Process isolation** — The scraper runs as a standalone Python script, completely decoupled from web server lifecycle
4. **Logging** — `StandardOutPath`/`StandardErrorPath` capture all output automatically
5. **No new dependencies** — No need for Redis, Celery, or persistent APScheduler job stores
6. **TCC handling** — We already know how to handle the `~/Documents/` TCC issue (use Homebrew Python directly with `PYTHONPATH` pointing to venv site-packages, per [`lessonsLearned.md`](../docs/memory/shared/lessonsLearned.md:17))

### What Happens to APScheduler?

**Remove APScheduler from both web servers.** The scheduler will be fully owned by launchd. The FastAPI and Streamlit apps become pure web servers with no scheduling responsibility.

- [`web/main.py`](../web/main.py:119) — Remove `ScrapeScheduler` from lifespan
- [`app.py`](../app.py:548) — Remove `ScrapeScheduler` from session state
- [`src/scheduler.py`](../src/scheduler.py) — **Keep the file** but deprecate `ScrapeScheduler` class; the new standalone script will import [`ScraperOrchestrator`](../src/orchestrator.py:32) and [`NotificationService`](../src/notifier.py) directly
- `apscheduler` can be removed from [`requirements.txt`](../requirements.txt) after migration is confirmed stable

---

## Part 1: Reliable Daily Scheduler

### 1.1 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  macOS launchd                                                  │
│                                                                 │
│  com.sunnynest.scraper        ← NEW: daily scrape job           │
│  ├── StartCalendarInterval: 06:00 local time                    │
│  ├── Runs: scripts/run-scraper.sh                               │
│  └── Logs: logs/scraper-{stdout,stderr}.log                     │
│                                                                 │
│  com.sunnynest.notify-am      ← NEW: morning notification       │
│  ├── StartCalendarInterval: 08:00 local time (Asia/Jerusalem)   │
│  ├── Runs: scripts/run-notify.sh                                │
│  └── Logs: logs/notify-{stdout,stderr}.log                      │
│                                                                 │
│  com.sunnynest.notify-pm      ← NEW: evening notification       │
│  ├── StartCalendarInterval: 20:00 local time                    │
│  ├── Runs: scripts/run-notify.sh                                │
│  └── Logs: logs/notify-{stdout,stderr}.log                      │
│                                                                 │
│  com.sunnynest.dashboard      ← EXISTING: old Streamlit (8501)  │
│  com.sunnynest.backoffice     ← EXISTING: old Streamlit (8502)  │
│  com.sunnynest.log-rotate     ← EXISTING: weekly log rotation   │
│                                                                 │
│  (FastAPI at :8000 runs via manual uvicorn — no scheduler)      │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 New Files

#### `scripts/run-scraper.py` — Standalone scraper entry point

```python
#!/usr/bin/env python3
"""Standalone scraper entry point — called by launchd daily.

Runs all scrapers via ScraperOrchestrator.run_sync_blocking(),
logs results, and exits. No web server, no APScheduler.
"""
import asyncio
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from src.database import init_db
from src.orchestrator import ScraperOrchestrator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("sunnynest.scraper-job")


def main() -> int:
    logger.info("=== Daily scrape starting at %s ===", datetime.now(timezone.utc).isoformat())
    init_db()
    orchestrator = ScraperOrchestrator()
    try:
        summary = orchestrator.run_sync_blocking()
        logger.info("Scrape complete: %s", summary)
        return 0
    except Exception:
        logger.exception("Scrape failed with unhandled error")
        return 1


if __name__ == "__main__":
    sys.exit(main())
```

#### `scripts/run-notify.py` — Standalone notification entry point

```python
#!/usr/bin/env python3
"""Standalone notification entry point — called by launchd twice daily."""
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from src.database import init_db
from src.notifier import EmailChannel, NotificationService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("sunnynest.notify-job")


def main() -> int:
    logger.info("=== Notification check at %s ===", datetime.now(timezone.utc).isoformat())
    init_db()
    service = NotificationService(channels=[EmailChannel()])
    try:
        result = service.run()
        logger.info("Notification result: %s", result)
        return 0
    except Exception:
        logger.exception("Notification check failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
```

#### `scripts/run-scraper.sh` — Shell wrapper for launchd

```bash
#!/usr/bin/env bash
# run-scraper.sh — Wrapper for launchd to run the daily scraper
set -euo pipefail
cd /Users/mvaturri/Documents/zillow
exec .venv/bin/python scripts/run-scraper.py
```

> **Note:** Uses `.venv/bin/python` directly. If TCC blocks access to `~/Documents/`, fall back to the Homebrew Python pattern from [`com.sunnynest.dashboard.plist`](../com.sunnynest.dashboard.plist:12) (Homebrew Python + `PYTHONPATH` to venv site-packages). The plist already handles this — see §1.3.

#### `scripts/run-notify.sh` — Shell wrapper for notifications

```bash
#!/usr/bin/env bash
# run-notify.sh — Wrapper for launchd to run notification check
set -euo pipefail
cd /Users/mvaturri/Documents/zillow
exec .venv/bin/python scripts/run-notify.py
```

### 1.3 New launchd Plists

#### `com.sunnynest.scraper.plist` — Daily scrape at 06:00

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.sunnynest.scraper</string>

    <key>ProgramArguments</key>
    <array>
        <string>/opt/homebrew/opt/python@3.14/bin/python3.14</string>
        <string>scripts/run-scraper.py</string>
    </array>

    <key>WorkingDirectory</key>
    <string>/Users/mvaturri/Documents/zillow</string>

    <!-- Run daily at 06:00 local time -->
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>6</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>

    <key>StandardOutPath</key>
    <string>/Users/mvaturri/Documents/zillow/logs/scraper-stdout.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/mvaturri/Documents/zillow/logs/scraper-stderr.log</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/opt/python@3.14/bin:/Users/mvaturri/Documents/zillow/.venv/bin:/usr/local/bin:/usr/bin:/bin</string>
        <key>PYTHONPATH</key>
        <string>/Users/mvaturri/Documents/zillow/.venv/lib/python3.14/site-packages</string>
        <key>PYTHONUNBUFFERED</key>
        <string>1</string>
        <key>PYTHONDONTWRITEBYTECODE</key>
        <string>1</string>
    </dict>
</dict>
</plist>
```

**Key design choices:**
- **`StartCalendarInterval`** (not `StartInterval`) — fires at a specific wall-clock time; if the Mac was asleep at 06:00, launchd fires the job when it wakes up
- **No `KeepAlive`** — this is a run-once job, not a persistent daemon; it runs, completes, and exits
- **06:00 local time** — runs before the user wakes up; results are ready for the 08:00 notification
- **Uses Homebrew Python directly** — avoids TCC issues with venv inside `~/Documents/`

#### `com.sunnynest.notify-am.plist` — Morning notification at 08:00

Same structure as scraper plist but:
- `Label`: `com.sunnynest.notify-am`
- `ProgramArguments`: `scripts/run-notify.py`
- `StartCalendarInterval`: `Hour=8, Minute=0`
- Log files: `logs/notify-stdout.log`, `logs/notify-stderr.log`

#### `com.sunnynest.notify-pm.plist` — Evening notification at 20:00

Same structure but:
- `Label`: `com.sunnynest.notify-pm`
- `StartCalendarInterval`: `Hour=20, Minute=0`
- Same log files (appended)

### 1.4 Configuration

Update [`config.yaml`](../config.yaml:21) to reflect the new scheduling model:

```yaml
# Scheduler — launchd-native (APScheduler removed)
schedule:
  # These values are documentation only — actual schedule is in launchd plists
  scrape_time: "06:00"        # com.sunnynest.scraper.plist
  notify_times: ["08:00", "20:00"]  # com.sunnynest.notify-{am,pm}.plist
  timezone: "Asia/Jerusalem"
```

The `interval_hours: 6` key becomes obsolete since we're switching from interval-based to calendar-based scheduling.

### 1.5 Files to Modify

| File | Action | Details |
|------|--------|---------|
| [`scripts/run-scraper.py`](../scripts/) | **Create** | Standalone scraper entry point |
| [`scripts/run-notify.py`](../scripts/) | **Create** | Standalone notification entry point |
| [`scripts/run-scraper.sh`](../scripts/) | **Create** | Shell wrapper for launchd |
| [`scripts/run-notify.sh`](../scripts/) | **Create** | Shell wrapper for launchd |
| [`com.sunnynest.scraper.plist`](../) | **Create** | Daily scrape launchd agent |
| [`com.sunnynest.notify-am.plist`](../) | **Create** | Morning notification launchd agent |
| [`com.sunnynest.notify-pm.plist`](../) | **Create** | Evening notification launchd agent |
| [`web/main.py`](../web/main.py:97) | **Modify** | Remove `ScrapeScheduler` from lifespan — FastAPI becomes a pure web server |
| [`app.py`](../app.py:548) | **Modify** | Remove `ScrapeScheduler` from session state |
| [`config.yaml`](../config.yaml:21) | **Modify** | Update `schedule` section to document launchd times |
| [`scripts/install-service.sh`](../scripts/install-service.sh) | **Modify** | Add new plists to install/unload/load cycle |
| [`scripts/uninstall-service.sh`](../scripts/uninstall-service.sh) | **Modify** | Add new plists to uninstall cycle |
| [`scripts/rotate-logs.sh`](../scripts/rotate-logs.sh) | **Modify** | Add `scraper-*.log` and `notify-*.log` to rotation |
| [`src/scheduler.py`](../src/scheduler.py) | **Deprecate** | Add deprecation notice; keep for backward compat until old Streamlit is fully retired |

---

## Part 2: Admin API Call Monitoring Section

### 2.1 Goal

Add a **"📡 Scrape Activity"** section to the admin dashboard at [`/admin/`](../web/routes/admin.py:131) that makes it trivially easy to spot gaps in scraping activity — like the 3-day gap that triggered this plan.

### 2.2 Design: Calendar Heatmap Grid

A **30-day calendar grid** (not a table, not a chart) showing one cell per day, color-coded by scrape activity:

```
📡 Scrape Activity — Last 30 Days

  Apr 06  Apr 05  Apr 04  Apr 03  Apr 02  Apr 01  Mar 31
  [🟢]    [🔴]    [🔴]    [🔴]    [🟢]    [🟢]    [🟢]

  Mar 30  Mar 29  Mar 28  Mar 27  Mar 26  Mar 25  Mar 24
  [🟢]    [🟢]    [🟢]    [🟢]    [🟡]    [🟢]    [🟢]

  Mar 23  Mar 22  Mar 21  Mar 20  Mar 19  Mar 18  Mar 17
  [🟢]    [🟢]    [🟢]    [🟢]    [🟢]    [🟢]    [🟢]

  Mar 16  Mar 15  Mar 14  Mar 13  Mar 12  Mar 11  Mar 10
  [🟢]    [🟢]    [🟢]    [🟢]    [🟢]    [🟢]    [🟢]

  Mar 09  Mar 08  Mar 07
  [🟢]    [🟢]    [🟢]

Legend: 🟢 All sources OK  🟡 Partial (some sources missing)  🔴 No activity  ⬜ Future
```

**Color logic per cell:**
- **Green** (`activity--ok`) — All configured sources (zillow, craigslist, realtor) have ≥1 API call that day
- **Yellow** (`activity--partial`) — Some sources have calls, but not all
- **Red** (`activity--gap`) — Zero API calls across all sources
- **Gray** (`activity--future`) — Future dates (today's cell is green/yellow/red based on current data)

**Tooltip on hover:** Shows per-source breakdown, e.g., "Zillow: 3 calls (200 OK) · Craigslist: 0 · Realtor: 2 calls (200 OK)"

### 2.3 Data Model

The existing [`api_call_log`](../src/models.py:224) table already has everything needed:
- `service` — source name (zillow, craigslist, realtor)
- `called_at` — timestamp
- `status_code` — HTTP status

**New database function needed:**

```python
def get_scrape_activity_grid(days: int = 30) -> list[dict]:
    """Return per-day, per-source API call summary for the last N days.

    Returns:
        List of dicts, one per day (most recent first):
        [
            {
                "date": "2026-04-06",
                "sources": {
                    "zillow": {"calls": 3, "success": 3, "errors": 0},
                    "craigslist": {"calls": 0, "success": 0, "errors": 0},
                    "realtor": {"calls": 2, "success": 2, "errors": 0},
                },
                "status": "partial",  # "ok" | "partial" | "gap"
            },
            ...
        ]
    """
```

**SQL approach:** Single query with `GROUP BY date(called_at), service` over the last 30 days, then fill in missing dates with zero counts in Python.

> **Note on Craigslist:** Craigslist scraping uses HTML scraping, not API calls, so it won't appear in `api_call_log`. Two options:
> 1. **Option A:** Log a synthetic API call entry for Craigslist scrapes (service="craigslist", endpoint="scrape", status_code=200)
> 2. **Option B:** Use `listings.last_seen` as a proxy — if any Craigslist listing was seen today, scraping ran
>
> **Recommendation:** Option A — add a `log_api_call("craigslist", "html-scrape", 200)` call in [`CraigslistScraper`](../src/scrapers/craigslist_scraper.py) after a successful scrape. This keeps the monitoring data source consistent.

### 2.4 UI Placement

The new section goes on [`web/templates/admin/dashboard.html`](../web/templates/admin/dashboard.html) **between** the KPI cards and the "Listings by Source" section:

```
📊 Dashboard
├── 🩺 System Health          (existing)
├── KPI Cards                  (existing)
├── 📡 Scrape Activity         ← NEW (calendar heatmap)
├── Listings by Source         (existing)
└── Recent Listings            (existing)
```

### 2.5 Template Structure

```html
<!-- Scrape Activity Heatmap -->
<div class="section">
    <h2 class="section-title">📡 Scrape Activity — Last 30 Days</h2>
    <div class="activity-legend">
        <span class="legend-item"><span class="activity-dot activity--ok"></span> All sources</span>
        <span class="legend-item"><span class="activity-dot activity--partial"></span> Partial</span>
        <span class="legend-item"><span class="activity-dot activity--gap"></span> No activity</span>
    </div>
    <div class="activity-grid">
        {% for day in scrape_activity %}
        <div class="activity-cell activity--{{ day.status }}"
             title="{{ day.date }}&#10;{% for src, data in day.sources.items() %}{{ src }}: {{ data.calls }} calls{% if not loop.last %}&#10;{% endif %}{% endfor %}">
            <span class="activity-date">{{ day.date[5:] }}</span>
        </div>
        {% endfor %}
    </div>
</div>
```

### 2.6 CSS

```css
/* --- Scrape Activity Heatmap --- */
.activity-grid {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    gap: 6px;
    max-width: 560px;
}

.activity-cell {
    aspect-ratio: 1;
    border-radius: var(--admin-radius-sm);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    font-size: 11px;
    color: var(--admin-text-muted);
    cursor: default;
    position: relative;
    min-height: 48px;
}

.activity-cell:hover {
    box-shadow: var(--admin-shadow-hover);
    z-index: 1;
}

.activity--ok     { background: var(--admin-success-bg); border: 1px solid #bbf7d0; }
.activity--partial { background: var(--admin-warning-bg); border: 1px solid #fde68a; }
.activity--gap    { background: var(--admin-danger-bg); border: 1px solid #fecaca; }
.activity--future { background: #f1f5f9; border: 1px solid #e2e8f0; opacity: 0.5; }

.activity-date {
    font-weight: 600;
    font-size: 12px;
    color: var(--admin-text-secondary);
}

.activity-legend {
    display: flex;
    gap: 16px;
    margin-bottom: 12px;
    font-size: 13px;
    color: var(--admin-text-secondary);
}

.activity-dot {
    display: inline-block;
    width: 12px;
    height: 12px;
    border-radius: 3px;
    margin-right: 4px;
    vertical-align: middle;
}

.legend-item {
    display: flex;
    align-items: center;
    gap: 4px;
}
```

### 2.7 Files to Create/Modify

| File | Action | Details |
|------|--------|---------|
| [`src/database.py`](../src/database.py) | **Modify** | Add `get_scrape_activity_grid(days=30)` function |
| [`web/routes/admin.py`](../web/routes/admin.py:131) | **Modify** | Call `get_scrape_activity_grid()` in `admin_dashboard()`, pass to template |
| [`web/templates/admin/dashboard.html`](../web/templates/admin/dashboard.html) | **Modify** | Add scrape activity heatmap section after KPI cards |
| [`web/static/css/admin.css`](../web/static/css/admin.css) | **Modify** | Add activity grid CSS |
| [`src/scrapers/craigslist_scraper.py`](../src/scrapers/craigslist_scraper.py) | **Modify** | Add `log_api_call("craigslist", ...)` after successful scrape for monitoring consistency |

---

## Part 3: Migration Plan

### Phase 1: Add Monitoring (No Risk)

1. Implement `get_scrape_activity_grid()` in [`src/database.py`](../src/database.py)
2. Add the heatmap section to [`web/templates/admin/dashboard.html`](../web/templates/admin/dashboard.html)
3. Add CSS to [`web/static/css/admin.css`](../web/static/css/admin.css)
4. Wire up in [`web/routes/admin.py`](../web/routes/admin.py:131)
5. Add Craigslist scrape logging to [`src/scrapers/craigslist_scraper.py`](../src/scrapers/craigslist_scraper.py)
6. **Deploy and verify** — the heatmap should immediately show the April 3–5 gap in red

### Phase 2: Create Standalone Scripts (No Risk)

1. Create [`scripts/run-scraper.py`](../scripts/)
2. Create [`scripts/run-notify.py`](../scripts/)
3. Create shell wrappers
4. **Test manually:** `.venv/bin/python scripts/run-scraper.py` — verify it runs a full scrape cycle
5. **Test manually:** `.venv/bin/python scripts/run-notify.py` — verify it runs a notification check

### Phase 3: Install launchd Agents (Parallel Run)

1. Create the 3 new plist files
2. Update [`scripts/install-service.sh`](../scripts/install-service.sh) to include new plists
3. Update [`scripts/uninstall-service.sh`](../scripts/uninstall-service.sh)
4. Update [`scripts/rotate-logs.sh`](../scripts/rotate-logs.sh) to include new log files
5. Run `scripts/install-service.sh` to install all agents
6. **Run in parallel for 3–5 days** — both APScheduler (in FastAPI) and launchd will fire; the orchestrator's upsert logic is idempotent, so duplicate runs are harmless
7. **Monitor the heatmap** — verify launchd jobs show up as green cells every day

### Phase 4: Remove APScheduler (After Verification)

1. Remove `ScrapeScheduler` import and usage from [`web/main.py`](../web/main.py:97) lifespan
2. Remove `ScrapeScheduler` import and usage from [`app.py`](../app.py:548) session state
3. Add deprecation notice to [`src/scheduler.py`](../src/scheduler.py)
4. Update [`config.yaml`](../config.yaml:21) schedule section
5. Optionally remove `apscheduler` from [`requirements.txt`](../requirements.txt) (only after confirming nothing else imports it)

### Rollback Plan

If launchd scheduling fails:
1. Re-enable APScheduler in [`web/main.py`](../web/main.py:119) lifespan (revert the removal)
2. Unload the launchd agents: `launchctl unload ~/Library/LaunchAgents/com.sunnynest.scraper.plist`
3. The monitoring heatmap stays regardless — it's read-only and always useful

---

## Estimated Effort

| Phase | Effort | Risk |
|-------|--------|------|
| Phase 1: Monitoring | 3–4 hours | None — read-only addition |
| Phase 2: Standalone scripts | 1–2 hours | None — not yet scheduled |
| Phase 3: launchd agents | 2–3 hours | Low — parallel run with existing scheduler |
| Phase 4: Remove APScheduler | 1 hour | Low — after 3–5 days of verified parallel run |
| **Total** | **7–10 hours** | |

---

## Open Questions

1. **Scrape time:** 06:00 local time is proposed. Should it be different? (Must run before the 08:00 notification)
2. **Craigslist logging:** Should we add `log_api_call()` to Craigslist scraper, or use `last_seen` as a proxy? (Recommendation: add logging for consistency)
3. **Old Streamlit retirement:** Should we plan to fully retire [`app.py`](../app.py) and [`com.sunnynest.dashboard.plist`](../com.sunnynest.dashboard.plist) now that FastAPI is the primary dashboard? This would eliminate one source of duplicate schedulers immediately.
4. **Notification timezone:** The plists use local system time. If the Mac's timezone is set to `Asia/Jerusalem`, the 08:00/20:00 plists fire at the right Israel time. Confirm the Mac's timezone is set correctly.
5. **Manual sync button:** The existing `POST /admin/sync` button on the admin dashboard should continue to work independently of the scheduler — it calls [`ScraperOrchestrator`](../src/orchestrator.py:32) directly, not through the scheduler.
