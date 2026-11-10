# P3 Backlog — Deferred Non-Blocking Issues

> **Purpose:** A persistent queue of P3 (non-blocking) issues surfaced by Code Review cycles. The Code → Review → Fix loop ships only P0/P1/P2; P3s land here for fix-on-demand.
>
> **How to use:** Tell the Orchestrator *"fix all open P3s"* (or *"fix the dedup P3s"*, *"fix the WhatsApp P3s"*) to spawn a new Code task that consumes one or more rows from this file.
>
> **How entries are added:** Per [`docs/memory/wiki/concepts/review-cycle.md`](wiki/concepts/review-cycle.md) §"Severity-based fix-cycle scope", the Orchestrator appends a row here for every P3 the Code Reviewer reports, with attribution to the source task and a copy of the reviewer's suggested fix.
>
> **How entries are removed:** When a fix lands, set `Status` to `closed YYYY-MM-DD` (don't delete — the closed history is useful for audits). Use `wontfix YYYY-MM-DD` if a row is consciously rejected, with a one-line reason.
>
> **Triage policy:** This file is global / single-source. If it grows past ~30 open rows, split per-feature (one file per wiki entity). See [`docs/memory/wiki/concepts/review-cycle.md`](wiki/concepts/review-cycle.md) for the rationale.

**Open count:** 54 · **Last refreshed:** 2026-06-04

---

## Open P3s — Zillow Stale-Rental Lifecycle

Source entity: [`wiki/entities/zillow-scraper.md`](wiki/entities/zillow-scraper.md) · [`wiki/entities/orchestrator.md`](wiki/entities/orchestrator.md)

### ZILLOW-STALE-P3-1 — Legacy 30% safety threshold is now redundant with `consecutive_misses` hysteresis

| Field | Value |
|---|---|
| **Date added** | 2026-06-04 |
| **Source task** | Zillow stale-rental fix (Round-1 Code Review) |
| **File:Line** | [`src/orchestrator.py:225-249`](../../src/orchestrator.py:225) |
| **Severity** | P3 |
| **Status** | open |
| **Why it matters** | The 30%-of-active-IDs check now duplicates the safety that `MARK_INACTIVE_MISS_THRESHOLD=3` provides. Two layers are safe to coexist (Reviewer verified) but the older layer's comment ("P2-8") is now misleading — a future reader could either (a) try to remove the counter thinking the 30% check is enough, or (b) think the 30% check is load-bearing and refuse to remove it during cleanup. P3 (not P2) because either resolution path is a strict simplification with zero behavior change. |
| **Suggested fix** | Either (a) delete the 30% guard and update the comment in `mark_inactive` to mention this was the previous belt-and-suspenders, OR (b) keep both but replace the "P2-8" comment with "Defense-in-depth: outer 30% guard covers fully-failed scrapes; inner `consecutive_misses` counter (Bug B, 2026-06-04) covers transient single-zpid drops". Pick one to land within 1 review cycle so the next reader has a clean story. |

### ZILLOW-STALE-P3-2 — Status validation missing on Craigslist and Realtor adapters

| Field | Value |
|---|---|
| **Date added** | 2026-06-04 |
| **Source task** | Zillow stale-rental fix (Round-1 Code Review) |
| **File:Line** | [`src/scrapers/craigslist_scraper.py:274`](../../src/scrapers/craigslist_scraper.py:274), [`src/scrapers/realtor_scraper.py:326`](../../src/scrapers/realtor_scraper.py:326) |
| **Severity** | P3 |
| **Status** | open |
| **Why it matters** | Neither source currently exposes a useful `listingStatus`-equivalent field, but if a future API/HTML change exposes one (e.g., Realtor adds `listingStatus`), the same class of "off-market shown as active" bug could surface. The `dict \| None` return contract is already in place via [`base.py:82`](../../src/scrapers/base.py:82), so the adapter side is ready; only the validation logic is missing. |
| **Suggested fix** | When a new status field appears upstream, add the equivalent guard following the Bug A template ([`zillow_scraper.py:304-339`](../../src/scrapers/zillow_scraper.py:304)). Until then, no change needed — log this so the next person scraping a status field doesn't reinvent the pattern. |

### ZILLOW-STALE-P3-3 — `mark_inactive()` should refuse to act on an empty `active_ids` list

| Field | Value |
|---|---|
| **Date added** | 2026-06-04 |
| **Source task** | Zillow stale-rental fix (Round-1 Code Review) |
| **File:Line** | [`src/database.py:879-886`](../../src/database.py:879) |
| **Severity** | P3 |
| **Status** | open |
| **Why it matters** | The orchestrator's `if seen_external_ids:` guard ([`orchestrator.py:245`](../../src/orchestrator.py:245)) currently protects this code path, but `mark_inactive` is a module-public function. A direct caller from a future script or REPL session passing `[]` would silently increment every active listing of that source (the `else True` branch at [line 881](../../src/database.py:881) becomes a tautology). After 3 such calls, every listing of that source would be deactivated. Defense-in-depth gap. |
| **Suggested fix** | Add an early-return guard at the top of `mark_inactive`: `if not active_ids: logger.warning("mark_inactive called with empty active_ids for source=%s — refusing to act (likely scraper failure)", source); return`. Also add a regression test `test_empty_active_ids_is_noop` in [`scripts/test_mark_inactive_counter.py`](../../scripts/test_mark_inactive_counter.py) — assert no counter changes and no deactivations after `mark_inactive("zillow", [])`. |

### ZILLOW-STALE-P3-4 — Extract upsert exclusion tuples into named constants

| Field | Value |
|---|---|
| **Date added** | 2026-06-04 |
| **Source task** | Zillow stale-rental fix (Round-1 Code Review) |
| **File:Line** | [`src/database.py:442`](../../src/database.py:442), [`src/database.py:501`](../../src/database.py:501) |
| **Severity** | P3 |
| **Status** | open |
| **Why it matters** | This is the second time fields have been added to both exclusion tuples ([`upsert-exclusion-pattern.md`](wiki/concepts/upsert-exclusion-pattern.md) Rule #6 already suggested this from the 2026-03-31 review). With `consecutive_misses` joining `notified`, `is_favorite`, `is_disliked`, `deactivated_at`, `listed_date`, `first_seen`, `source`, `external_id`, `url`, `id`, the inline tuple at [line 501](../../src/database.py:501) is now 11 items long and a future contributor will inevitably add a field to one tuple but not the other. |
| **Suggested fix** | Extract two module-level constants: `_UPSERT_PRIMARY_EXCLUDE = ("id", "first_seen", "listed_date", "notified", "is_favorite", "is_disliked", "deactivated_at", "consecutive_misses")` and `_UPSERT_MERGED_EXCLUDE = _UPSERT_PRIMARY_EXCLUDE + ("source", "external_id", "url")`. Reference them in both `for key, value in listing_data.items():` loops. Update [`wiki/concepts/upsert-exclusion-pattern.md`](wiki/concepts/upsert-exclusion-pattern.md) Rule #6 from "Consider" to "Done — see constants". |

---

## Open P3s — Deduplication

Source entity: [`wiki/entities/deduplication.md`](wiki/entities/deduplication.md)

### DEDUP-P3-1 — Cascade-interaction hardening in `_merge_duplicate()`

| Field | Value |
|---|---|
| **Date added** | 2026-05-08 |
| **Source task** | Cross-source dedup `IntegrityError` fix (Round-1 Code Review) |
| **File:Line** | [`src/dedup.py:271`](../../src/dedup.py:271), [`src/dedup.py:430`](../../src/dedup.py:430) |
| **Severity** | P3 |
| **Status** | open |
| **Why it matters** | A future refactor that removes `session.refresh(dup)` would silently re-introduce the `uq_ls_source_external_id` collision class — the cascade `delete-orphan` interaction with direct FK reassignment is non-obvious. |
| **Suggested fix** | Add `assert not dup.sources` immediately after `session.refresh(dup)` in [`find_and_merge_duplicate()`](../../src/dedup.py:430), and a 2-line comment in [`_merge_duplicate()`](../../src/dedup.py:271) explaining why the query-then-reassign path is required given `cascade="all, delete-orphan"`. |

### DEDUP-P3-2 — Additional dedup test coverage

| Field | Value |
|---|---|
| **Date added** | 2026-05-08 |
| **Source task** | Cross-source dedup `IntegrityError` fix (Round-1 Code Review) |
| **File:Line** | [`scripts/test_dedup_merge.py`](../../scripts/test_dedup_merge.py) |
| **Severity** | P3 |
| **Status** | open |
| **Why it matters** | Current coverage exercises the happy path and the IntegrityError-rollback path. Four scenarios are unprotected — any of them could regress without the test suite noticing. |
| **Suggested fix** | Add four tests:<br>1. `test_three_way_merge` — zillow + craigslist + realtor for same property; assert canonical ends with 3 source rows.<br>2. `test_defensive_fallback_when_no_existing_source_row` — exercises the `else` branch used by backfill's "truly orphaned listing" path.<br>3. `test_integrity_error_path_rolls_back_session_and_returns_none` — patch `flush` to raise; assert rollback + `None` returned + new "investigate" log wording present.<br>4. `test_image_urls_and_price_history_merge` — gap-fill + image union + price-snapshot transfer (currently never asserted). |

### DEDUP-P3-3 — Canonical-picker source-priority sort key

| Field | Value |
|---|---|
| **Date added** | 2026-05-08 |
| **Source task** | Cross-source dedup `IntegrityError` fix (Round-1 Code Review) |
| **File:Line** | [`src/dedup.py`](../../src/dedup.py) — canonical-picker logic |
| **Severity** | P3 |
| **Status** | open |
| **Why it matters** | Current "earliest `first_seen`, id as tie-break" rule can pick a leaner Realtor record over a richer Zillow record (Cluster 2 in the 2026-05-08 backfill dry-run picked `realtor 135` over `zillow 16`). `_GAP_FILL_FIELDS` covers most of the data delta, so this is cosmetic — but the canonical row is what users see. |
| **Suggested fix** | Add a source-priority sort key: `zillow=0, realtor=1, craigslist=2` as primary; `first_seen` as secondary. Document the priority order on [`wiki/entities/deduplication.md`](wiki/entities/deduplication.md) so it's discoverable. |

### DEDUP-P3-5 — Minor nits in `backfill_dedup.py`

| Field | Value |
|---|---|
| **Date added** | 2026-05-08 |
| **Source task** | Cross-source dedup `IntegrityError` fix (Round-1 Code Review) |
| **File:Line** | [`scripts/backfill_dedup.py`](../../scripts/backfill_dedup.py) |
| **Severity** | P3 |
| **Status** | open |
| **Why it matters** | None of the three are functional bugs, but together they hurt readability and one (skip-reason double-counting) makes the summary line harder to trust. |
| **Suggested fix** | (a) Move `from datetime import timezone` to module level. (b) Catch `KeyboardInterrupt` separately from `Exception` so Ctrl-C exits with the partial summary. (c) Audit the skip-reason counter for double-increments in the cluster-loop branches. |

---

## Open P3s — Notification System (WhatsApp)

Source entity: [`wiki/entities/notification-system.md`](wiki/entities/notification-system.md)

### WHATSAPP-P3-1 — Add Meta error code 2500 to OAuth detection set

| Field | Value |
|---|---|
| **Date added** | 2026-05-08 |
| **Source task** | WhatsApp token-expiry detection + visible failure surfacing |
| **File:Line** | `WhatsAppChannel` OAuth-error detection (see entity page for current line) |
| **Severity** | P3 |
| **Status** | open |
| **Why it matters** | Meta's documented OAuth error codes include 2500 (auth-error variant). Current detection set will misclassify a 2500-coded failure as a generic send error → no banner, no token-expiry alert. Probability low (we've never seen 2500 in logs) but cost-of-fix tiny. |
| **Suggested fix** | Add `2500` to the OAuth error code set in `WhatsAppChannel`. Add a unit-test fixture for the 2500 path. |

### WHATSAPP-P3-2 — `meta_message` truncation contract docs

| Field | Value |
|---|---|
| **Date added** | 2026-05-08 |
| **Source task** | WhatsApp token-expiry detection + visible failure surfacing |
| **File:Line** | `notification_log.error_message` write site |
| **Severity** | P3 |
| **Status** | open |
| **Why it matters** | Meta error messages occasionally exceed the column width and get silently truncated. No docs say at how many bytes/codepoints; if a future filter regex matches near the truncation boundary it will silently miss. |
| **Suggested fix** | Document the truncation contract (codepoints vs bytes, exact width) in a `log_notification()` docstring + on [`wiki/entities/notification-system.md`](wiki/entities/notification-system.md). |

### WHATSAPP-P3-3 — Bump startup probe timeout 5s → 10s

| Field | Value |
|---|---|
| **Date added** | 2026-05-08 |
| **Source task** | WhatsApp token-expiry detection + visible failure surfacing |
| **File:Line** | Startup `validate_token()` probe |
| **Severity** | P3 |
| **Status** | open |
| **Why it matters** | 5s is tight for a cold WhatsApp Cloud API endpoint over residential ISP. A spurious timeout at boot would mark the token "invalid" and show the red banner even though it's good. |
| **Suggested fix** | Bump probe timeout from 5s to 10s. Keep all other timeouts unchanged. |

### WHATSAPP-P3-4 — `log_notification()` docstring: codepoint vs byte truncation

| Field | Value |
|---|---|
| **Date added** | 2026-05-08 |
| **Source task** | WhatsApp token-expiry detection + visible failure surfacing |
| **File:Line** | `log_notification()` (notifier module) |
| **Severity** | P3 |
| **Status** | open |
| **Why it matters** | Same root concern as WHATSAPP-P3-2 (truncation behaviour) but specific to the helper function's docstring rather than the column contract. Easy to address together. |
| **Suggested fix** | Add a one-paragraph docstring to `log_notification()` clarifying whether the `error_message` parameter is truncated by codepoint or byte before insert. |

### WHATSAPP-P3-5 — Replace `opacity: 0.7` with `color: #b91c1c` on banner secondary text (WCAG AA)

| Field | Value |
|---|---|
| **Date added** | 2026-05-08 |
| **Source task** | WhatsApp token-expiry detection + visible failure surfacing |
| **File:Line** | `info-banner--error` secondary-text styles in [`web/static/css/admin.css`](../../web/static/css/admin.css) |
| **Severity** | P3 |
| **Status** | open |
| **Why it matters** | `opacity: 0.7` over a tinted background can drop contrast below 4.5:1 — the WCAG AA threshold for body text. Per [`docs/design/design-bible.md`](../design/design-bible.md) banner errors must remain AA-compliant. |
| **Suggested fix** | Drop `opacity: 0.7`; set explicit `color: #b91c1c` (or the design-bible-approved error-secondary token). Verify with a contrast checker against the banner background. **Don't forget** to bump the `?v=N` cache-buster in [`web/templates/admin/base.html`](../../web/templates/admin/base.html) per AGENTS.md §5. |

---

## Open P3s — Notification System (Telegram)

Source entity: [`wiki/entities/notification-system.md`](wiki/entities/notification-system.md)

### TELEGRAM-P3-1 — Single oversized listing line silently drops the entire message body

| Field | Value |
|---|---|
| **Date added** | 2026-05-10 |
| **Source task** | TelegramChannel implementation (Round-1 Code Review) |
| **File:Line** | [`src/notifier.py:1323`](../../src/notifier.py:1323) |
| **Severity** | P3 |
| **Status** | open |
| **Why it matters** | The `_build_text_body` truncation loop drops a whole listing if its rendered line exceeds the 4000-char budget. With unusually long titles + addresses + URLs, listing #1 alone could exceed budget → `result` keeps only the header + `…and N more` footer (zero listings rendered). Realistic likelihood is low (typical line is <500 chars) but the failure is silent. |
| **Suggested fix** | If `i == 0` and the candidate line exceeds budget, individually truncate the line itself (e.g. trim the title to ~200 chars + ellipsis) so at least one listing renders. Add a log line `logger.warning("Telegram listing %d exceeded line budget — truncated", listing.id)`. |

### TELEGRAM-P3-2 — Lazy `from src.utils import sqft_to_sqm` is unnecessary

| Field | Value |
|---|---|
| **Date added** | 2026-05-10 |
| **Source task** | TelegramChannel implementation (Round-1 Code Review) |
| **File:Line** | [`src/notifier.py:1270`](../../src/notifier.py:1270) |
| **Severity** | P3 |
| **Status** | open |
| **Why it matters** | The lazy import comment claims "to avoid a top-level circular with src.utils" but `src/notifier.py:37` already does `from src.utils import load_config` at module top — there is no circular dependency. The lazy import adds a per-message import overhead and is misleading documentation. |
| **Suggested fix** | Move `from src.utils import sqft_to_sqm` to the module-level imports near line 37; delete the misleading comment. |

### TELEGRAM-P3-3 — `validate_token` exception handler labels everything as `network`

| Field | Value |
|---|---|
| **Date added** | 2026-05-10 |
| **Source task** | TelegramChannel implementation (Round-1 Code Review) |
| **File:Line** | [`src/notifier.py:1108`](../../src/notifier.py:1108) |
| **Severity** | P3 |
| **Status** | open |
| **Why it matters** | The broad `except Exception` mislabels programming errors (e.g. `AttributeError`, `JSONDecodeError`) as `error_category="network"`, hiding bugs in admin diagnostics. Mirrors the same anti-pattern at [`src/notifier.py:672`](../../src/notifier.py:672) (`WhatsAppChannel.validate_token`). |
| **Suggested fix** | Catch `(httpx.TimeoutException, httpx.NetworkError, OSError)` explicitly with `network`; let other exceptions fall through to a separate `except Exception` that returns `error_category="unexpected"`. Apply the same fix to `WhatsAppChannel.validate_token` for consistency. |

### TELEGRAM-P3-4 — Defence-in-depth: scrub bot token from any error messages built from URL-bearing exceptions

| Field | Value |
|---|---|
| **Date added** | 2026-05-10 |
| **Source task** | TelegramChannel implementation (Round-1 Code Review) |
| **File:Line** | [`src/notifier.py:1112`](../../src/notifier.py:1112), [`src/notifier.py:1240`](../../src/notifier.py:1240) |
| **Severity** | P3 |
| **Status** | open |
| **Why it matters** | Telegram's design forces the bot token into the URL path (`/bot<TOKEN>/sendMessage`) — unlike WhatsApp's bearer-header design. Some `httpx` exception types embed the request URL in `str(exc)` (e.g. `httpx.HTTPStatusError`). Today's catch-all paths (`f"... {exc}"`) most likely don't reach those, but a future refactor that adds `raise_for_status()` would silently exfiltrate the token into `notification_log.error_message` (visible to anyone with admin access) and into `logger.exception` traceback frames. |
| **Suggested fix** | Add a private `_scrub_token(message: str, token: str) -> str` helper that does `message.replace(token, "<redacted>")`; call it on every `error_message` value built from an exception in this channel. Same applies to any future log lines that include the URL. |

---

## Closed / Won't-Fix Archive

*(Empty — entries land here when set to `closed YYYY-MM-DD` or `wontfix YYYY-MM-DD`.)*

---

## Future Ideas (not P3 — not part of "fix all open P3s")

These are aspirational follow-ups deferred from the same review cycles. They're tracked here for discoverability but **excluded** from a generic "fix all open P3s" sweep — they need their own task brief because they're scoped as new features, not bug-class fixes.

- **Dedup operator visibility** — surface "dedup merges this run: N" in admin scrape stats. Sustained zero would have caught the 2026-05-08 IntegrityError silent-no-op in days, not weeks. *Source: dedup post-mortem.*
- **WhatsApp delivery webhook** — subscribe to Meta `messages` webhook to capture `delivered`/`read` status in `notification_log`. Catches silent recipient-side drops (a different failure class than token expiry). *Source: WhatsApp review.*
- **Dashboard URL doc fix** — update `README.md` from `localhost:8501` to `sunnynest:8000`. *Source: housekeeping.*
- **Investigate missing scraper logs** — `/tmp/sunnynest/scraper-stdout.log` and `scraper-stderr.log` are missing despite successful scraper runs. Directly defeats the new `logger.exception` observability gain in dedup. *Source: dedup post-mortem.*

---

## Schema Reference

When the Orchestrator appends a new row, use this template:

```markdown
### <FEATURE>-P3-<N> — <one-line title>

| Field | Value |
|---|---|
| **Date added** | YYYY-MM-DD |
| **Source task** | <task name> (Round-N Code Review) |
| **File:Line** | [`path/to/file.py:LINE`](../../path/to/file.py:LINE) |
| **Severity** | P3 |
| **Status** | open |
| **Why it matters** | <2-3 sentences> |
| **Suggested fix** | <copied verbatim from reviewer's report, lightly edited for this file's tone> |
```

Group rows by feature/entity using `## Open P3s — <Entity Name>` H2 headers (matching wiki entity-page titles). When closing a row, change `Status` to `closed YYYY-MM-DD` and move it under the `## Closed / Won't-Fix Archive` header (preserving the row body for audit).

### TELEGRAM-P3-5 — `TelegramChannel.get_recipient(cfg)` returns `"unknown"` instead of the env-var chat_id
**Discovered:** 2026-05-10 (live deployment verification)
**File:** [`src/notifier.py`](src/notifier.py:1170) `TelegramChannel.get_recipient`
**Symptom:** `TelegramChannel.get_recipient(cfg)` returns the literal string `"unknown"` instead of the actual `TELEGRAM_CHAT_ID` env var value. Demonstrated by `python -c "from src.notifier import TelegramChannel; from src.utils import load_config; print(TelegramChannel().get_recipient(load_config()))"` → `unknown` (when `TELEGRAM_CHAT_ID` IS set in `.env`).
**Why:** `get_recipient` reads from `config.get("telegram", {}).get("chat_id", "")` (always empty by design — `chat_id` is intentionally env-only) and falls back to `"unknown"`. It should read from `os.environ.get("TELEGRAM_CHAT_ID", "")` first, like the actual `send()` and `validate_token()` paths do.
**Impact:** `notification_log.recipient` rows for Telegram will have `recipient="unknown"` instead of the masked chat_id, making it harder to distinguish in the admin history. Also affects the recipient masking logic in [`web/routes/admin.py`](web/routes/admin.py:683) — though the admin page works around this by reading `os.environ` directly.
**Fix:** Update `TelegramChannel.get_recipient` to mirror the env-first pattern from `WhatsAppChannel.get_recipient`:
```python
def get_recipient(self, config: dict[str, Any]) -> str:
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if chat_id:
        return chat_id
    return config.get("telegram", {}).get("chat_id", "unknown")
```
**Severity:** P3 — log/observability cosmetic. Doesn't affect deliverability.

---

## Open P3s — Price Filter ($5K–$7.5K change, 2026-05-14)

Source entity: [`wiki/entities/config-yaml.md`](wiki/entities/config-yaml.md), [`wiki/entities/filter-bar.md`](wiki/entities/filter-bar.md)

### PRICE-P3-1 — Stale `6500` fallback default in `zillow_scraper.py`

| Field | Value |
|---|---|
| **Date added** | 2026-05-14 |
| **Source task** | Default price filter $5K–$6.5K → $5K–$7.5K (Code Review round 1) |
| **File:Line** | [`src/scrapers/zillow_scraper.py:94`](../../src/scrapers/zillow_scraper.py:94) |
| **Severity** | P3 |
| **Status** | open |
| **Why it matters** | `filters_cfg.get("max_price", 6500)` — the fallback is only reached if `config.yaml` is missing or has no `filters.max_price` key. In normal operation this is unreachable, but the fallback is now misleading and would silently apply the old cap if config is ever absent (e.g. during unit tests that don't load a real config). |
| **Suggested fix** | Change to `filters_cfg.get("max_price", 7500)` at [`src/scrapers/zillow_scraper.py:94`](../../src/scrapers/zillow_scraper.py:94). |

### PRICE-P3-2 — Stale `6500` fallback default in `realtor_scraper.py`

| Field | Value |
|---|---|
| **Date added** | 2026-05-14 |
| **Source task** | Default price filter $5K–$6.5K → $5K–$7.5K (Code Review round 1) |
| **File:Line** | [`src/scrapers/realtor_scraper.py:101`](../../src/scrapers/realtor_scraper.py:101) |
| **Severity** | P3 |
| **Status** | open |
| **Why it matters** | Identical issue to PRICE-P3-1 — `filters_cfg.get("max_price", 6500)` fallback is now inconsistent with the new default. |
| **Suggested fix** | Change to `filters_cfg.get("max_price", 7500)` at [`src/scrapers/realtor_scraper.py:101`](../../src/scrapers/realtor_scraper.py:101). |

### PRICE-P3-3 — Stale `6500` example in `listings.py` docstring

| Field | Value |
|---|---|
| **Date added** | 2026-05-14 |
| **Source task** | Default price filter $5K–$6.5K → $5K–$7.5K (Code Review round 1) |
| **File:Line** | [`web/routes/listings.py:25`](../../web/routes/listings.py:25) |
| **Severity** | P3 |
| **Status** | open |
| **Why it matters** | `description="Max price, e.g. '6500'"` is a documentation string only — no runtime impact — but it now contradicts the new default and will confuse future developers reading the API docs. |
| **Suggested fix** | Update to `description="Max price, e.g. '7500'"` at [`web/routes/listings.py:25`](../../web/routes/listings.py:25). |

### PRICE-P3-4 — Stale `5000-6500` example in `parse_filters()` docstring

| Field | Value |
|---|---|
| **Date added** | 2026-05-14 |
| **Source task** | Default price filter $5K–$6.5K → $5K–$7.5K (Code Review round 1) |
| **File:Line** | [`web/routes/__init__.py:28`](../../web/routes/__init__.py:28) |
| **Severity** | P3 |
| **Status** | open |
| **Why it matters** | `"5000-6500"` in the docstring example for `parse_filters()` is documentation only but now misleading. |
| **Suggested fix** | Update example to `"5000-7500"` at [`web/routes/__init__.py:28`](../../web/routes/__init__.py:28). |

---

## Open P3s — Silent-Notification Prevention Bundle (2026-06-03)

Source entity: [`wiki/entities/notification-system.md`](wiki/entities/notification-system.md) · concept: [`wiki/concepts/silent-failure-pattern.md`](wiki/concepts/silent-failure-pattern.md)

### SILENCE-P3-1 — Cache silence-detector query result

| Field | Value |
|---|---|
| **Date added** | 2026-06-03 |
| **Source task** | Silent-notification prevention bundle (Code mode round-1 self-flagged) |
| **File:Line** | [`web/routes/dashboard.py:40`](../../web/routes/dashboard.py:40) |
| **Severity** | P3 |
| **Status** | open |
| **Why it matters** | Silence-detector query runs on every dashboard page-load (2 DB queries: last-success + filtered-unnotified). On a 500 KB SQLite they're sub-ms, but cache the result in-memory for 60 s if dashboard ever sees >10 req/s. |
| **Suggested fix** | Add a 60s memoization cache around `_compute_notification_silence_state()`. |

### SILENCE-P3-2 — Hardcode threshold & timezone constants → move to config.yaml

| Field | Value |
|---|---|
| **Date added** | 2026-06-03 |
| **Source task** | Silent-notification prevention bundle (Code mode round-1; also flagged by Reviewer round-1 as SILENCE-P3-5 — dedupe) |
| **File:Line** | [`web/routes/dashboard.py:27`](../../web/routes/dashboard.py:27) `_SILENCE_THRESHOLD_HOURS = 48`; [`src/database.py:1478`](../../src/database.py:1478) `_IST` |
| **Severity** | P3 |
| **Status** | open |
| **Why it matters** | 48h threshold + `_IST = timezone(timedelta(hours=3))` are hardcoded in two places. If user moves time zones or wants a custom silence threshold, both need editing. |
| **Suggested fix** | Move to `config.yaml` under a new `notification_health:` section (`silence_threshold_hours: 48`, `timezone: "Asia/Jerusalem"`). |

### SILENCE-P3-3 — Edge-case: previously-notified-then-reset listings don't trigger banner

| Field | Value |
|---|---|
| **Date added** | 2026-06-03 |
| **Source task** | Silent-notification prevention bundle (Code mode round-1 self-flagged) |
| **File:Line** | [`web/routes/dashboard.py`](../../web/routes/dashboard.py) silence-detector query |
| **Severity** | P3 |
| **Status** | open |
| **Why it matters** | Silence detector counts unnotified listings whose `first_seen >= now - 48h`. A listing first seen 3 days ago that *became unnotified* (e.g., user reset `notified`) wouldn't trigger the banner. Edge case; current heuristic is "good enough" for typical scrape-then-notify flow. |
| **Suggested fix** | Either explicitly document this scoping decision in the function docstring, OR change query to `first_seen >= cutoff OR notified_reset_at >= cutoff` (would need a new column). |

### SILENCE-P3-4 — Unify silence detector with `get_last_channel_failure()`

| Field | Value |
|---|---|
| **Date added** | 2026-06-03 |
| **Source task** | Silent-notification prevention bundle (Code mode round-1 self-flagged) |
| **File:Line** | [`web/routes/dashboard.py`](../../web/routes/dashboard.py) + [`src/database.py`](../../src/database.py) `get_last_channel_failure()` |
| **Severity** | P3 |
| **Status** | open |
| **Why it matters** | Silence detector and existing admin `get_last_channel_failure()` are conceptually overlapping but live in different places. Future dashboards/admin pages would benefit from a shared module. |
| **Suggested fix** | Create `src/notifier_health.py` module exporting both functions; update callers. |

### SILENCE-P3-5 — Test runner pattern is hand-rolled (vs pytest)

| Field | Value |
|---|---|
| **Date added** | 2026-06-03 |
| **Source task** | Silent-notification prevention bundle (Reviewer round-1 as ANTISPAM-P3-2) |
| **File:Line** | [`scripts/test_anti_spam_guard.py`](../../scripts/test_anti_spam_guard.py), [`scripts/test_dedup_merge.py`](../../scripts/test_dedup_merge.py) |
| **Severity** | P3 |
| **Status** | open |
| **Why it matters** | New test file uses hand-rolled runner pattern. Same shape as `test_dedup_merge.py`. Consider adopting pytest — project-wide convention change. |
| **Suggested fix** | Adopt pytest across all scripts/test_* files; create `pytest.ini` or `pyproject.toml [tool.pytest]`. |

### SILENCE-P3-6 — `get_last_successful_notification_at()` could bound the scan window

| Field | Value |
|---|---|
| **Date added** | 2026-06-03 |
| **Source task** | Silent-notification prevention bundle (Reviewer round-1 as SILENCE-P3-7) |
| **File:Line** | [`src/database.py`](../../src/database.py) `get_last_successful_notification_at()` |
| **Severity** | P3 |
| **Status** | open |
| **Why it matters** | Function does `ORDER BY sent_at DESC LIMIT 1` with no upper bound. `sent_at` column has `index=True` so SQLite uses it, but for a long backlog explicit `.filter(sent_at >= cutoff)` (e.g., 30 days) makes index-scan stop earlier. |
| **Suggested fix** | Add optional `since: datetime` parameter; pass `now - 30 days` from silence detector caller. |

### LAUNCHD-P3-1 — Stale `[8, 20]` references in plans/READMEs

| Field | Value |
|---|---|
| **Date added** | 2026-06-03 |
| **Source task** | Silent-notification prevention bundle (Code mode round-1 self-flagged) |
| **File:Line** | [`plans/notification-scheduler.md`](../../plans/notification-scheduler.md), `README.md` |
| **Severity** | P3 |
| **Status** | open |
| **Why it matters** | Notify-am Hour shifted 8→10 on 2026-06-03; some plans/READMEs still reference 08:00. Documentation-only, but misleading. |
| **Suggested fix** | `grep -rn '08:00\|"08"\|hour.*8' plans/ README.md` and update each occurrence to 10:00. |

### ANTISPAM-P3-1 — Update lessonsLearned.md "Silent Failure Pattern" entry

| Field | Value |
|---|---|
| **Date added** | 2026-06-03 |
| **Source task** | Silent-notification prevention bundle (Code mode round-1 self-flagged) |
| **File:Line** | [`docs/memory/shared/lessonsLearned.md`](shared/lessonsLearned.md) "Silent Failure Pattern" section |
| **Severity** | P3 |
| **Status** | open |
| **Why it matters** | Old rationale "counting failures prevents unlimited failure spam from misconfigured channels" is now stale. The 2026-06-03 reversal needs to be documented in lessonsLearned to match the wiki's silent-failure-pattern.md. |
| **Suggested fix** | Update the "Silent Failure Pattern" entry in lessonsLearned.md to reflect Rule #3 inversion + cite the 2026-06-03 incident. |

### NOTIF-P3-1 — Hoist `_IST` constant to module level + consider `zoneinfo.ZoneInfo("Asia/Jerusalem")` [hardens-against-this-bug-class]

| Field | Value |
|---|---|
| **Date added** | 2026-06-03 |
| **Source task** | Silent-notification prevention bundle (Reviewer round-2) |
| **File:Line** | [`src/database.py:1495`](../../src/database.py:1495), [`src/database.py:1728`](../../src/database.py:1728), [`scripts/test_anti_spam_guard.py:50`](../../scripts/test_anti_spam_guard.py:50) |
| **Severity** | P3 |
| **Status** | open |
| **Why it matters** | `_IST = timezone(timedelta(hours=3))` is duplicated in 3 sites — drift risk if Asia/Jerusalem civil-time ever changes. More importantly: `timedelta(hours=3)` is a **fixed-offset approximation** that drifts by 1h relative to wall-clock during DST transitions — exact same bug class as the IST-vs-UTC-day boundary fix this bundle just landed. **Tagged `[hardens-against-this-bug-class]`** because it's the same family of tz mismatch. |
| **Suggested fix** | Hoist to module-level constant in `src/database.py`. Better: switch to `zoneinfo.ZoneInfo("Asia/Jerusalem")` for correct DST handling. Update the test to import the same constant. |

### NOTIF-P3-2 — `get_notification_stats()` uses `func.date(...) == today` with UTC-vs-IST mismatch [hardens-against-this-bug-class]

| Field | Value |
|---|---|
| **Date added** | 2026-06-03 |
| **Source task** | Silent-notification prevention bundle (Reviewer round-2) |
| **File:Line** | [`src/database.py:1735-1737`](../../src/database.py:1735) |
| **Severity** | P3 |
| **Status** | open |
| **Why it matters** | `today_count` in `get_notification_stats()` uses `func.date(sent_at) == today` with `today = datetime.now(_IST).date()`. This is the **exact same UTC-vs-IST mismatch** that `get_today_notification_count()` just fixed — but here it powers the admin "Notifications Today" tile. Near IST midnight the admin tile silently undercounts. **Tagged `[hardens-against-this-bug-class]`** because it's literally the bug we just fixed, in a sibling function. |
| **Suggested fix** | Reuse the `start_utc/end_utc` window pattern from [`get_today_notification_count()`](../../src/database.py:1463). Could extract a small private `_today_ist_utc_window() -> tuple[datetime, datetime]` helper to share between the two functions. |

---

## Open P3s — School Icons on Map (2026-06-03)

Source entity: [`wiki/entities/map-view.md`](wiki/entities/map-view.md) · Source task: "School icons on map" Option A implementation (Reviewer rounds 1 + 2)

### SCHOOL-P3-1 — No layer-control toggle for the schools layer

| Field | Value |
|---|---|
| **Date added** | 2026-06-03 |
| **Source task** | School icons on map (Reviewer round 1) |
| **File:Line** | [`web/static/js/map.js:136-150`](../../web/static/js/map.js:136), [`web/static/js/map.js:156`](../../web/static/js/map.js:156) |
| **Severity** | P3 |
| **Status** | open |
| **Why it matters** | Schools layer is added to the map but **not registered in the `L.control.layers` overlays object**. User said "ON by default, visible at all zooms" but didn't explicitly require non-toggleable. Other POI categories all have toggles; consistency with existing POI overlays matters and users may want to hide the 13 pins occasionally. |
| **Suggested fix** | Add `'🏫 Schools': schoolsLayer` to the `overlays` map at [`map.js:156`](../../web/static/js/map.js:156). One line. |

### SCHOOL-P3-2 — Add `district` field to each school entry now (forward-compat for Option B)

| Field | Value |
|---|---|
| **Date added** | 2026-06-03 |
| **Source task** | School icons on map (Code mode self-noted) |
| **File:Line** | [`web/static/js/map.js:43-57`](../../web/static/js/map.js:43) |
| **Severity** | P3 |
| **Status** | open |
| **Why it matters** | UX mockup Option B (district-tinted badges) is a likely future request. Adding `district: 'ssd' \| 'cusd' \| 'scusd'` to each entry now is free and turns the upgrade into a 5-line class-name swap instead of a re-keying job. |
| **Suggested fix** | Add a 4th key `district` to each of the 13 entries (8 ssd + 3 cusd + 2 scusd per the original brief). No UI change today; future Option-B implementation reads it. |

### SCHOOL-P3-3 — Move `SCHOOLS` array to `data/schools.json` and serve via small API endpoint

| Field | Value |
|---|---|
| **Date added** | 2026-06-03 |
| **Source task** | School icons on map (Reviewer round 1 + Code mode self-noted) |
| **File:Line** | [`web/static/js/map.js:21-57`](../../web/static/js/map.js:21) |
| **Severity** | P3 |
| **Status** | open |
| **Why it matters** | Low value while count is 13/static. Worth it if the list grows past ~25 or if non-engineers need to edit the list without touching JS. The file-level comment at [`map.js:28-30`](../../web/static/js/map.js:28) already anticipates this migration. |
| **Suggested fix** | Extract to `data/schools.json`, add `GET /api/schools` endpoint in [`web/routes/api.py`](../../web/routes/api.py), have [`map.js`](../../web/static/js/map.js) fetch it on init. Document migration path in [`docs/memory/wiki/entities/map-view.md`](../wiki/entities/map-view.md). |

### SCHOOL-P3-4 — Add private/charter elementary schools

| Field | Value |
|---|---|
| **Date added** | 2026-06-03 |
| **Source task** | School icons on map (Code mode self-noted) |
| **File:Line** | [`web/static/js/map.js:43-57`](../../web/static/js/map.js:43) |
| **Severity** | P3 |
| **Status** | open |
| **Why it matters** | Current 13 are public-only. Renters comparing neighborhoods often care about private (Stratford, Challenger) or charter options too. Best paired with SCHOOL-P3-2 (`district` field becomes `'ssd' \| 'cusd' \| 'scusd' \| 'private' \| 'charter'`) and SCHOOL-P3-3 (extract to JSON). |
| **Suggested fix** | Compile list with user input on which private/charter schools to include; geocode via [`scripts/geocode_schools.py`](../../scripts/geocode_schools.py); add to array (or JSON file if SCHOOL-P3-3 lands first). |

### SCHOOL-P3-5 — `interactive: true` is the Leaflet default — drop or comment

| Field | Value |
|---|---|
| **Date added** | 2026-06-03 |
| **Source task** | School icons on map (Reviewer round 1) |
| **File:Line** | [`web/static/js/map.js:146`](../../web/static/js/map.js:146) |
| **Severity** | P3 |
| **Status** | open |
| **Why it matters** | Pure code-noise nit — `interactive: true` does nothing because it's the Leaflet `L.marker` default. Either drop it or add a one-line comment explaining why it's spelled out. |
| **Suggested fix** | Either delete the option from the marker constructor, or add `// explicit: required for bindTooltip hover to fire` if there's a defensive reason. |

### SCHOOL-P3-6 — DRY-up duplicated POI tooltip options

| Field | Value |
|---|---|
| **Date added** | 2026-06-03 |
| **Source task** | School icons on map (Reviewer round 1) |
| **File:Line** | [`web/static/js/map.js:147`](../../web/static/js/map.js:147), [`web/static/js/map.js:357`](../../web/static/js/map.js:357) |
| **Severity** | P3 |
| **Status** | open |
| **Why it matters** | `{ direction: 'top', offset: [0, -14] }` is duplicated between the schools layer and [`createPOIMarker()`](../../web/static/js/map.js:345). If the offset ever needs tuning, two sites must change in lockstep. |
| **Suggested fix** | Extract a `POI_TOOLTIP_OPTS = { direction: 'top', offset: [0, -14] }` constant near [`POI_CATEGORIES`](../../web/static/js/map.js) and reference it from both call sites. |

### SCHOOL-P3-7 — Manual school entries lack retry-trigger annotation

| Field | Value |
|---|---|
| **Date added** | 2026-06-03 |
| **Source task** | School icons on map (Reviewer round 2) |
| **File:Line** | [`web/static/js/map.js:45,50,56,57`](../../web/static/js/map.js:45) |
| **Severity** | P3 |
| **Status** | open |
| **Why it matters** | The 4 `// manual` entries (Cumberland, Vargas, Braly, Ponderosa) document *why* they're manual but give no signal for when to retry. If Nominatim coverage improves, nobody will know to re-run [`scripts/geocode_schools.py`](../../scripts/geocode_schools.py). |
| **Suggested fix** | Append to the JSDoc above `SCHOOLS`: *"Re-run scripts/geocode_schools.py annually; if Nominatim now returns a match within ~200m of any `// manual` value, drop the override."* Style nit only. |

### SCHOOL-P3-8 — Formalize dedicated `--color-poi-school-favorite` token

| Field | Value |
|---|---|
| **Date added** | 2026-06-03 |
| **Source task** | Favorite schools green styling (Code mode self-noted) |
| **File:Line** | [`web/static/css/style.css:1432`](../../web/static/css/style.css:1432), [`docs/design/design-bible.md:206-211`](../../docs/design/design-bible.md:206) |
| **Severity** | P3 |
| **Status** | open |
| **Why it matters** | `.school-poi-icon--favorite` reuses `--color-poi-park` (`#16a34a`) as a placeholder green. The 🏫 icon carries the semantic so there's no immediate confusion with parks, but if the favorite-schools feature graduates from "hardcoded flag" to a real product feature, it deserves its own token (e.g. `--color-poi-school-favorite: #16a34a` or a brighter `#22c55e`) and a row in the Design Bible POI table at line 206. |
| **Suggested fix** | UX Designer task: add `--color-poi-school-favorite` row to the Design Bible POI category table, decide whether to keep `#16a34a` or switch to a distinct shade, then update [`style.css:1432`](../../web/static/css/style.css:1432) to consume the token. |

### SCHOOL-P3-9 — Move favorite schools to user-preferences / config file

| Field | Value |
|---|---|
| **Date added** | 2026-06-03 |
| **Source task** | Favorite schools green styling |
| **File:Line** | [`web/static/js/map.js:41-58`](../../web/static/js/map.js:41) |
| **Severity** | P3 |
| **Status** | open |
| **Why it matters** | The 6 favorites are hardcoded `isFavorite: true` in [`SCHOOLS`](../../web/static/js/map.js:41) (owner's personal list). Fine as a single-user product; not OK once SunnyNest serves multiple renters. Pair this with SCHOOL-P3-3 (extract to `data/schools.json`) so favorites become per-user state in a future user-prefs table. |
| **Suggested fix** | Add `favorite_schools` to a user-prefs config (yaml or DB). When SCHOOL-P3-3 lands, fetch `/api/schools` + `/api/me/preferences` and merge `isFavorite` at runtime. **Same constant lives in [`web/dependencies.py:FAVORITE_SCHOOLS`](../../web/dependencies.py:75) — both move together.** |

### SCHOOL-P3-10 — Investigate root cause of `_do_geocode` Nominatim unavailability on 2026-06-03

| Field | Value |
|---|---|
| **Date added** | 2026-06-03 |
| **Source task** | School icons — 15-schools + favorites (Reviewer R3) |
| **File:Line** | [`src/geocoder.py:22`](../../src/geocoder.py:22), [`src/geocoder.py:55`](../../src/geocoder.py:55), [`src/geocoder.py:71-82`](../../src/geocoder.py:71) |
| **Severity** | P3 |
| **Status** | open |
| **Why it matters** | While re-running [`scripts/geocode_schools.py`](../../scripts/geocode_schools.py) for the 2 new schools, `_do_geocode()` returned `"Geocoder service unavailable"` for all addresses; direct `curl` to Nominatim with a proper User-Agent worked fine. Worked around via OSM way lookups for Montclaire + Laurelwood (the existing 13 use cached coords). Root cause uncertain: (a) circuit breaker tripped from prior production run + cooldown not elapsed, (b) `Nominatim(user_agent="sunnyvale-rental-finder")` is generic — Nominatim TOU prefers contact info. Distinct from the OPEN P2 about silent city-centroid fallback in `geocode_address()`. |
| **Suggested fix** | Debug mode investigation. If (b), bumping User-Agent to include a contact email is 1 line. If (a), add a `geocoder_status()` admin endpoint so the breaker state is visible. |

### SCHOOL-P3-11 — ARIA double-announce on school icons (inner div aria-label + Leaflet tooltip)

| Field | Value |
|---|---|
| **Date added** | 2026-06-03 |
| **Source task** | School icons — 15-schools + favorites (Reviewer R3) |
| **File:Line** | [`web/static/js/map.js:167`](../../web/static/js/map.js:167) |
| **Severity** | P3 |
| **Status** | open |
| **Why it matters** | Inner `<div class="school-poi-icon...">🏫</div>` carries an `aria-label`, but the wrapper marker also has a bound Leaflet tooltip. Screen readers may double-announce ("⭐ Cherry Chase Elementary" twice). Low severity — most AT will dedupe. |
| **Suggested fix** | Either drop the `aria-label` from the inner div (rely on Leaflet tooltip), or set `aria-hidden="true"` on the emoji span and `role="img" aria-label="..."` on the wrapper. |

### SCHOOL-P3-12 — Unit test pinning FAVORITE_SCHOOLS == map.js SCHOOLS.filter(isFavorite)

| Field | Value |
|---|---|
| **Date added** | 2026-06-03 |
| **Source task** | Favorite-school highlight (Option C) — Code mode self-noted |
| **File:Line** | [`web/dependencies.py:75-92`](../../web/dependencies.py:75), [`web/static/js/map.js:50-69`](../../web/static/js/map.js:50) |
| **Severity** | P3 |
| **Status** | open |
| **Why it matters** | The Python `FAVORITE_SCHOOLS` frozenset and the JS `SCHOOLS` array `isFavorite: true` entries must agree byte-for-byte. Today enforced only by a comment block at [`dependencies.py:81-92`](../../web/dependencies.py:81). Reviewer verified the current match programmatically, but drift could land silently between cycles. |
| **Suggested fix** | Add `tests/test_school_favorites_consistency.py`: shell-out `grep -oE` over `map.js` to extract names where `isFavorite: true`, assert set equality vs `FAVORITE_SCHOOLS`. ~15 LOC. Best fixed alongside SCHOOL-P3-3 (extract to shared JSON would obsolete this test). |

### SCHOOL-P3-13 — Move school-name normalization to ingest-time (school_districts.py) instead of read-time

| Field | Value |
|---|---|
| **Date added** | 2026-06-03 |
| **Source task** | Favorite-school highlight (Option C) — Code mode self-noted; Reviewer triage kept at P3 |
| **File:Line** | [`web/dependencies.py:103-113`](../../web/dependencies.py:103) (read-time), [`src/school_districts.py:153`](../../src/school_districts.py:153) (proposed ingest-time site) |
| **Severity** | P3 |
| **Status** | open |
| **Why it matters** | DB stores `"Cherry Chase Elementary School"` (with " School" suffix from GeoJSON), but the canonical UI form matching `map.js` SCHOOLS is `"Cherry Chase Elementary"`. Today [`_normalize_school_name()`](../../web/dependencies.py:103) strips the suffix at read-time — works, defended by Reviewer as the right v1 call (no migration risk, preserves DB fidelity, 5 LOC). Ingest-time would be cleaner long-term: normalize once at write, no per-render call. Requires a one-off backfill of existing rows. |
| **Suggested fix** | Add normalization to [`src/school_districts.py:153`](../../src/school_districts.py:153) before writing `school_elementary` / `school_middle` / `school_high`. Write a one-shot backfill script. Then drop `_normalize_school_name()` from `dependencies.py` and revert `is_favorite_school()` to direct frozenset membership. Best timed when favorite-school feature expands beyond elementary. |

### SCHOOL-P3-14 — `.is-fav-school` card-root class is emitted but currently unused in CSS

| Field | Value |
|---|---|
| **Date added** | 2026-06-03 |
| **Source task** | Favorite-school highlight (Option C) — Code mode self-noted |
| **File:Line** | [`web/templates/partials/listing-card.html:5`](../../web/templates/partials/listing-card.html:5), [`web/static/css/style.css`](../../web/static/css/style.css) |
| **Severity** | P3 |
| **Status** | open |
| **Why it matters** | Code mode added `is-fav-school` to the card root as a forward-compat CSS hook (Option C currently styles only the chip + map pill). Dead-but-cheap markup. UX may later add a subtle card-level treatment (e.g., 4px green left-border per Option-A mockup) — would be a 1-selector CSS addition. Alternatively remove for strict YAGNI. |
| **Suggested fix** | Either (a) add a subtle card-level CSS rule (e.g., `.listing-card.is-fav-school { border-left: 4px solid #16a34a; }`) per Option A's mockup, OR (b) remove the unused class for YAGNI. UX call. |

### SCHOOL-P3-15 — `_normalize_school_name()` should `.strip()` for defense-in-depth

| Field | Value |
|---|---|
| **Date added** | 2026-06-03 |
| **Source task** | Favorite-school highlight (Option C) — Reviewer found |
| **File:Line** | [`web/dependencies.py:103-113`](../../web/dependencies.py:103) |
| **Severity** | P3 |
| **Status** | open |
| **Why it matters** | `endswith(" Elementary School")` is exact — if a future scraper or manual DB edit leaves trailing whitespace (`"Cherry Chase Elementary School "`), the match silently fails and the listing won't be highlighted. Unlikely with current controlled GeoJSON ingest, but cheap to defend. |
| **Suggested fix** | Add `name = name.strip()` as the first line of [`_normalize_school_name()`](../../web/dependencies.py:103). 1 line. |

### SCHOOL-P3-17 — Re-enable doc comment should also mention removing CSS DISABLED markers

| Field | Value |
|---|---|
| **Date added** | 2026-06-04 |
| **Source task** | `SCHOOLS_UI_ENABLED` flag disable (Reviewer R1 nit) |
| **File:Line** | [`web/dependencies.py:105-106`](../../web/dependencies.py:105) |
| **Severity** | P3 |
| **Status** | open |
| **Why it matters** | The re-enable doc comment correctly tells future-maintainer to flip the flag + bump CSS cache version, but omits "remove the `/* DISABLED 2026-06-04 */` comment blocks in [`web/static/css/style.css`](../../web/static/css/style.css) above `.school-pill-fav` and `.price-pill-marker.is-fav-school`". Easy to grep for but completeness matters for the flip-back. |
| **Suggested fix** | Append to the doc comment: `"and remove '/* DISABLED 2026-06-04 ... */' comment blocks in web/static/css/style.css above .school-pill-fav and .price-pill-marker.is-fav-school"`. Will be addressed automatically when [`plans/school-boundaries-nces.md`](../../../plans/school-boundaries-nces.md) Definition-of-Done step 6 runs. |

> **NOTE on re-enable tracking:** SCHOOL-P3-16 (originally proposed by Code mode as "re-enable the flag when SABS data lands") was **NOT added as a P3** on Reviewer R1's recommendation — sweeping it standalone would re-introduce the bug we just suppressed. Instead, the re-enable steps live as the Definition-of-Done section of [`plans/school-boundaries-nces.md`](../../../plans/school-boundaries-nces.md). Don't add a SCHOOL-P3-16 here.

---

## Open P3s — Featured POI (2026-06-04)

Source entity: [`wiki/entities/map-view.md`](wiki/entities/map-view.md) · Source task: "Ortega Park featured POI" Option A implementation

### POI-P3-1 — Add `featured: Optional[bool]` to `POICreate` Pydantic schema

| Field | Value |
|---|---|
| **Date added** | 2026-06-04 |
| **Source task** | Featured POI Option A (Code mode self-noted, Reviewer agreed) |
| **File:Line** | [`web/routes/api.py:50-55`](../../web/routes/api.py:50), [`src/poi.py:69-110`](../../src/poi.py:69) |
| **Severity** | P3 |
| **Status** | open |
| **Why it matters** | Current v1 contract: `featured` is set only by direct JSON edit. POICreate Pydantic accepts `category, name, address, lat, lng` only. To enable POI-P3-2 (toggle UI), the API must accept the flag. **Caveat:** Reviewer noted that if Pydantic v2 has `extra="forbid"` (the default), the API will return 422 for any request containing `featured` — so this is forward-prep for the toggle UI but also closes a latent silent-drop risk (see POI-P3-4). |
| **Suggested fix** | (a) Add `featured: Optional[bool] = False` to `POICreate`; (b) thread it through [`create_poi`](../../web/routes/api.py:93) into [`add_poi(... featured=...)`](../../src/poi.py:69) signature; (c) include `featured` in the dict returned by `add_poi`. ~5-line change. |

### POI-P3-2 — "★ Feature this POI" toggle button in POI list partial

| Field | Value |
|---|---|
| **Date added** | 2026-06-04 |
| **Source task** | Featured POI Option A (Code mode self-noted) |
| **File:Line** | [`web/templates/partials/poi-list.html`](../../web/templates/partials/poi-list.html), [`web/routes/api.py`](../../web/routes/api.py) (new `PATCH /api/poi/{id}/featured` endpoint), [`src/poi.py`](../../src/poi.py) (new `update_poi_featured(id, featured)` helper) |
| **Severity** | P3 |
| **Status** | open |
| **Why it matters** | Today the `featured` flag is set only by hand-editing `data/interest-points.json`. A "★ Feature" star toggle button on each POI list entry would be more user-friendly + visually consistent with the favorite-school ★ pattern shipped 2026-06-03. **Depends on POI-P3-1** (API schema needs to accept `featured`). |
| **Suggested fix** | (a) Add a `<button>` to the poi-list partial that fires `hx-patch="/api/poi/{{poi.id}}/featured"` with `featured=!poi.featured`; (b) new `PATCH` endpoint in api.py; (c) helper in poi.py that reads, modifies one field, writes. Visual: ★ for featured, ☆ for not. |

### POI-P3-3 — Enrich featured-POI tooltip with distance-to-nearest-listing

| Field | Value |
|---|---|
| **Date added** | 2026-06-04 |
| **Source task** | Featured POI Option A (UX mockup proposed but explicitly deferred per user) |
| **File:Line** | [`web/static/js/map.js`](../../web/static/js/map.js:419) |
| **Severity** | P3 |
| **Status** | open |
| **Why it matters** | UX mockup showed `"Ortega Park · Park · 0.3 mi from 3 listings"` as the richer hover treatment. Currently tooltip is just `"Ortega Park · Parks"`. User said "may give priority to listings close to it" — this P3 is the natural first step of that ranking work. **Belongs with the deferred ranking-by-distance plan**, not standalone. |
| **Suggested fix** | Add a small haversine helper. On marker hover, compute distance to all currently-visible (filtered) listing markers; show count within 0.5 mi + min distance. Pair with the future ranking-by-distance plan/task. |

### POI-P3-4 — Verify/test `add_poi()` Pydantic passthrough of unknown kwargs

| Field | Value |
|---|---|
| **Date added** | 2026-06-04 |
| **Source task** | Featured POI Option A (Code mode flagged, Reviewer confirmed) |
| **File:Line** | [`src/poi.py:69-110`](../../src/poi.py:69) |
| **Severity** | P3 |
| **Status** | open |
| **Why it matters** | Currently safe because `_write_store` pass-throughs all dict keys (verified by Reviewer). BUT [`add_poi`](../../src/poi.py:69) has a fixed positional signature — if POI-P3-1 ever adds a kwarg path, an unknown kwarg would silently disappear. Worth a test that pins the contract. Footgun for whoever lands POI-P3-1. |
| **Suggested fix** | Add `tests/test_poi_passthrough.py` that writes a JSON with a future-unknown field (`{"category": "park", "name": "X", ..., "future_field": "y"}`), reads it back via `list_pois()`, asserts the unknown field survives a `_write_store` round-trip. ~10 LOC. |

### POI-P3-5 — Featured POI label pill can visually overlap nearby price pills at high zoom

| Field | Value |
|---|---|
| **Date added** | 2026-06-04 |
| **Source task** | Featured POI Option A (Reviewer found) |
| **File:Line** | [`web/static/css/style.css:1480-1499`](../../web/static/css/style.css:1480) (`.poi-featured-label` positioning) |
| **Severity** | P3 |
| **Status** | open |
| **Why it matters** | The always-shown label pill is absolutely positioned 4 px below the 36 px pin with `pointer-events: none`, so it won't block clicks (z-order keeps the price pill clickable: default `0` > featured `-50`). But at zoom ≥15 with a listing pinned within ~30 m of Ortega Park, the white label could visually overlap a price pill. Cosmetic only. |
| **Suggested fix** | Either (a) hide labels at zoom < 14, (b) implement simple label collision detection, OR (c) accept the overlap — featured POIs are rare and the user can visually disambiguate via hover. Recommend (c) as no-op, document in CSS comment. |
