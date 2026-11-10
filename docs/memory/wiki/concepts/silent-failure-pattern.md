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
3. **Rate limiters count only what they're meant to ration.** When the resource being protected is **the recipient's inbox** (e.g., daily-cap notifications), count **successful sends** — failures are non-events, and counting them lets transient network blips silently consume the cap and block recovery (2026-06-03 silent-Telegram regression). When the resource is **a misbehaving channel's outbound bandwidth** (rare — typically a separate per-channel circuit-breaker, not the user-facing cap), counting attempts is fine. The 2026-03-31 generation of this rule said "count ALL attempts to prevent unlimited failure spam" — that turned out to be the *cause* of a 7-day Telegram silence; see [Notification System](../entities/notification-system.md) anti-spam guard.
4. **Add pre-flight checks before expensive operations** — check credentials BEFORE querying DB, building emails, or connecting to SMTP
5. **One scheduler instance only** — multiple processes each running their own scheduler multiplied the failures
6. **Environment variables must persist across restarts** — use `.env` file with `load_dotenv()`, not terminal session vars

## Examples

- **Zillow scraper:** Returns `[]` with a warning log when `RAPIDAPI_KEY` is missing — no error, no exception
- **SMTP notifier:** Pre-flight check added — skips pipeline early with `skipped_reason` when credentials missing
- **Anti-spam guard:** Inverted twice — originally counted successes, changed to count all attempts on 2026-03-31 ("prevent unlimited failure spam"), then **inverted back on 2026-06-03 to count successes only** after the "count all" semantics caused a 7-day silent Telegram silence. The lesson: pick the count semantic based on what resource is being rationed (see Rule #3 above).

### Safeguards Now in Place
- `_validate_environment()` runs at every FastAPI startup (now also live-probes the WhatsApp token via `WhatsAppChannel.validate_token()` when the channel is enabled)
- System Health panel on admin dashboard (`/admin/`)
- SMTP warning banner on Notifications page
- WhatsApp credential / API token warning banner on Notifications page
- API key warning banner on API Usage page
- Pre-flight credential check in `NotificationService.run()`
- Anti-spam guard counts successful sends only (`success=True`) — see Rule #3 for the rationale and the 2026-06-03 regression that drove this back-inversion
- **Silence-detector banner on user dashboard** (2026-06-03) — red banner at `/` when no successful notification in 48h AND matching unnotified listings exist. Surfaces silence proactively; operators don't need to visit `/admin/notifications` to discover broken pipelines. Closes the "operator only notices by visiting the admin page" failure mode that gated the 2026-06-03 incident at 7 days.
- **Categorised failure logging in `notification_log`** (2026-05-08) — channels return a `SendResult` with `error_category` + `error_message`; admin UI surfaces a prominent red banner when the most-recent send for a channel was a `token_expired`/`auth` failure within the last 48 h. Catches the WhatsApp-Test-Number 24 h token-expiry pattern that previously failed silently.

### Variants of This Pattern Surfaced So Far
| Date | Feature | Failure Mode | Resolution |
|------|---------|--------------|------------|
| 2026-03-31 | Zillow scraper | `RAPIDAPI_KEY` missing → empty results | Startup validation + System Health banner |
| 2026-03-31 | SMTP notifier | `SMTP_PASSWORD` missing → 0% success | Startup validation + SMTP warning banner + anti-spam counts attempts |
| 2026-05-08 | WhatsApp notifier | `WHATSAPP_API_TOKEN` expired (~24 h Test Number lifetime) → HTTP 401 logged but no banner; user only noticed missing messages | `error_category="token_expired"` in `notification_log` + red error banner + per-row badge + startup token live-probe |
| 2026-05-08 | Cross-source deduplication | `_merge_duplicate()` always raised `IntegrityError` (UNIQUE on `listing_sources(source, external_id)`); broad `except IntegrityError` caught it and logged `WARNING "possible race condition, skipping"` → **zero cross-source merges for ~6 weeks** while the dashboard quietly accumulated duplicate cards (1426 Ormsby Dr appeared 3× before user noticed) | Query-then-reassign the existing `ListingSource` instead of INSERTing a new one; replaced `logger.warning("possible race condition")` with `logger.exception("investigate")` so future regressions surface a traceback. One-shot [`scripts/backfill_dedup.py`](../../../../scripts/backfill_dedup.py) merges historical orphans (6 clusters / 8 rows in prod). |
| 2026-05-10 | Telegram notifier (new channel) | **Closed at the source.** Telegram bot tokens never auto-expire (no Test Number / 24h equivalent), and there is no recipient allowlist (the user just `/start`s the bot once). The WhatsApp variant of this pattern (token expiry + invisible recipient drops) does not occur. Bot token revocation by user via BotFather still surfaces as `error_category="auth"` (HTTP 401) — visible via the existing red error banner pattern. | Adopt Telegram as the primary push channel; flip `whatsapp.enabled: false`. Reuse existing `error_category` taxonomy (no new categories needed). `TelegramChannel.validate_token()` startup probe via `getMe` mirrors WhatsApp's. |
| 2026-06-03 | Anti-spam guard (notifier) | 2 morning network-DNS failures (launchd fired before VPN was up) inserted 2 `success=0` rows in `notification_log`. The "count ALL attempts" anti-spam guard interpreted those as 2 sends, hit the 2/day cap, and silently skipped the PM recovery run — even though the network had recovered by then. New listings kept arriving and being logged as "unnotified"; nothing was ever delivered. User noticed 7 days later by visiting the dashboard. | (1) Invert anti-spam guard to count successful sends only (Rule #3 inversion). (2) Add dashboard silence-detector banner on `/` so silence is visible without an admin-page visit. (3) Shift AM trigger 08:00→10:00 to mitigate the launchd-vs-VPN startup race. (4) Extract `load_notification_filters()` as the single source of truth for filter logic so the silence detector cannot drift from the notifier. (5) New regression test `test_anti_spam_guard.test_ist_day_boundary_not_utc_day` guards the IST-window fix that landed in the same diff. |
| 2026-06-04 | Zillow scraper (response trust) | User reported 1525 Bittern Dr displayed as $6,200/mo active rental; actual Zillow.com state was "Off market" / for sale at $2.98M. Two-layered silent failure: (A) [`normalize()`](../../../src/scrapers/zillow_scraper.py:268) trusted that sending `listingStatus=For_Rent` as a request parameter would ensure only rentals in the response — but the RapidAPI provider's index returned an off-market for-sale row with a stale rental price; (B) [`mark_inactive()`](../../../src/database.py:824) deactivated on a single missing scrape, but the provider's index is flaky enough that one daily "hit" kept the stale row "active" forever. Compound effect: a $2.98M for-sale property displayed as a $6,200 rental for an unknown number of days. | (1) Top-of-function status guard in `normalize()` rejecting items where `property.listing.listingStatus != "forRent"` OR `marketingStatus != "active"` (case-insensitive; returns `None`). Orchestrator handles `None` with a per-source `normalize_filtered` debug-log counter. (2) New `consecutive_misses` column + `MARK_INACTIVE_MISS_THRESHOLD = 3` hysteresis counter in `mark_inactive()` — closes the flaky-upstream variant for ALL sources. (3) 15 new regression tests across `scripts/test_zillow_status_filter.py` + `scripts/test_mark_inactive_counter.py`. (4) One-shot [`scripts/deactivate_stale_zillow.py`](../../../scripts/deactivate_stale_zillow.py) for the user to clear the visible ghost row immediately. |

### Sub-rule reinforced (2026-05-08)
**Never tag an actual exception path with a benign log message.** The "possible race condition, skipping" wording was *plausible enough* that it stopped any operator (and any LLM agent reading logs) from investigating further — for ~6 weeks. Two preventive habits, both now codified:
1. **`logger.exception(...)` for caught exceptions** — includes the full traceback, makes the failure mechanism visible, and won't be mistaken for normal ops.
2. **Don't speculate in the log message about *why* the exception happened.** If you don't know, write `"…investigate"` not `"…possible race condition"`. Speculation in logs becomes the next reader's prior, and the prior is rarely re-examined.

### Sub-rule added (2026-06-03) — Docstring drift as silent failure
The 2026-06-03 round-1 Code Reviewer caught a docstring in [`src/database.py`](../../../src/database.py) `get_today_notification_count()` claiming "uses timezone-aware date calculation (UTC+3) … preventing off-by-one miscounts near midnight" — but the actual SQL used `func.date(sent_at) == today` against a naive-UTC column, so the bug was NOT closed. **Stale docstrings cause the same harm as stale log messages.** Both become the next reader's prior, and the prior is rarely re-examined.
1. **When inverting a behavior, `grep` for every docstring or comment that references the old behavior and update them in the same diff.** Especially cross-references like "consistent with `X`" — invert the function, leave the docstring, and the docstring becomes a trap.
2. **Don't overpromise in a docstring.** Either implement the claimed property or soften the claim to match what the code actually does. The 2026-06-03 round-2 fix took the implement-it-properly path (UTC-bounded window translated from IST midnight).

### Sub-pattern added (2026-06-03) — Duplication as silent failure
When two consumers must apply *the same* logic in lockstep (e.g., the notifier deciding "what to send" and the silence detector deciding "what we *would have* sent"), copy-pasting the logic into both creates a silent-failure surface — any future change to one site silently desynchronizes the pair. The silence detector would then silently false-positive (or false-negative), defeating its purpose as a silence-detection mechanism. **Rule:** when paired consumers must stay in lockstep, factor the shared logic into a single helper with a docstring that names both consumers. Example: [`notifier.load_notification_filters()`](../../../src/notifier.py:1345) is the single source of truth for filter extraction; consumed by `NotificationService.run()` and `web.routes.dashboard._compute_notification_silence_state()`.

### Sub-pattern added (2026-06-04) — Trust-the-provider scraper pattern
A request-side filter parameter (`?listingStatus=For_Rent`, `?status=active`, `?include_closed=false`, etc.) is a **request** to the upstream provider — not a **guarantee** about the response. Providers' indexes drift, cache stale rows, and occasionally return items that don't match the filter. **Rule:** every scraper that relies on a request-side filter for correctness MUST re-validate the response-side equivalent fields in `normalize()`. If validation fails, return `None` (the orchestrator now treats `None` as a skip signal — see [Orchestrator](../entities/orchestrator.md)). Pair this defensive-normalize rule with a lifecycle hysteresis counter (`consecutive_misses ≥ N` before deactivation) so the *opposite* failure mode — provider correctly omits a withdrawn listing but intermittently re-includes it — also resolves cleanly. Both layers are required: each alone is insufficient. Live example: [Zillow Scraper](../entities/zillow-scraper.md) 2026-06-04 Bug A + Bug B (one user-visible bug, two layered defects). **Anti-pattern:** "We're already passing `listingStatus=For_Rent`, so the response must be rentals" — this assumption silently corrupted DB state for ~2 days before a user noticed.

## Related

- [Environment Validation](environment-validation.md) — the fix for this pattern
- [Security Patterns](security-patterns.md) — env vars for secrets
- [Zillow Scraper](../entities/zillow-scraper.md) — affected by API key silent failure
- [Notification System](../entities/notification-system.md) — affected by SMTP silent failure
