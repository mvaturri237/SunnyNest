# Telegram Notification Channel — Spec

> Status: **PLANNED** — 2026-05-10
> Owner: Architect (spec) → Code (impl) → Code Reviewer (review)
> Plan freshness: fresh as of 2026-05-10

## Why

WhatsApp via Meta Cloud API has proven unreliable for this single-user deployment for two reasons documented in [`notification-system.md`](../docs/memory/wiki/entities/notification-system.md):

1. **24 h Test Number token expiry** — `WHATSAPP_API_TOKEN` for the Meta-provided Test Number rotates every ~24 h. Already mitigated with `token_expired` detection + admin banner ([`src/notifier.py:528`](../src/notifier.py:528)), but operationally still requires a daily manual token refresh in the Meta App Dashboard.
2. **Test Number recipient allowlist** — non-allowlisted recipients get messages silently dropped by Meta (HTTP 200 + valid `wamid` returned, message never delivered). Invisible from SunnyNest's side; no webhook subscription planned.

Telegram has no equivalent of either failure mode (bot tokens are long-lived; no recipient allowlist for personal DMs).

**Decision:** Add a `TelegramChannel`. Keep `WhatsAppChannel` code in place but flip `whatsapp.enabled: false` in [`config.yaml`](../config.yaml) so it stops dispatching while remaining trivially re-enableable later.

---

## 1. Telegram Bot API summary

| Aspect | Value |
|--------|-------|
| Endpoint | `POST https://api.telegram.org/bot<token>/sendMessage` |
| Required body params | `chat_id` (int or `@channelusername`), `text` (string, ≤4096 chars) |
| Optional body params | `parse_mode` (`"HTML"` / `"MarkdownV2"`), `disable_web_page_preview` (bool) |
| Auth | Bearer token in URL path (`/bot<token>/...`) — no header |
| Response | JSON `{"ok": true, "result": {...}}` on success; `{"ok": false, "error_code": N, "description": "..."}` on failure |
| Rate limits | ~30 messages/sec global; **1/sec per chat** (we send ≤ 2/day, so irrelevant) |
| Token revocation | User-initiated only via `@BotFather` (`/revoke`) — does NOT auto-expire |
| Char limit | **4096** (same as WhatsApp — reuse the existing truncation logic verbatim) |
| HTML support | `<b>`, `<i>`, `<u>`, `<s>`, `<a href="…">`, `<code>`, `<pre>` — that's all |
| SDK | None — plain `httpx.Client.post` like [`WhatsAppChannel.send_with_diagnostics`](../src/notifier.py:679) |

### Bot setup (one-time, user-side)

