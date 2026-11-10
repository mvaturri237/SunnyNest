# Config (YAML)

> Central configuration file managing search parameters, filters, API settings, email notifications, and scheduler documentation.

**Status:** Active  
**Owner files:** `config.yaml`  
**Config:** Self — this IS the config file  
**Added:** 2026-03-27  
**Last updated:** 2026-06-03

## Overview

`config.yaml` is the central configuration file for SunnyNest. It defines search parameters (city, ZIP codes), default filters (price range, bedrooms), API settings for each data source, email/Telegram/WhatsApp notification configuration, and scheduler documentation. It serves as the single source of truth for user search preferences — all user-facing data views (dashboard, notifications, analytics) apply these filters.

**Important:** Config values override code constants at runtime. When a code constant has a `config.yaml` counterpart, both must be updated together (see [CSS Cache Versioning](../concepts/css-cache-versioning.md) for the general principle).

## Architecture

- **Format:** YAML, loaded via `PyYAML`
- **Read pattern:** `load_config()` function reads and parses the file
- **Write pattern:** Settings page writes via `update_email_settings()`, `update_telegram_settings()`, and `update_whatsapp_settings()` in `src/utils.py` (backup to `config.yaml.bak` before every write)
- **Secrets:** API keys and passwords have empty defaults in config — actual values set via environment variables (`.env` file)
- **Filter application:** `_apply_listing_filters(query, filters)` in `src/database.py` applies config filters to any SQLAlchemy query

## Current State

### Sections

| Section | Purpose | Key Values |
|---------|---------|------------|
| `search` | Search parameters | city: Sunnyvale, state: CA, 4 ZIP codes |
| `filters` | Default filters | price: $5K–$7.5K, bedrooms: 3–4, types: [house] |
| `schedule` | Scheduler docs (launchd) | scrape: 06:00, notify: 08:00/20:00, tz: Asia/Jerusalem |
| `email` | Email notification settings | Gmail SMTP, port 587, enabled: true |
| `telegram` | Telegram notification settings | Telegram Bot API, enabled: false (until BotFather setup), parse_mode: HTML |
| `whatsapp` | WhatsApp notification settings | Meta Cloud API, enabled: false (since 2026-05-10 — superseded by Telegram) |
| `notification_schedule` | Legacy schedule config | hours: **[10, 20]** (AM shifted 08:00→10:00 on 2026-06-03 to match launchd) |
| `scraper` | Shared scraper settings | delay: 3-8s, max_pages: 3, detail_pages: true |
| `zillow_api` | Zillow API config | host, key (env var) |
| `realtor_api` | Realtor.com API config | host, key (env var), budget: 150, threshold: 90%, enabled: true |

### Key Rules

1. **Secrets in env vars:** `rapidapi_key`, `sender_password` have empty defaults — real values via `RAPIDAPI_KEY`, `SMTP_PASSWORD`, `NOTIFICATION_RECIPIENT`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `WHATSAPP_API_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_RECIPIENT_PHONE` env vars
2. **Config overrides code:** When `config.yaml` has a value, it wins over code constants (e.g., `monthly_budget: 150` overrides `API_BUDGET_LIMITS["realtor"]`)
3. **Schedule is documentation only:** Actual schedule defined in launchd plists, not config
4. **Settings page writes:** `email.enabled`, `email.recipient_email`, `telegram.enabled`, `whatsapp.enabled`, and `whatsapp.recipient_phone` are writable from UI. **`telegram.parse_mode` and `chat_id` are NOT writable** — `parse_mode` is a code-level constant (HTML), `chat_id` is env-only as a co-secret with the bot token.

## Key Files

| File | Purpose |
|------|---------|
| `config.yaml` | The configuration file itself |
| `src/utils.py` | `update_email_settings()`, `get_email_settings()`, `update_telegram_settings()`, `get_telegram_settings()`, `update_whatsapp_settings()`, `get_whatsapp_settings()` |
| `src/database.py` | `_apply_listing_filters()` — applies config filters |
| `.env` | Environment variables for secrets |
| `.env.example` | Documentation of required env vars |

## History

- [2026-06-03] `notification_schedule.hours` changed `[8, 20]` → `[10, 20]` (synced with `com.sunnynest.notify-am.plist` Hour 8 → 10). Part of the silent-notification-prevention bundle ([Notification System](notification-system.md) 2026-06-03 history). Per AGENTS.md §5 rule #3 the plist + config.yaml must stay aligned.
- [2026-05-14] `filters.max_price` changed `6500` → `7500` (default price filter raised to $5K–$7.5K per user request). `web/routes/dashboard.py` `_DROPDOWN_DEFAULTS["filter_price_max"]` and `web/templates/dashboard.html` quick-range radio updated in sync. `app.py` `_price_options` dict + sentinel updated (P2 fix). Scrapers + notifier pick up automatically from config.
- [2026-05-10] `telegram` section added (`enabled: false`, `parse_mode: "HTML"`); `whatsapp.enabled` flipped `true` → `false` (superseded by Telegram as primary push channel)
- [2026-04-14] `scraper.max_pages` increased from 1 → 3 to capture more listings per scrape (user reported 6 vs 18 on Zillow)
- [2026-04-12] `email.dashboard_url` updated from `http://localhost:8501` to `http://sunnynest:8000` (FastAPI migration)
- [2026-04-12] WhatsApp section added — `whatsapp.enabled`, `whatsapp.recipient_phone`
- [2026-04-06] Realtor.com budget updated: 100 → 150 calls/month
- [2026-04-06] Schedule section updated to document launchd (APScheduler removed)
- [2026-04-01] `realtor_api` section added for Realtor.com scraper
- [2026-03-31] Settings persistence via `update_email_settings()` (backup before write)
- [2026-03-28] `schedule.interval_hours` changed from 24 → 6
- [2026-03-28] `property_types` reduced to `[house]`
- [2026-03-27] API key moved from config to env var (security fix)
- [2026-03-27] Initial configuration

## Related

- [Zillow Scraper](zillow-scraper.md) — `zillow_api` section
- [Realtor Scraper](realtor-scraper.md) — `realtor_api` section
- [Notification System](notification-system.md) — `email` section
- [Filter Bar](filter-bar.md) — `filters` section provides defaults
- [Scheduler (launchd)](scheduler-launchd.md) — `schedule` section (documentation only)
- [Admin Dashboard](admin-dashboard.md) — Settings page reads/writes config
- [Environment Validation](../concepts/environment-validation.md) — startup checks for env vars
