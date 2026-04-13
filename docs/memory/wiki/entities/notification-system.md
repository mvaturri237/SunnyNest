# Notification System

> Multi-channel notification system (Email + WhatsApp) that sends new listing alerts filtered by config.yaml criteria, with anti-spam guard and per-channel credential checks.

**Status:** Active
**Owner files:** `src/notifier.py`, `src/database.py`
**Config:** `config.yaml` → `email`, `whatsapp`, `notification_schedule`
**Added:** 2026-03-27
**Last updated:** 2026-04-12

## Overview

The notification system sends alerts when new listings matching the user's search criteria are found. It supports two channels:

1. **Email** — Gmail SMTP with app-specific passwords, sends HTML-formatted listing tables
2. **WhatsApp** — Meta WhatsApp Business Cloud API via `httpx`, sends concise text messages (4096-char limit)

Both channels apply `config.yaml` filters (price $5K–$6.5K, 3–4 BR, houses) to show only relevant listings (~10 matching instead of all active), and share the same anti-spam guard (max 2 sends/day).

The system runs twice daily (08:00 and 20:00) via [launchd scheduler](scheduler-launchd.md) plists, fully decoupled from the web server lifecycle.

## Architecture

- **`BaseNotificationChannel` ABC** — abstract base class with `send()`, `is_enabled()`, `get_recipient()`, `channel_name`
- **`EmailChannel`** — SMTP-based email implementation (Gmail, port 587, TLS)
- **`WhatsAppChannel`** — Meta WhatsApp Business Cloud API implementation (`graph.facebook.com/v21.0`)
- **`NotificationService` class** with `run()` method — the primary entry point, dispatches to all registered channels
- **Channel-agnostic pre-flight:** Each channel's `send()` validates its own credentials independently
- **Config-filtered:** `get_unnotified_listings(filters=config_filters)` applies the same filters as the dashboard
- **Anti-spam guard:** `get_today_notification_count()` counts ALL attempts (success + failure) — prevents unlimited failure spam
- **`notified` flag:** Set to `True` if ANY channel succeeds. Non-matching listings stay `notified=False` for future filter changes
- **Legacy delegation:** Old functions (`send_notification`, `_build_html_body`) delegate to `NotificationService` with `DeprecationWarning`

## Current State

- **Email:** Operational when `SMTP_PASSWORD` env var is set (Gmail App Password)
- **WhatsApp:** Operational when `WHATSAPP_API_TOKEN` and `WHATSAPP_PHONE_NUMBER_ID` env vars are set (disabled by default in config)
- **Schedule:** Twice daily at 08:00 and 20:00 via launchd plists
- **Admin UI:** Warning banners on Notifications admin page when credentials missing (separate banners for SMTP and WhatsApp)
- **Settings page:** Shows enabled/disabled status and recipient for both channels
- **Known issue:** If credentials are not set for a channel, that channel is silently skipped with `skipped_reason` logged

## Configuration

### Email Channel

| Key | Default | Description |
|-----|---------|-------------|
| `email.enabled` | `true` | Enable/disable email notifications |
| `email.smtp_server` | `smtp.gmail.com` | SMTP server |
| `email.smtp_port` | `587` | SMTP port (TLS) |
| `email.sender_email` | `maorvaturri@gmail.com` | Sender address |
| `email.sender_password` | `""` | Set via `SMTP_PASSWORD` env var |
| `email.recipient_email` | `maorvaturri@gmail.com` | Set via `NOTIFICATION_RECIPIENT` env var |
| `email.dashboard_url` | `http://sunnynest:8000` | Link in email body |

### WhatsApp Channel

| Key | Default | Description |
|-----|---------|-------------|
| `whatsapp.enabled` | `false` | Enable/disable WhatsApp notifications |
| `whatsapp.recipient_phone` | `""` | Set via `WHATSAPP_RECIPIENT_PHONE` env var (format: country code + number) |
| — | — | `WHATSAPP_API_TOKEN` env var — Meta Cloud API bearer token |
| — | — | `WHATSAPP_PHONE_NUMBER_ID` env var — WhatsApp Business phone number ID |

### Schedule

| Key | Default | Description |
|-----|---------|-------------|
| `notification_schedule.hours` | `[8, 20]` | Hours to send (local time) |
| `notification_schedule.timezone` | `Asia/Jerusalem` | Timezone for schedule |

## Key Files

| File | Purpose |
|------|---------|
| `src/notifier.py` | `BaseNotificationChannel`, `EmailChannel`, `WhatsAppChannel`, `NotificationService` |
| `src/database.py` | `get_unnotified_listings()`, `get_today_notification_count()` |
| `src/utils.py` | `get_email_settings()`, `update_email_settings()`, `get_whatsapp_settings()`, `update_whatsapp_settings()` |
| `scripts/run-notify.py` | Standalone script for launchd execution (registers both channels) |
| `config.yaml` → `email`, `whatsapp` | Channel configuration |
| `.env` → `SMTP_PASSWORD` | Email SMTP credentials (secret) |
| `.env` → `WHATSAPP_API_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID` | WhatsApp API credentials (secrets) |

## History

- [2026-04-12] Dashboard URL updated from `http://localhost:8501` to `http://sunnynest:8000` in config and code fallback defaults
- [2026-04-12] WhatsApp channel added — `WhatsAppChannel` class, config section, admin UI updates, channel-agnostic pre-flight
- [2026-04-06] Scheduler migrated to launchd — notifications now run via `scripts/run-notify.py`
- [2026-03-31] Config filter fix — notifications now apply `config.yaml` filters (~10 matching instead of all 39)
- [2026-03-31] 39-listing email fix — `upsert_listing()` now excludes `notified` from scraper overwrites
- [2026-03-31] Notification failure fix — anti-spam guard counts all attempts, pre-flight SMTP check added
- [2026-03-28] Email end-to-end test successful (Gmail App Password)
- [2026-03-27] Initial implementation

## Related

- [Scheduler (launchd)](scheduler-launchd.md) — triggers notification runs
- [Database Schema](database-schema.md) — `notified` flag, notification stats queries
- [Config (YAML)](config-yaml.md) — email and whatsapp settings, notification schedule
- [Admin Dashboard](admin-dashboard.md) — Notifications admin page with stats, Settings page with channel status
- [Silent Failure Pattern](../concepts/silent-failure-pattern.md) — credential dependency for both channels
- [Upsert Exclusion Pattern](../concepts/upsert-exclusion-pattern.md) — `notified` flag protection
- [Adapter Pattern](../concepts/adapter-pattern.md) — `BaseNotificationChannel` ABC for multi-channel dispatch
