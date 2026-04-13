# Cloud-Based Scheduler Evaluation (Free Tier)

## Problem Statement

The daily scraper currently runs via macOS launchd (`com.sunnynest.scraper.plist`) at 06:00 local time. This requires the laptop to be powered on and awake. If the laptop is closed or off, the scrape is missed — as happened during the April 3–5 gap that prompted the launchd migration.

**Goal:** Evaluate free cloud options to run `scripts/run-scraper.py` daily without depending on the laptop being on.

---

## The SQLite Challenge

This is the central constraint. The database is a local SQLite file at `data/listings.db`. Every option must answer: **where does the data go?**

| Approach | Description | Complexity |
|----------|-------------|------------|
| **A. Git-committed DB** | Scraper runs in CI, commits `listings.db` back to the repo. Local dashboard pulls via `git pull`. | Low — but DB in git is an anti-pattern (binary diffs, merge conflicts, repo bloat) |
| **B. Artifact storage** | Scraper runs in CI, uploads DB as a build artifact. Local machine downloads it on a schedule or on-demand. | Medium — requires a download step; artifacts expire (90 days on GitHub) |
| **C. Cloud DB migration** | Replace SQLite with a free cloud database (Turso, Supabase, PlanetScale). Both scraper and dashboard connect to it. | High — requires code changes to `src/database.py`, connection string management, latency considerations |
| **D. Hybrid: cloud scrape → JSON → local import** | Scraper runs in cloud, writes results to a JSON file (committed or artifact). Local import script merges into SQLite. | Medium — preserves local SQLite; needs a new import/merge script |

---

## Option 1: GitHub Actions + Git-Committed DB

**How it works:** A GitHub Actions workflow runs `scripts/run-scraper.py` on a cron schedule. After scraping, it commits the updated `listings.db` back to the repo. The local machine does `git pull` to get fresh data.

### Pros
- ✅ **Zero new services** — uses existing GitHub repo
- ✅ **Free tier is generous** — 2,000 min/month (private) or unlimited (public); a single scrape takes ~2–5 min
- ✅ **Secrets management built-in** — `RAPIDAPI_KEY`, `SMTP_PASSWORD` go in GitHub repo Settings → Secrets
- ✅ **Cron scheduling built-in** — `schedule: cron: '0 3 * * *'` (UTC) ≈ 06:00 Israel
- ✅ **Notifications still work** — the scraper script already calls `NotificationService` after scraping
- ✅ **Minimal code changes** — `run-scraper.py` works as-is; just needs a workflow YAML

### Cons
- ❌ **Binary file in git** — `listings.db` is ~500KB now but will grow; git stores full copies (no delta compression for binary)
- ❌ **Merge conflicts** — if you edit locally AND the cloud scrapes, `git pull` will conflict on the binary DB
- ❌ **GitHub cron is imprecise** — can be delayed 5–60 minutes during high load
- ❌ **Repo must be private** — DB contains listing data; API keys are in secrets (safe), but the DB itself shouldn't be public
- ⚠️ **Dashboard reads stale data** — until you `git pull`, the local dashboard shows yesterday's data

### SQLite handling
Approach **A** (git-committed DB). Simple but fragile. Works if you treat the cloud as the sole writer and never modify the DB locally (read-only local copy).

### Effort: ~2 hours
- Create `.github/workflows/scrape.yml`
- Add secrets to GitHub repo settings
- Add `data/listings.db` to tracked files (remove from `.gitignore`)
- Test the workflow

---

## Option 2: GitHub Actions + Turso (Cloud SQLite)

