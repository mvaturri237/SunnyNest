# Notification System

> Multi-channel notification system (Email + Telegram + WhatsApp) that sends new listing alerts filtered by config.yaml criteria, with anti-spam guard and per-channel credential checks.

**Status:** Active
**Owner files:** `src/notifier.py`, `src/database.py`
**Config:** `config.yaml` → `email`, `telegram`, `whatsapp`, `notification_schedule`
**Added:** 2026-03-27
**Last updated:** 2026-06-03 (anti-spam guard inverted to count successes only; silence-detector banner; AM trigger 08:00→10:00)

## Overview

The notification system sends alerts when new listings matching the user's search criteria are found. It supports three channels:

1. **Email** — Gmail SMTP with app-specific passwords, sends HTML-formatted listing tables
2. **Telegram** — Telegram Bot API via `httpx`, sends HTML-formatted text messages (4096-char limit). **Primary push channel** as of 2026-05-10 — bot tokens never auto-expire and there is no recipient allowlist.
3. **WhatsApp** — Meta WhatsApp Business Cloud API via `httpx`, sends concise text messages (4096-char limit). **Disabled by default** since 2026-05-10 due to (a) Test Number 24h token expiry and (b) Test Number recipient allowlist silently dropping messages. Code remains in place; flip `whatsapp.enabled: true` to re-enable.

All channels apply `config.yaml` filters (price $5K–$6.5K, 3–4 BR, houses) to show only relevant listings (~10 matching instead of all active), and share the same anti-spam guard (max 2 sends/day).

The system runs twice daily (08:00 and 20:00) via [launchd scheduler](scheduler-launchd.md) plists, fully decoupled from the web server lifecycle.

## Architecture

