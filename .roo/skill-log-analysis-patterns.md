# Skill: Log Analysis Patterns (SunnyNest)

> **Tier 2 — loaded by Debug mode when reading logs.** Knowing where logs live and what common errors look like is half the battle.

## Purpose
Reduce time-to-first-clue when investigating issues. SunnyNest has multiple processes (scraper, notify, web, scheduler) writing to multiple files — knowing the layout saves minutes.

---

## Where SunnyNest Logs Live

All launchd-managed services write to `/tmp/sunnynest/` (NOT `~/Documents/zillow/logs/` — TCC blocks writes there; see [`lessonsLearned.md`](../docs/memory/shared/lessonsLearned.md:17)).

| Source | File | Plist | Purpose |
|--------|------|-------|---------|
| Scraper (daily 06:00) | `/tmp/sunnynest/scraper.log` | [`com.sunnynest.scraper.plist`](../com.sunnynest.scraper.plist:1) | Output of [`scripts/run-scraper.py`](../scripts/run-scraper.py:1) |
| Notify AM (daily 08:00) | `/tmp/sunnynest/notify-am.log` | [`com.sunnynest.notify-am.plist`](../com.sunnynest.notify-am.plist:1) | Email/WhatsApp notifications |
| Notify PM (daily 18:00) | `/tmp/sunnynest/notify-pm.log` | [`com.sunnynest.notify-pm.plist`](../com.sunnynest.notify-pm.plist:1) | Email/WhatsApp notifications |
| Dashboard (FastAPI/web) | `/tmp/sunnynest/dashboard.log` | [`com.sunnynest.dashboard.plist`](../com.sunnynest.dashboard.plist:1) | [`web/main.py`](../web/main.py:1) — uvicorn output |
| Backoffice (Streamlit) | `/tmp/sunnynest/backoffice.log` | [`com.sunnynest.backoffice.plist`](../com.sunnynest.backoffice.plist:1) | [`backoffice.py`](../backoffice.py:1) |
| Log rotation (weekly) | `/tmp/sunnynest/log-rotate.log` | [`com.sunnynest.log-rotate.plist`](../com.sunnynest.log-rotate.plist:1) | [`scripts/rotate-logs.sh`](../scripts/rotate-logs.sh:1) |

Archived rotations are gzipped alongside the live log: `*.log.YYYYMMDD-HHMMSS.gz` (kept 30 days).

---

## The Triage Pattern (do these in order)

### Step 1: Tail recent activity
```bash
tail -n 100 /tmp/sunnynest/scraper.log
```
Look at the last ~100 lines first. The freshest entries are usually the most relevant.

### Step 2: Grep for errors
```bash
grep -E "ERROR|WARN|Exception|Traceback" /tmp/sunnynest/scraper.log | tail -n 50
```
Filters noise. `tail` again because old errors aren't this run's problem.

### Step 3: Expand context around the error
```bash
grep -n "ERROR" /tmp/sunnynest/scraper.log | tail -n 5   # find line numbers
grep -B 5 -A 10 "ERROR" /tmp/sunnynest/scraper.log | less
```
Context above (`-B`) often shows the trigger; context below (`-A`) shows the impact / stack trace.

### Step 4: Stream live (if reproducing)
```bash
tail -F /tmp/sunnynest/scraper.log
# in another terminal:
.venv/bin/python scripts/run-scraper.py
```

---

## Common SunnyNest Error Signatures

| Signature in logs | Likely cause | Where to look next |
|-------------------|--------------|--------------------|
| `geopy.exc.GeocoderTimedOut` or `429 Too Many Requests` | Geocoder rate-limited (Nominatim 1 req/sec) | [`src/geocoder.py`](../src/geocoder.py:1) — check circuit breaker state |
| `401 Unauthorized` on RapidAPI | Expired/missing `RAPIDAPI_KEY` | `.env` file; [`lessonsLearned.md` "Silent Failure"](../docs/memory/shared/lessonsLearned.md:38) |
| `database is locked` | Concurrent writers to SQLite | Orphan process? `pgrep -fl sunnynest`; ensure only one scheduler running |
| `Run time was missed` (APScheduler) | Should NOT appear post-launchd migration | If present, an old APScheduler instance is still running — kill it |
| `Exit code: 78` (launchd) | TCC denied — log path under `~/Documents` | Check `StandardOutPath` / `StandardErrorPath` in plist; should be `/tmp/sunnynest/` |
| `[errno 8] nodename nor servname provided` | DNS / network down | `ping 8.8.8.8`; check VPN |
| `smtplib.SMTPAuthenticationError` | Bad / missing `SMTP_PASSWORD` | `.env`; admin dashboard System Health panel |
| Python `ModuleNotFoundError` from launchd run | Wrong Python or missing `PYTHONPATH` | Plist must use `.venv/bin/python` (or full Homebrew path); see [`lessonsLearned.md` macOS Python notes](../docs/memory/shared/lessonsLearned.md:71) |
| Empty log + service "exited" status | Process crashed before opening log; or wrong `WorkingDirectory` | `launchctl list \| grep sunnynest`; inspect `LastExitStatus` |

---

## Useful Commands (macOS-specific)

| Command | What it does |
|---------|--------------|
| `tail -F /tmp/sunnynest/scraper.log` | Follow log, including across truncation/rotation |
| `grep -B 5 -A 10 "ERROR" file.log` | 5 lines before, 10 after each match |
| `grep -c "ERROR" file.log` | Count of error lines |
| `awk 'NR > 1000' file.log` | Skip first 1000 lines (when log is huge) |
| `launchctl list \| grep sunnynest` | Status of all SunnyNest launchd services |
| `launchctl print gui/$(id -u)/com.sunnynest.scraper` | Detailed status of one service (last exit code, run count) |
| `log show --predicate 'process == "python3.14"' --last 1h` | macOS unified log (NOT `journalctl` — that's Linux) — useful when launchd never wrote any output |
| `pgrep -fl sunnynest` | List any running SunnyNest processes (find orphans) |

---

## Anti-Patterns (avoid)

- ❌ `cat large.log` — floods terminal, scrolls past actual error
- ❌ `grep ERROR | head` — `head` shows oldest, you want newest (`| tail`)
- ❌ Reading log without checking the timestamp range — you might be looking at yesterday's failure
- ❌ Stopping at the first `ERROR` line — the **last** error before silence is usually the cause; earlier errors may be downstream effects

---

## Quick Checklist

- [ ] Identified which log file matches the failing service
- [ ] Tailed recent lines, then greped for ERROR/WARN
- [ ] Expanded context (`-B`/`-A`) around the relevant match
- [ ] Cross-referenced the error signature against the table above
- [ ] If signature unknown, captured the exact error text for handoff to Code mode