**How it works:** Migrate from local SQLite to [Turso](https://turso.tech) — a free hosted SQLite-compatible database (libSQL). The scraper runs in GitHub Actions and writes directly to Turso. The local FastAPI dashboard also reads from Turso. No file syncing needed.

### Pros
- ✅ **True cloud database** — no file syncing, no merge conflicts, no stale data
- ✅ **SQLite-compatible** — Turso uses libSQL (a fork of SQLite); SQLAlchemy works via `libsql-client` or `sqlalchemy-libsql`
- ✅ **Generous free tier** — 9 GB storage, 500 databases, 25M row reads/month, 100 locations
- ✅ **Dashboard always has fresh data** — reads directly from Turso, no `git pull` needed
- ✅ **Secrets in GitHub Actions** — `TURSO_DATABASE_URL` and `TURSO_AUTH_TOKEN` as secrets
- ✅ **Works from anywhere** — could even host the dashboard on Render/Railway later

### Cons
- ❌ **Code changes required** — `src/database.py` needs a new connection string path (`libsql://...` instead of `sqlite:///data/listings.db`)
- ❌ **New dependency** — `libsql-experimental` or `sqlalchemy-libsql` package
- ❌ **Network latency** — local dashboard queries go over the internet (~50–100ms per query vs. <1ms for local SQLite)
- ❌ **Vendor lock-in** — tied to Turso's free tier; if they change pricing, need to migrate again
- ⚠️ **Migration needed** — existing data in `data/listings.db` must be exported and imported into Turso

### SQLite handling
Approach **C** (cloud DB migration). The cleanest long-term solution but the most work upfront.

### Effort: ~6–10 hours
- Sign up for Turso, create database
- Install `sqlalchemy-libsql`, update `src/database.py` connection logic
- Migrate existing data from local SQLite to Turso
- Update `.env.example` with `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN`
- Create GitHub Actions workflow
- Test end-to-end (scraper → Turso → dashboard reads)

---

## Option 3: GitHub Actions + JSON Artifact (Hybrid)

**How it works:** The scraper runs in GitHub Actions but instead of writing to SQLite directly, it outputs a JSON file of scraped listings. This JSON is committed to the repo (or stored as an artifact). A local import script reads the JSON and merges it into the local SQLite database.

### Pros
- ✅ **Preserves local SQLite** — no database migration, dashboard code unchanged
- ✅ **JSON is git-friendly** — text-based, diffable, mergeable (unlike binary SQLite)
- ✅ **Decoupled** — cloud scraper and local DB are independent; import is idempotent via `upsert_listing()`
- ✅ **Incremental** — only new/changed listings in each JSON file
- ✅ **Fallback** — if cloud scraping fails, launchd still works as a backup

### Cons
- ❌ **New code needed** — scraper needs a "JSON output mode" + a new `scripts/import-listings.py` script
- ❌ **Two-step process** — scrape (cloud) → import (local); not fully automatic unless you add a local cron to auto-import
- ❌ **Enrichment split** — geocoding, school assignment, dedup happen in the orchestrator; these need to run either in the cloud (needs `shapely`, GeoJSON files) or locally during import
- ⚠️ **Notifications delayed** — notifications fire during import, not during scrape; timing depends on when you import

### SQLite handling
Approach **D** (cloud scrape → JSON → local import). Good middle ground but adds operational complexity.

### Effort: ~4–6 hours
- Modify `ScraperOrchestrator` to support JSON output mode (skip DB writes, return raw dicts)
- Create `scripts/import-listings.py` that reads JSON and calls `upsert_listing()` + enrichment
- Create GitHub Actions workflow that runs scraper in JSON mode and commits output
- Add local cron/launchd job to auto-import (optional)

---

## Comparison Matrix

| Criteria | Git-Committed DB | Turso Cloud DB | JSON Hybrid |
|----------|:-:|:-:|:-:|
| **Simplicity** | ⭐⭐⭐ | ⭐⭐ | ⭐⭐ |
| **Code changes** | Minimal (workflow only) | Moderate (DB layer) | Moderate (new scripts) |
| **Data freshness** | Stale until `git pull` | Always fresh | Stale until import |
| **Merge safety** | ❌ Binary conflicts | ✅ No conflicts | ✅ Text-based |
| **Long-term scalability** | ❌ Repo bloat | ✅ Proper DB | ⚠️ OK for now |
| **Offline dashboard** | ✅ Works offline | ❌ Needs internet | ✅ Works offline |
| **Free tier risk** | Low (GitHub is stable) | Medium (Turso is a startup) | Low |
| **Effort** | ~2h | ~6–10h | ~4–6h |

---

## Recommendation

### Start with Option 1 (Git-Committed DB), plan for Option 2 (Turso) later

**Rationale:**

1. **Option 1 solves the immediate problem** — the scraper runs daily regardless of laptop state. It takes ~2 hours to set up and requires zero code changes to the Python codebase.

2. **The downsides are manageable at current scale** — the DB is ~500KB, grows slowly (a few listings per day), and you're the sole user. Binary conflicts won't happen if you treat the cloud as the sole writer and the local copy as read-only.

3. **Option 2 is the right long-term answer** but it's premature right now. When any of these triggers occur, migrate to Turso:
   - `listings.db` exceeds ~5 MB
   - You want to access the dashboard from a phone/tablet (not just localhost)
   - You add a second user
   - You want to host the dashboard publicly

4. **Option 3 is clever but over-engineered** for a single-user project. The two-step process adds friction without enough benefit over Option 1.

### Quick-start: Option 1 implementation sketch

```yaml
# .github/workflows/scrape.yml
name: Daily Scrape
on:
  schedule:
    - cron: '0 3 * * *'  # 03:00 UTC = 06:00 Israel
  workflow_dispatch:       # Manual trigger button

jobs:
  scrape:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: python scripts/run-scraper.py
        env:
          RAPIDAPI_KEY: ${{ secrets.RAPIDAPI_KEY }}
          REALTOR_RAPIDAPI_KEY: ${{ secrets.REALTOR_RAPIDAPI_KEY }}
          SMTP_PASSWORD: ${{ secrets.SMTP_PASSWORD }}
          NOTIFICATION_RECIPIENT: ${{ secrets.NOTIFICATION_RECIPIENT }}
      - uses: stefanzweifel/git-auto-commit-action@v5
        with:
          commit_message: "chore: daily scrape [skip ci]"
          file_pattern: data/listings.db
```

> ⚠️ **Prerequisite:** Remove `data/listings.db` from `.gitignore` and commit the current DB file to the repo.

---

## Open Questions (for owner decision)

1. **Is the repo private?** — If public, the DB file would be visible to anyone. Listing data isn't sensitive, but it's worth confirming.
2. **Acceptable staleness?** — With Option 1, the local dashboard shows yesterday's data until you `git pull`. Is that OK?
3. **Keep launchd as fallback?** — The existing launchd plist could remain as a backup scraper when the laptop is on. Dual-writing is safe because `upsert_listing()` is idempotent.
4. **Playwright dependency** — `requirements.txt` includes `playwright` (for Craigslist). GitHub Actions runners need `playwright install chromium` added to the workflow. This adds ~1 min to the job.
