# Admin Dashboard

> Backoffice admin panel at `/admin/` with 5 pages: Dashboard KPIs, Analytics, API Usage, Notifications, and Settings.

**Status:** Active  
**Owner files:** `web/routes/admin.py`, `web/templates/admin/*.html`, `web/static/css/admin.css`  
**Config:** `config.yaml` → `email`, `telegram`, `whatsapp` (Settings page)
**Added:** 2026-03-30
**Last updated:** 2026-05-10

## Overview

The admin dashboard is a 5-page backoffice panel accessible at `/admin/` on the FastAPI server. It provides system monitoring, listing analytics, API budget tracking, notification management, and settings configuration. Originally planned as a separate Streamlit app (`backoffice.py` on port 8502), it was merged into the FastAPI server during the frontend migration.

The admin UI uses dedicated CSS (`admin.css`) with `--admin-*` design tokens, separate from the dashboard's `style.css`.

## Architecture

- **Route prefix:** `/admin/` — all admin pages under this prefix
- **Template inheritance:** `web/templates/admin/base.html` with sidebar navigation
- **Dedicated CSS:** `web/static/css/admin.css` with `--admin-*` design tokens
- **Real DB queries:** All KPIs and charts use live database queries (not cached)
- **Manual sync button:** `POST /admin/sync` triggers `ScraperOrchestrator.run_sync()` on demand
  - 5-minute cooldown timer (`time.monotonic()`)
  - `asyncio.Lock()` prevents concurrent syncs
  - Basic auth via `ADMIN_SECRET_KEY` env var (optional, dev mode = open)
- **System Health:** "🩺 System Health" section with green/red indicators for env vars

## Current State

### Pages

| Page | Route | Features |
|------|-------|----------|
| Dashboard | `/admin/` | KPIs (total listings, avg rent, API calls, sources), sync button, 30-day scrape heatmap, System Health |
| Analytics | `/admin/analytics` | Listing analytics, price distribution, lifecycle KPIs (avg/median lifespan, total removed), lifespan by bedrooms/price range |
| API Usage | `/admin/api-usage` | Donut quota charts, success trends, sparklines (see [API Usage Page](api-usage-page.md)) |
| Notifications | `/admin/notifications` | Notification stats; SMTP / Telegram / WhatsApp credential warning banners; **red error banners** when most-recent WhatsApp send failed with `token_expired`, when Telegram failed with `auth` (BotFather token revoked), or generic `info-banner--warning` for other categories; per-row failure badges in history (e.g. "🔑 Token expired", "💬 Telegram failure") |
| Settings | `/admin/settings` | Email enable/disable toggle, recipient email input (persists to `config.yaml`); Telegram + WhatsApp enabled status + masked recipients (Telegram `chat_id` shows last 4 only); env var documentation in security footer |

- **HTMX:** Version 2.0.4 with SRI hash across both dashboard and admin templates
- **Accessibility:** `aria-live="polite" role="status"` on sync result container

## Key Files

| File | Purpose |
|------|---------|
| `web/routes/admin.py` | All admin route handlers |
| `web/templates/admin/base.html` | Admin base template with sidebar nav |
| `web/templates/admin/dashboard.html` | Dashboard KPIs + sync button + heatmap |
| `web/templates/admin/analytics.html` | Listing analytics |
| `web/templates/admin/api-usage.html` | API usage visualization |
| `web/templates/admin/notifications.html` | Notification management |
| `web/templates/admin/settings.html` | Settings page |
| `web/static/css/admin.css` | Admin-specific CSS |

## History

- [2026-05-10] Telegram channel surfaced in admin UI — Notifications page: credential warning banner ("Telegram bot credentials not configured") + auth-failure red banner (BotFather regen instructions) + generic Telegram failure warning + per-row "💬 Telegram failure" badge. Settings page: Telegram status row, masked `chat_id` (last 4 only) row, env var note in security footer (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`). CSS bumped to `admin.css?v=9` (cache flush only — no new rules; reuses existing `info-banner--error` and badge styles).
- [2026-05-08] Notifications page — added prominent red `info-banner--error` banner that appears when the most recent WhatsApp send within the last 48 h failed with `token_expired` (links to Meta App Dashboard, instructs user to update `WHATSAPP_API_TOKEN` in `.env`). Also added secondary banners for non-token WhatsApp failures and SMTP `auth` failures. History table rows show specific failure badges (`🔑 Token expired`, `❌ {category}`) instead of a generic `❌ Failed`. CSS bumped to `admin.css?v=8` (added `info-banner--error` rule).
- [2026-04-06] Listing Lifecycle analytics section added to Analytics page — KPI cards (avg/median lifespan, total removed) + bar charts (lifespan by bedrooms, lifespan by price range)
- [2026-04-06] API Usage page completely redesigned — donut charts, success trends, sparklines
- [2026-04-06] Scrape activity heatmap added to dashboard (30-day calendar, per-source gap detection)
- [2026-03-31] Manual sync button added with cooldown + auth + HTMX
- [2026-03-31] Startup environment validation — System Health section added
- [2026-03-31] Notification failure fix — SMTP warning banner added
- [2026-03-30] Phase 2: Initial backoffice admin panel — 5 pages, dedicated CSS

## Related

- [API Usage Page](api-usage-page.md) — detailed API budget visualization
- [Notification System](notification-system.md) — notification stats and management
- [Scheduler (launchd)](scheduler-launchd.md) — heatmap monitors scrape activity
- [Config (YAML)](config-yaml.md) — Settings page reads/writes config
- [App Isolation](../concepts/app-isolation.md) — dashboard vs backoffice separation
- [CSS Cache Versioning](../concepts/css-cache-versioning.md) — admin.css version bumping