- **`BaseNotificationChannel` ABC** — abstract base class with `send()`, `is_enabled()`, `get_recipient()`, `channel_name`
- **`EmailChannel`** — SMTP-based email implementation (Gmail, port 587, TLS)
- **`TelegramChannel`** — Telegram Bot API implementation (`api.telegram.org/bot<token>/sendMessage`, `parse_mode=HTML`)
- **`WhatsAppChannel`** — Meta WhatsApp Business Cloud API implementation (`graph.facebook.com/v21.0`)
- **`NotificationService` class** with `run()` method — the primary entry point, dispatches to all registered channels
- **Channel-agnostic pre-flight:** Each channel's `send()` validates its own credentials independently
- **Config-filtered:** `get_unnotified_listings(filters=config_filters)` applies the same filters as the dashboard
- **Anti-spam guard:** `get_today_notification_count()` counts **only successful sends** (`success=True`). Transient failures (network, auth, rate-limited) do NOT consume the daily cap, so morning failures cannot silently block PM recovery. **Inverted on 2026-06-03** after the previous "count all attempts" semantics caused a 7-day Telegram silence (2 morning DNS-failure rows consumed the 2/day cap → PM correctly skipped → user only noticed by visiting dashboard a week later). See [Silent Failure Pattern](../concepts/silent-failure-pattern.md) "duplication-as-silent-failure" sub-pattern and the 2026-06-03 row in the Variants table.
- **IST-correct daily windowing:** `get_today_notification_count()` now translates the IST "today" window to UTC bounds (`sent_at >= start_utc AND sent_at < end_utc`) before querying, since `notification_log.sent_at` stores naive UTC. This eliminates a near-midnight off-by-one (cosmetic for the 10:00/20:00 schedule, but the prior `func.date()` comparison docstring overpromised a fix that wasn't there).
- **Shared filter extraction:** [`notifier.load_notification_filters(config)`](../../../src/notifier.py:1345) is the **single source of truth** for which listings are notification-eligible. Two consumers: `NotificationService.run()` (decides what to actually send) and `web.routes.dashboard._compute_notification_silence_state()` (decides whether the dashboard silence banner appears). Adding/removing a filter here propagates to both — eliminates the copy-paste drift class that would otherwise silently false-positive the silence detector.
- **Silence-detector banner:** Red banner on `/` (dashboard) when **(a)** no successful notification in the last 48h **AND** **(b)** there are matching unnotified listings in that window (i.e., the notifier WOULD have sent something). Surfaces silence proactively — operators no longer need to visit `/admin/notifications` to discover broken pipelines.
- **`notified` flag:** Set to `True` if ANY channel succeeds. Non-matching listings stay `notified=False` for future filter changes
- **Legacy delegation:** Old functions (`send_notification`, `_build_html_body`) delegate to `NotificationService` with `DeprecationWarning`

## Current State

- **Email:** Operational — `SMTP_PASSWORD` env var set, sending successfully (verified 2026-05-08)
- **Telegram (added 2026-05-10):** Code-side operational, **inert until user-side bot setup**. `TelegramChannel` registered in `scripts/run-notify.py`, `telegram.enabled: false` until `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` are set in `.env` (user creates bot via [@BotFather](https://t.me/BotFather), captures `chat_id` via `getUpdates`, then flips `enabled: true`). Reuses existing `error_category` taxonomy — no new categories needed. **No `token_expired` equivalent**: Telegram bot tokens don't auto-expire (positive design property closing the WhatsApp variant of the [Silent Failure Pattern](../concepts/silent-failure-pattern.md)). Tokens can be revoked manually via BotFather → that surfaces as `error_category="auth"` (HTTP 401).
- **WhatsApp:** Code-side operational but **`whatsapp.enabled: false` since 2026-05-10** (replaced by Telegram as primary push channel). Code remains; flip `enabled: true` in `config.yaml` to re-enable. Two unresolved limitations below remain reasons to keep it disabled.
- **WhatsApp delivery limitation (2026-05-08):** Current `WHATSAPP_PHONE_NUMBER_ID` is a Meta-provided **Test Number** (`verified_name: "Test Number"`, `messaging_limit_tier: TIER_250`). Test numbers can only deliver to recipients explicitly added to the App's allowed-phone-number list in the Meta App Dashboard. Messages to non-allowlisted recipients are silently dropped by Meta (no error returned, no webhook callback) — invisible to SunnyNest. To remove this limitation, register a real production phone number in WhatsApp Business and update `WHATSAPP_PHONE_NUMBER_ID`.
- **WhatsApp token-expiry detection (2026-05-08):** Meta Test Number access tokens expire ~every 24 hours. `WhatsAppChannel` now detects HTTP 401 / `OAuthException` / Meta error codes 190/102/463/467 and tags failures with `error_category="token_expired"` in `notification_log`. The Notifications admin page renders a prominent red `info-banner--error` with regeneration instructions whenever the most recent WhatsApp send within the last 48 h failed with `token_expired`. The history table shows a "🔑 Token expired" badge per row. Startup probe in `web/main.py` calls `WhatsAppChannel.validate_token()` (cheap `GET /{phone_id}` — no quota cost) when WhatsApp is enabled.
- **Schedule:** Twice daily at **10:00 and 20:00** via launchd plists (AM shifted 08:00→10:00 on 2026-06-03 to give VPN/network time to come up reliably — see [Scheduler (launchd)](scheduler-launchd.md))
- **Admin UI:** Warning banners on Notifications admin page when credentials missing (separate banners for SMTP, Telegram, and WhatsApp). Plus error banners surfacing the most-recent failure for each channel: `token_expired` (WhatsApp OAuth), `auth` (SMTP / Telegram authentication), `recipient_refused` (Telegram bot blocked or chat not found), and other categories. Per-row badges include "🔑 Token expired" (WhatsApp) and "💬 Telegram failure".
- **Settings page:** Shows enabled/disabled status and recipient for all three channels (Telegram chat_id masked to last 4 only).
- **Failure diagnostics architecture:**
  - `BaseNotificationChannel.send_with_diagnostics()` returns a `SendResult` dataclass with `error_category` + `error_message`; `send()` is a thin bool wrapper.
  - `notification_log` table now has `error_category TEXT` and `error_message TEXT` columns (additive migration in `_ensure_notification_error_columns`).
  - Categories: `token_expired`, `auth`, `rate_limited`, `recipient_refused`, `network`, `api_error`, `missing_credentials`, `disabled`, `no_listings`, `unexpected`.
  - `get_last_channel_failure(channel, within_hours=48)` returns the latest log row only if it's a failure — a later success automatically clears the warning.
- **Known issues:**
  - If credentials are not set for a channel, that channel is skipped with `error_category="missing_credentials"` logged
  - SunnyNest treats Meta API `200 OK` as definitive success but Meta may silently drop messages (Test Number allowlist, recipient blocked, etc.). No `delivered`/`read` webhook subscription yet — see `notification_log` only shows `sent` status.

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

### Telegram Channel

| Key | Default | Description |
|-----|---------|-------------|
| `telegram.enabled` | `false` | Enable/disable Telegram notifications |
| `telegram.parse_mode` | `"HTML"` | Telegram message parse mode (HTML preferred over MarkdownV2 — escape surface is just `& < >` via `html.escape()`) |
| — | — | `TELEGRAM_BOT_TOKEN` env var — bot token from [@BotFather](https://t.me/BotFather) (never auto-expires) |
| — | — | `TELEGRAM_CHAT_ID` env var — recipient chat ID (env-only, NOT in config.yaml — co-secret with bot token) |

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
| `notification_schedule.hours` | `[10, 20]` | Hours to send (local IST). AM shifted 08:00→10:00 on 2026-06-03. |
| `notification_schedule.timezone` | `Asia/Jerusalem` | Timezone for schedule |

## Key Files

| File | Purpose |
|------|---------|
| `src/notifier.py` | `BaseNotificationChannel`, `EmailChannel`, `TelegramChannel`, `WhatsAppChannel`, `NotificationService` |
| `src/database.py` | `get_unnotified_listings()`, `get_today_notification_count()` |
| `src/utils.py` | `get_email_settings()`, `update_email_settings()`, `get_telegram_settings()`, `update_telegram_settings()`, `get_whatsapp_settings()`, `update_whatsapp_settings()` |
| `scripts/run-notify.py` | Standalone script for launchd execution (registers all three channels) |
| `config.yaml` → `email`, `telegram`, `whatsapp` | Channel configuration |
| `.env` → `SMTP_PASSWORD` | Email SMTP credentials (secret) |
| `.env` → `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | Telegram bot credentials (secrets) |
| `.env` → `WHATSAPP_API_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID` | WhatsApp API credentials (secrets) |
| `scripts/test_telegram_notification.py` | Manual e2e Telegram test (`--preview` / `--send`) |
| `scripts/test_telegram_classification.py` | Mock-based unit tests for Telegram error categorization (6 cases) |
| `scripts/test_telegram_validate_token.py` | Mock-based unit tests for `TelegramChannel.validate_token` (2 cases) |

## History

- [2026-06-03] **Silent-notification prevention — 3-fix bundle (✅ APPROVED, 0 P1/P2 after 2 rounds, 12 P3s → backlog).** Triggered by a 7-day Telegram silence (May 27 → Jun 3) discovered when the user visited the dashboard and noticed no notifications since May 27. Live evidence captured before the fix: 2 morning network-failure rows in `notification_log` consumed the 2/day anti-spam cap, silently blocking PM recovery; deleting the 2 failed rows + manual re-run delivered the 9 backlogged listings successfully via Email + Telegram (HTTP 200 both channels). **Fixes:** (1) `get_today_notification_count()` now counts `success=True` only — replaces the 2026-03-31 "count all attempts" semantics that *caused* this regression. (2) `get_today_notification_count()` switched from `func.date(sent_at) == today` (UTC-day compare) to a UTC-bounded window translated from IST midnight, eliminating a near-midnight off-by-one and removing a now-false "tz-aware" docstring claim. (3) New `load_notification_filters(config)` module-level helper in [`src/notifier.py`](../../../src/notifier.py:1345) — single source of truth for filter extraction, consumed by both `NotificationService.run()` and `_compute_notification_silence_state()`. (4) New silence-detector banner on `/` dashboard ([`web/routes/dashboard.py:40`](../../../web/routes/dashboard.py:40), [`web/templates/dashboard.html:385`](../../../web/templates/dashboard.html:385), [`web/static/css/style.css:1432`](../../../web/static/css/style.css:1432); CSS bumped `?v=11`→`?v=12`). (5) `com.sunnynest.notify-am.plist` Hour `8`→`10`; `config.yaml notification_schedule.hours [8,20]→[10,20]`. (6) New regression tests: [`scripts/test_anti_spam_guard.py`](../../../scripts/test_anti_spam_guard.py) — 5/5 pass including the new IST-vs-UTC-day boundary test. **Pipeline:** Orchestrator → Debug → Code (R1) → Reviewer (R1: ❌ 1P1+2P2) → Code (R2) → Reviewer (R2: ✅) → wiki sync. Cloud scheduler queued as separate follow-up for the laptop-asleep-on-weekends gap.
- [2026-05-10] **Telegram channel added; WhatsApp disabled by default** — new `TelegramChannel(BaseNotificationChannel)` (~330 LOC) mirroring `WhatsAppChannel` 1:1 (same `SendResult` contract, same PANW root CA SSL pattern, same body truncation). Reuses existing `error_category` taxonomy (no new categories): HTTP 401 → `auth`, 403 "bot was blocked" / 400 "chat not found" → `recipient_refused`, 429 → `rate_limited`, network → `network`, other → `api_error`. Bot token + `chat_id` both env-only (co-secrets). New startup probe in [`web/main.py`](../../../web/main.py) calls `TelegramChannel.validate_token()` (cheap `getMe`, gated by `telegram.enabled`). Admin UI: Telegram credential warning banner + auth-failure banner + per-row "💬 Telegram failure" badge on Notifications page; Telegram status row + masked `chat_id` (last 4) on Settings page. CSS cache bumped to `v=9`. `whatsapp.enabled` flipped `true` → `false`. Code Reviewer: ✅ APPROVED, 0 P1/P2, 4 P3s logged to [`docs/memory/p3-backlog.md`](../../p3-backlog.md). Inert until user creates bot via [@BotFather](https://t.me/BotFather) and provides `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` in `.env`.
- [2026-05-08] **Token-expiry detection + visible failure surfacing** — added `OAuthException`/401 detection in `WhatsAppChannel`; new `SendResult` dataclass + `send_with_diagnostics()` method on `BaseNotificationChannel`; new `error_category`/`error_message` columns on `notification_log` (additive migration); new `get_last_channel_failure()` DB helper; new red error banner + per-row "🔑 Token expired" badge on Notifications admin page; new `WhatsAppChannel.validate_token()` static method called at FastAPI startup (no quota cost). CSS cache bumped to v=8.
- [2026-05-08] Diagnostic — user reported missing WhatsApp messages. Root cause: Meta sender is a Test Number requiring recipient allowlist. No SunnyNest code change needed. Documented Test Number delivery limitation and future improvement (subscribe to `messages` webhook for `delivered`/`read` status).
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
