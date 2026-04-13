# Environment Validation

> Validate all required environment variables at application startup and show credential status in the admin UI — don't wait until use-time to discover missing config.

**Applies to:** [Config (YAML)](../entities/config-yaml.md), [Admin Dashboard](../entities/admin-dashboard.md), [Zillow Scraper](../entities/zillow-scraper.md), [Notification System](../entities/notification-system.md)  
**Learned:** 2026-03-31  
**Source:** `docs/memory/shared/lessonsLearned.md` — Silent Failure Pattern + `docs/memory/shared/systemPatterns.md` — Startup Environment Validation

## Pattern

Features that depend on external credentials (API keys, SMTP passwords) fail silently when those credentials are missing. The system keeps running, keeps scheduling jobs, keeps logging "normal" activity — but nothing actually works. This went undetected for 5 days with the Zillow API key.

The fix is a two-layer validation approach:
1. **Startup validation:** `_validate_environment()` in `web/main.py` checks all required/recommended env vars at boot and logs clear ⚠️ warnings
2. **Runtime UI:** "🩺 System Health" panel on the admin dashboard with green/red indicators per env var

## Rules

1. **Validate credentials at startup, not at use-time** — `_validate_environment()` runs at every FastAPI startup
2. **Show credential status in the admin UI** — operators can verify everything with one glance after any restart
3. **Non-blocking:** App starts even with missing vars (warnings only, no crash)
4. **No credential values in logs or templates** — only presence/absence
5. **Conditional checks:** SMTP_PASSWORD only warns when email is enabled in config
6. **`.env` file is the single source of truth for secrets** — `load_dotenv()` reads it at startup

### Required Environment Variables

| Variable | Purpose | Used By |
|----------|---------|---------|
| `RAPIDAPI_KEY` | Zillow + Realtor.com API access | Scrapers |
| `REALTOR_RAPIDAPI_KEY` | Realtor.com API (optional override) | Realtor scraper |
| `SMTP_PASSWORD` | Gmail App Password for notifications | Notifier |
| `NOTIFICATION_RECIPIENT` | Email recipient (optional, config fallback) | Notifier |
| `ADMIN_SECRET_KEY` | Admin sync button auth (optional) | Admin routes |

## Examples

- **Zillow API key incident (2026-03-31):** `RAPIDAPI_KEY` lost after server restart — scraper silently returned `[]` for 5 days
- **SMTP password incident (2026-03-31):** `SMTP_PASSWORD` commented out — 21 failed notification attempts with 0% success rate
- **Prevention:** `.env.example` documents all required env vars; `_validate_environment()` catches missing vars at startup

## Related

- [Config (YAML)](../entities/config-yaml.md) — config.yaml has empty defaults for secrets
- [Admin Dashboard](../entities/admin-dashboard.md) — System Health panel
- [Silent Failure Pattern](silent-failure-pattern.md) — the underlying anti-pattern
- [Security Patterns](security-patterns.md) — env vars for secrets
