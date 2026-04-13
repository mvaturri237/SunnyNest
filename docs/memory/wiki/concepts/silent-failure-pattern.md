# Silent Failure Pattern

> Features that depend on external credentials fail silently when those credentials are missing — the system keeps running but nothing actually works. Always validate at startup and show status in the admin UI.

**Applies to:** [Zillow Scraper](../entities/zillow-scraper.md), [Realtor Scraper](../entities/realtor-scraper.md), [Notification System](../entities/notification-system.md)  
**Learned:** 2026-03-31  
**Source:** `docs/memory/shared/lessonsLearned.md` — The "Silent Failure" Pattern

## Pattern

The same class of bug occurred twice in 2 days:

1. **Zillow API key (2026-03-31):** `RAPIDAPI_KEY` was not set after the frontend migration restart. The scraper silently returned `[]` every run — no errors, no warnings, just no data. Went unnoticed for 5 days.

2. **SMTP password (2026-03-31):** `SMTP_PASSWORD` was commented out in `.env`. Notifications failed 21 times with 0% success rate. The anti-spam guard (which only counted successes) never triggered, allowing unlimited failure spam.

**Root pattern:** Features that depend on external credentials fail silently when those credentials are missing. The system keeps running, keeps scheduling jobs, keeps logging "normal" activity — but nothing actually works.

## Rules

1. **Validate credentials at startup, not at use-time** — the single most important defense
2. **Show credential status in the admin UI** — operators can verify with one glance
3. **Rate limiters must count ALL attempts, not just successes** — prevents unlimited failure spam
4. **Add pre-flight checks before expensive operations** — check credentials BEFORE querying DB, building emails, or connecting to SMTP
5. **One scheduler instance only** — multiple processes each running their own scheduler multiplied the failures
6. **Environment variables must persist across restarts** — use `.env` file with `load_dotenv()`, not terminal session vars

## Examples

- **Zillow scraper:** Returns `[]` with a warning log when `RAPIDAPI_KEY` is missing — no error, no exception
- **SMTP notifier:** Pre-flight check added — skips pipeline early with `skipped_reason` when credentials missing
- **Anti-spam guard:** Changed from counting successes to counting all attempts

### Safeguards Now in Place
- `_validate_environment()` runs at every FastAPI startup
- System Health panel on admin dashboard (`/admin/`)
- SMTP warning banner on Notifications page
- API key warning banner on API Usage page
- Pre-flight credential check in `NotificationService.run()`
- Anti-spam guard counts all attempts (success + failure)

## Related

- [Environment Validation](environment-validation.md) — the fix for this pattern
- [Security Patterns](security-patterns.md) — env vars for secrets
- [Zillow Scraper](../entities/zillow-scraper.md) — affected by API key silent failure
- [Notification System](../entities/notification-system.md) — affected by SMTP silent failure