1. DM `@BotFather` on Telegram → `/newbot` → pick a name + username (e.g., `sunnynest_alerts_bot`)
2. Receive bot token (format `1234567890:ABC-DEF...`) → store as `TELEGRAM_BOT_TOKEN`
3. DM the new bot once (any message — required to "open" the chat from the bot's side)
4. Get user's `chat_id` via `https://api.telegram.org/bot<token>/getUpdates` → look for `result[0].message.chat.id` → store as `TELEGRAM_CHAT_ID` (positive integer for personal DMs; negative for groups — out of scope)

This is documented inline in [`.env.example`](../.env.example) (see §5).

---

## 2. Class design

`TelegramChannel(BaseNotificationChannel)` mirrors [`WhatsAppChannel`](../src/notifier.py:440) structure 1:1. Reuses [`SendResult`](../src/notifier.py:54) and the [`BaseNotificationChannel`](../src/notifier.py:80) ABC unchanged.

```python
class TelegramChannel(BaseNotificationChannel):
    _TELEGRAM_TEXT_LIMIT: int = 4096                             # same as WhatsApp
    _API_BASE: str = "https://api.telegram.org"

    @property
    def channel_name(self) -> str: return "telegram"

    @staticmethod
    def _build_ssl_context() -> ssl.SSLContext: ...              # COPY from WhatsAppChannel — PANW root CA pattern

    def get_recipient(self, config) -> str: ...                  # returns TELEGRAM_CHAT_ID
    def is_enabled(self, config) -> bool: ...                    # config["telegram"]["enabled"]

    @staticmethod
    def _classify_telegram_error(status_code: int, body_text: str) -> tuple[str, str]: ...

    @classmethod
    def validate_token(cls, bot_token=None, timeout=10.0) -> SendResult: ...   # GET /bot<token>/getMe

    def send(self, listings, config) -> bool: ...                # thin wrapper → send_with_diagnostics
    def send_with_diagnostics(self, listings, config) -> SendResult: ...

    def _build_text_body(self, listings) -> str: ...             # near-identical to WhatsAppChannel._build_text_body
```

### Config + env wiring

| Source | Key | Default | Purpose |
|--------|-----|---------|---------|
| `config.yaml` | `telegram.enabled` | `false` | Master toggle (writable from Settings page) |
| `config.yaml` | `telegram.parse_mode` | `"HTML"` | `"HTML"` or `"MarkdownV2"` (sticky to HTML for v1) |
| `.env` | `TELEGRAM_BOT_TOKEN` | — | Secret bot token (never in config.yaml) |
| `.env` | `TELEGRAM_CHAT_ID` | — | Recipient — env var (not config.yaml) since it's user-specific and pairs with the token |

### Why `TELEGRAM_CHAT_ID` is in `.env`, not `config.yaml`

WhatsApp's recipient is in `config.yaml` (writable from the Settings UI) because it's a phone number — semi-public. A Telegram `chat_id` is a numeric user ID that's tightly coupled to the bot token; treating it as a co-secret keeps the (token, chat_id) pair atomic and prevents someone with read-only `config.yaml` access from learning the operator's Telegram ID. Settings page **displays** the value (read-only) but does NOT write it.

### `validate_token` (startup probe)

`GET https://api.telegram.org/bot<token>/getMe` — returns the bot's profile (id, username) on success. Free, no rate cost. Mirrors [`WhatsAppChannel.validate_token`](../src/notifier.py:608) exactly.

### SSL handling

**Reuse the PANW Enterprise Root CA pattern verbatim** ([`src/notifier.py:464`](../src/notifier.py:464)). The user is behind a Palo Alto Networks GlobalProtect TLS-decryption proxy; without the custom CA + cleared `VERIFY_X509_STRICT` flag, `https://api.telegram.org` will fail with cert verification errors at runtime. Copy `_build_ssl_context()` byte-for-byte (or hoist it to a module-level function — see §7).

---

## 3. Message format

Mirror [`WhatsAppChannel._build_text_body`](../src/notifier.py:813) but use Telegram HTML for the URL so it renders as a tappable link instead of a raw URL:

```
🏠 3 new listings in Sunnyvale

• <a href="https://www.zillow.com/...">123 Main St — $5,800/mo, 3BR</a>
  123 Main St, Sunnyvale, CA · 1,200 sqft (111 m²)
• <a href="https://...">456 Oak Ave — $6,200/mo, 4BR</a>
  456 Oak Ave, Sunnyvale, CA · 1,450 sqft (135 m²)
…and 1 more
```

### Rules

- `parse_mode=HTML` in the request body
- Escape listing fields with `html.escape()` before substitution (XSS-equivalent: a malicious listing title with `<script>` would be rendered inert by Telegram, but escape regardless — defense in depth, matches [security-patterns.md](../docs/memory/wiki/concepts/security-patterns.md))
- `disable_web_page_preview=true` — otherwise Telegram fetches a thumbnail of the first URL and inflates the message; we want compact lines
- Truncate at **4000 chars** (per task brief — leaves 96-char headroom under the 4096 limit; the existing WhatsApp code reserves only ~30. Use 4000 as a clearer safety margin)
- Append "…and N more" footer when truncated (verbatim from WhatsApp)
- Per [Design Bible](../docs/design/design-bible.md) §"Show area in BOTH sqft AND m²", show area as `1,200 sqft (111 m²)` when sqft is present (NEW vs. WhatsApp which only shows BR — call this out in the implementation PR)

### What NOT to do

- ❌ No emoji-heavy formatting (1 emoji per message header is enough)
- ❌ No MarkdownV2 — its escape rules are notoriously fragile (every `.`, `-`, `(`, `)`, `=`, etc. must be backslash-escaped). HTML's escape surface is just `& < >` via `html.escape()`. Stick to HTML.
- ❌ No inline keyboards / buttons (P3 backlog)

---

## 4. Error categorization

Map Telegram API errors to existing [`SendResult.error_category`](../src/notifier.py:54) values. **Reuse** the existing taxonomy — do NOT invent new categories.

| Telegram response | Category | Notes |
|-------------------|----------|-------|
| HTTP 200 + `{"ok": true}` | success | — |
| HTTP 401 | `auth` | Bot token invalid or revoked via BotFather (no auto-expiry). Surface "regenerate token via @BotFather" in error_message. |
| HTTP 403 + `description` contains `"bot was blocked by the user"` | `recipient_refused` | User blocked the bot; cannot recover server-side |
| HTTP 403 + `description` contains `"chat not found"` | `recipient_refused` | Wrong/stale `TELEGRAM_CHAT_ID` |
| HTTP 400 + `description` contains `"chat not found"` | `recipient_refused` | Same — Telegram is inconsistent on whether this is 400 or 403 |
| HTTP 400 + other | `api_error` | Bad request body (e.g., malformed HTML in `text`) |
| HTTP 429 + `parameters.retry_after` (int seconds) | `rate_limited` | Include `retry_after` in error_message; we send ≤ 2/day so this should never fire in practice |
| HTTP 5xx | `api_error` | Telegram-side outage |
| `httpx.ConnectError` / `httpx.TimeoutException` / `OSError` | `network` | DNS, connection, timeout |
| `ImportError` (no httpx) | `unexpected` | Same as WhatsApp |
| Other unhandled `Exception` | `unexpected` | Catch-all with `logger.exception` |
| `telegram.enabled: false` | `disabled` | Pre-flight short-circuit |
| Missing `TELEGRAM_BOT_TOKEN` or `TELEGRAM_CHAT_ID` | `missing_credentials` | Pre-flight short-circuit |
| `listings == []` | `no_listings` | Pre-flight short-circuit |

### Notable non-mapping

There is **no** `token_expired` for Telegram — bot tokens don't auto-expire. If the user revokes via BotFather, we get HTTP 401 → `auth`. The admin banner for `auth` is generic enough to cover both SMTP auth and Telegram bot revocation; no UI changes needed for the banner copy beyond the recipient identifier.

### `_classify_telegram_error` skeleton

```python
@staticmethod
def _classify_telegram_error(status_code: int, body_text: str) -> tuple[str, str]:
    description = ""
    retry_after = None
    try:
        parsed = json.loads(body_text)
        description = str(parsed.get("description", "") or "").lower()
        retry_after = parsed.get("parameters", {}).get("retry_after")
    except (ValueError, TypeError, json.JSONDecodeError):
        pass

    if status_code == 401:
        return "auth", (
            "Telegram bot token invalid (HTTP 401). "
            "Check TELEGRAM_BOT_TOKEN in .env, or regenerate via @BotFather → /revoke → /token."
        )
    if status_code == 429:
        ra = f" retry_after={retry_after}s" if retry_after else ""
        return "rate_limited", f"Telegram rate-limited (HTTP 429){ra}: {description[:200]}"
    if "bot was blocked by the user" in description or "chat not found" in description:
        return "recipient_refused", (
            f"Telegram recipient refused (HTTP {status_code}): {description[:200]}. "
            "Verify TELEGRAM_CHAT_ID and that the user has not blocked the bot."
        )
    if status_code == 400:
        return "api_error", f"Telegram bad request (HTTP 400): {description[:200]}"
    return "api_error", f"Telegram API HTTP {status_code}: {description[:200] or body_text[:200]}"
```

---

## 5. Files to add/modify

| File | Change | Purpose |
|------|--------|---------|
| [`src/notifier.py`](../src/notifier.py) | **add** `TelegramChannel` class after `WhatsAppChannel` | The channel itself |
| [`scripts/run-notify.py`](../scripts/run-notify.py) | **modify** import + `channels=[…]` list | Register `TelegramChannel()` alongside `EmailChannel()` and `WhatsAppChannel()` |
| [`web/main.py`](../web/main.py) | **modify** startup hook | Call `TelegramChannel.validate_token()` when `config["telegram"]["enabled"]` (mirrors WhatsApp probe) |
| [`web/routes/admin.py`](../web/routes/admin.py) | **modify** `notifications` route handler | Compute `telegram_last_failure` (via `get_last_channel_failure("telegram", within_hours=48)`) + `telegram_credentials_ok`; pass to template context |
| [`web/templates/admin/notifications.html`](../web/templates/admin/notifications.html) | **modify** | Add Telegram credential warning banner + Telegram failure banner block (mirroring WhatsApp pattern from 2026-05-08); add "💬 Telegram failure" badge per `notification_log` row when `channel == "telegram"` and `success = 0` |
| [`web/templates/admin/settings.html`](../web/templates/admin/settings.html) | **modify** | Add Telegram row: enabled toggle + read-only `chat_id` display + read-only bot username (from `validate_token` cache if available) |
| [`web/static/css/admin.css`](../web/static/css/admin.css) | **bump** `?v=N` in [`web/templates/admin/base.html`](../web/templates/admin/base.html) | Per [CSS Cache Versioning](../docs/memory/wiki/concepts/css-cache-versioning.md) — even if no new CSS rules are added, bump prevents stale rendered HTML in the user's browser |
| [`config.yaml`](../config.yaml) | **add** `telegram:` section | `enabled: false`, `parse_mode: HTML` — flip `enabled: true` after user confirms bot setup |
| [`config.yaml`](../config.yaml) | **modify** | `whatsapp.enabled: true` → `whatsapp.enabled: false` (disable but keep the section for future re-enablement) |
| [`.env.example`](../.env.example) | **add** | `TELEGRAM_BOT_TOKEN=` + `TELEGRAM_CHAT_ID=` placeholders + 4-line bot-setup comment |
| [`src/utils.py`](../src/utils.py) | **add** | `get_telegram_settings()` (read) + `update_telegram_settings()` (write `enabled` only, NOT `chat_id` — that's env-only) — mirrors [`get_whatsapp_settings`](../src/utils.py) shape |

**Total:** 8 modified, 2 added (well, 1 add + 1 effective add via `TelegramChannel` class). No DB migration — `notification_log` already has the `error_category`/`error_message` columns it needs.

---

## 6. Test plan

### 6a. Unit/integration tests

| File | Type | Purpose |
|------|------|---------|
| [`scripts/test_telegram_notification.py`](../scripts/test_telegram_notification.py) | end-to-end (manual) | Mirrors [`scripts/test_email_notification.py`](../scripts/test_email_notification.py) — sends a test Telegram message using real credentials. Run: `.venv/bin/python scripts/test_telegram_notification.py`. Pass/fail criterion: message appears in user's Telegram + `notification_log` row with `success=1`. |
| `scripts/test_telegram_classification.py` (or inline `tests/`) | mock-based unit | Patches `httpx.Client` with [`respx`](https://lundberg.github.io/respx/) (already in `requirements.txt` if present, else use `unittest.mock`) and asserts `_classify_telegram_error` returns the expected `(category, message)` tuple for: (a) 401 invalid token, (b) 403 "bot was blocked", (c) 400 "chat not found", (d) 429 with `retry_after=10`, (e) 500 server error, (f) network exception. Six cases, one assert each. |
| `scripts/test_telegram_validate_token.py` | mock-based unit | Patches `httpx.Client.get` to return (a) 200 with `{"ok": true, "result": {"username": "test_bot"}}` → asserts `SendResult(success=True)`; (b) 401 → asserts `success=False, error_category="auth"`. Two cases. |

**No new test infrastructure required** — these mirror the (informal) ad-hoc test scripts already in `scripts/test_*.py`. If the user prefers `pytest` later, easy to migrate.

### 6b. Manual end-to-end checklist

1. ☐ User creates bot via `@BotFather`, captures `TELEGRAM_BOT_TOKEN`
2. ☐ User DMs the bot once, captures `chat_id` via `getUpdates`
3. ☐ User pastes both into `.env`
4. ☐ User flips `telegram.enabled: true` in `config.yaml`
5. ☐ User flips `whatsapp.enabled: false` in `config.yaml` (turn off the unreliable channel)
6. ☐ Run: `.venv/bin/python scripts/test_telegram_notification.py` → expect message in Telegram
7. ☐ Run: `.venv/bin/python scripts/run-notify.py` → expect Telegram message + `notification_log` row + Email still works
8. ☐ Restart FastAPI server, hit `/admin/` → System Health shows `TELEGRAM_BOT_TOKEN: ✓`, `TELEGRAM_CHAT_ID: ✓`
9. ☐ Hit `/admin/notifications` → Telegram section visible, no warning banners
10. ☐ Hit `/admin/settings` → Telegram row shows `enabled: true`, `chat_id` (masked: last 4 digits), bot username

### 6c. Failure-path verification (before approving the PR)

- ☐ Temporarily set `TELEGRAM_BOT_TOKEN=garbage` → restart → `/admin/notifications` shows `auth` failure banner; `notification_log` row has `error_category="auth"`
- ☐ Temporarily blank `TELEGRAM_CHAT_ID` → restart → `/admin/notifications` shows `missing_credentials` warning banner

Per [§6 Runtime Verification](../AGENTS.md), Code mode MUST `curl /admin/notifications` after the change and confirm the HTML output contains the expected Telegram block + no `&#x` raw entities.

---

## 7. Implementation notes (for Code mode)

### Should `_build_ssl_context` be hoisted to module level?

Currently it's a `@staticmethod` on `WhatsAppChannel` ([`src/notifier.py:464`](../src/notifier.py:464)). Adding `TelegramChannel` makes a second copy. Two options:

- **Option A (minimal change, recommended):** copy the static method into `TelegramChannel`. Adds ~30 lines of duplication. Easy to read, no refactor risk. Pick this.
- **Option B (hoist):** extract to module-level `_build_ssl_context()` function used by both. Cleaner long-term, but it's a refactor that should be its own PR per the "one logical change per PR" review-cycle norm. **Defer** to a follow-up cleanup task.

Code Reviewer can call out the duplication as a P3 if desired, but do NOT block the Telegram PR on it.

### Httpx client lifecycle

Match [`WhatsAppChannel.send_with_diagnostics`](../src/notifier.py:679) pattern: open a `with httpx.Client(timeout=30, verify=ssl_ctx) as client:` block per send. We send ≤ 2 messages/day; no need for a long-lived client.

### Logging

- One `INFO` line on send attempt: `"Sending Telegram notification (%d listing(s)) to chat_id=%s"` (mask all but last 4 digits of chat_id)
- One `INFO` line on success: `"Telegram notification sent successfully to chat_id=%s"`
- One `ERROR` line on non-2xx: `"Telegram API returned HTTP %d: %s"` — include first 500 chars of body
- `logger.exception` for the catch-all `Exception` handler — per the 2026-05-08 sub-rule in [Silent Failure Pattern](../docs/memory/wiki/concepts/silent-failure-pattern.md): never speculate in log messages

### Wiki impact (post-implementation, NOT this spec)

After Code → Review approves the implementation, update:

- **Existing entity:** [`notification-system.md`](../docs/memory/wiki/entities/notification-system.md) — add Telegram channel row to Architecture + Configuration sections; add "Telegram channel added" history entry; update `Owner files` to confirm `src/notifier.py` still owns it
- **Existing entity:** [`config-yaml.md`](../docs/memory/wiki/entities/config-yaml.md) — add `telegram` section row to Sections table; bump Last updated
- **Existing entity:** [`admin-dashboard.md`](../docs/memory/wiki/entities/admin-dashboard.md) — Notifications page row now mentions Telegram banner too; bump Last updated
- **Concept page:** [`silent-failure-pattern.md`](../docs/memory/wiki/concepts/silent-failure-pattern.md) — add a row to "Variants" table noting Telegram has no token-expiry equivalent (a *positive* note: Telegram closes the WhatsApp variant by removing the failure mode at the source)
- **Index + log:** bump `Last updated` in [`index.md`](../docs/memory/wiki/index.md), append entry to [`log.md`](../docs/memory/wiki/log.md)

---

## 8. Out of scope

Explicit non-goals — do NOT expand scope without a new spec:

- ❌ **Removing WhatsApp** — keep the class + tests; only `whatsapp.enabled: false` in config. Re-enablement is a one-line config flip if Meta ever ships production-grade for free.
- ❌ **MarkdownV2** — escape rules are too fragile for the marginal styling benefit
- ❌ **Inline keyboards / interactive buttons** — adds webhook-receiver complexity (would need a public callback URL); P3 future
- ❌ **Multi-recipient broadcast** — single `TELEGRAM_CHAT_ID` is enough for this single-user tool. Adding more recipients is one new env var (`TELEGRAM_CHAT_IDS=id1,id2`) — a 5-minute change when needed
- ❌ **Group chats / channels** — only personal DMs in v1. Group `chat_id` values are negative integers (e.g., `-1001234567890`); adding bot to a group requires extra `/setjoingroups` BotFather toggle. Not blocked by design — `chat_id` field accepts negative ints transparently — just untested
- ❌ **Photo / media attachments** — `sendPhoto` endpoint exists but text-only is sufficient (URL preview already disabled to keep messages compact)
- ❌ **Webhook for delivery confirmations** — Telegram doesn't have a "delivered/read" webhook for outgoing bot messages anyway (only incoming user messages)
- ❌ **Refactoring `_build_ssl_context` to module level** — see §7 Option B; defer to a separate cleanup PR
- ❌ **Migrating `scripts/test_*.py` to pytest** — out of scope for this feature

---

## Wiki Impact

- **New entities:** none — `TelegramChannel` is a new class within an existing entity ([`notification-system.md`](../docs/memory/wiki/entities/notification-system.md))
- **Updated entities (after impl):** [`notification-system.md`](../docs/memory/wiki/entities/notification-system.md), [`config-yaml.md`](../docs/memory/wiki/entities/config-yaml.md), [`admin-dashboard.md`](../docs/memory/wiki/entities/admin-dashboard.md)
- **New concepts:** none
- **Updated concepts (after impl):** [`silent-failure-pattern.md`](../docs/memory/wiki/concepts/silent-failure-pattern.md) — add Telegram as a "variant closed at the source" note

---

## Negative consequences (mandatory ADR section)

Per [`.roo/skill-architect-design-review.md`](../.roo/skill-architect-design-review.md), every design decision must surface its downsides:

1. **More code to maintain** — a third channel adds ~250 LOC to [`src/notifier.py`](../src/notifier.py) (now ~1100 lines, would become ~1350). Mitigation: structure mirrors WhatsApp 1:1, so the cognitive load per channel stays flat.
2. **Vendor lock-in to Telegram** — if Telegram itself becomes hostile (rare but not impossible), we're back where we started. Mitigation: the `BaseNotificationChannel` ABC means we can swap to Signal / Discord / SMS by adding a 4th class; existing channels keep working.
3. **PANW root CA SSL pattern duplicated for the 2nd time** — accepted technical debt; flagged for follow-up refactor (§7 Option B).
4. **`TELEGRAM_CHAT_ID` in `.env` (not `config.yaml`)** is inconsistent with WhatsApp's `recipient_phone` (which is in `config.yaml`). Reasoning in §2; the inconsistency is intentional but documented to avoid future confusion.
5. **No delivery confirmation** — Telegram doesn't expose "user read this message" for bot messages. Same blind spot as WhatsApp had with `delivered`/`read` webhooks (we never implemented those). Acceptable for a single-user tool where the user can self-verify.
6. **Test Number → Production hesitation** — by switching to Telegram instead of fixing WhatsApp's Test Number → Production migration, we never validate that path. If a future user wants WhatsApp specifically, they'll need to redo that migration work. Acceptable for now.

---

*End of spec. Ready for Code mode delegation.*
