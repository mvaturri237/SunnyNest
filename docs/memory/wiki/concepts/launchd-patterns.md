# launchd Patterns

> macOS launchd is the correct tool for persistent background jobs — never embed schedulers inside web server processes. Use Homebrew Python to avoid TCC issues with ~/Documents/.

**Applies to:** [Scheduler (launchd)](../entities/scheduler-launchd.md), [Admin Dashboard](../entities/admin-dashboard.md)  
**Learned:** 2026-03-27 (process management), 2026-04-06 (APScheduler replacement), 2026-04-12 (TCC log path fix)
**Source:** `docs/memory/shared/lessonsLearned.md` — Streamlit process manager, TCC, APScheduler

## Pattern

Background scheduling must be **decoupled from web server lifecycle**. A web server's job is to serve requests, not to be a cron daemon. When the web server restarts, crashes, or goes idle, an embedded scheduler dies with it. On macOS, `launchd` with `StartCalendarInterval` is the correct tool — it's OS-native, survives reboots, and catches up on missed jobs when the Mac wakes from sleep.

## Rules

1. **Never put `BackgroundScheduler` or `AsyncIOScheduler` inside a web server process** — use OS scheduler (launchd/cron/systemd timers) or a dedicated job runner
2. **Use `KeepAlive: true`** for persistent services (dashboard, backoffice) — auto-restarts on crash
3. **Bind to `localhost` only** for personal tools without authentication
4. **Always add log rotation** — `StandardOutPath`/`StandardErrorPath` grow unbounded
5. **Use `exec` in wrapper scripts** so launchd tracks the real process PID
6. **Set `PYTHONUNBUFFERED=1`** for real-time log output from Python processes
7. **Use Homebrew Python** to avoid TCC issues (see below)

### TCC (Transparency, Consent, Control) Issues

- `~/Documents/`, `~/Desktop/`, `~/Downloads/` are TCC-protected on modern macOS (Catalina+)
- Processes spawned by launchd do NOT inherit the user's TCC grants
- Python venvs inside `~/Documents/` are doubly problematic: Python reads `pyvenv.cfg` at startup, triggering TCC
- **Fix (Python binary):** Use Homebrew Python binary directly (bypassing venv), set `PYTHONPATH` to venv's `site-packages` and `PYTHONDONTWRITEBYTECODE=1`
- **Fix (log paths):** `StandardOutPath`/`StandardErrorPath` must NOT point to TCC-protected directories. Use `/tmp/sunnynest/` instead of `~/Documents/zillow/logs/`. `WorkingDirectory` pointing to `~/Documents/` is fine (read access), but launchd cannot *write* log files there. Exit code 78 is the symptom of TCC denial.
- Homebrew Python path: `/opt/homebrew/Cellar/python@3.14/3.14.0_1/Frameworks/Python.framework/Versions/3.14/bin/python3.14` (or symlink `/opt/homebrew/opt/python@3.14/bin/python3.14` which survives minor version upgrades)

### macOS Python Command

- macOS does NOT provide a `python` command — only `python3`
- **ALL Python commands in this project MUST use `.venv/bin/python`** — never bare `python`, never bare `python3`
- The system `python3` does NOT have project dependencies

## Examples

- **APScheduler incident (2026-04-06):** 3-day scraping gap (April 3–5) because APScheduler's in-memory timer missed fire times when the laptop slept. Multiple web servers each ran their own scheduler — no single source of truth.
- **Fix:** 3 launchd plists + 2 standalone scripts, completely decoupled from web servers
- **Monitoring:** 30-day calendar heatmap on admin dashboard to detect future gaps

## Related

- [Scheduler (launchd)](../entities/scheduler-launchd.md) — the launchd implementation
- [Admin Dashboard](../entities/admin-dashboard.md) — scrape activity heatmap
- [Silent Failure Pattern](silent-failure-pattern.md) — no monitoring meant the gap went undetected
