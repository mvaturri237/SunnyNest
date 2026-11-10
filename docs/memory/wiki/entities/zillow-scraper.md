# Zillow Scraper

> Primary data source for rental listings via RapidAPI "ZLLW Working API", fetching Sunnyvale house rentals with a 500 req/month free tier.

**Status:** Active  
**Owner files:** `src/scrapers/zillow_scraper.py`, `src/scrapers/base.py`  
**Config:** `config.yaml` → `zillow_api`  
**Added:** 2026-03-27
**Last updated:** 2026-06-04

## Overview

The Zillow scraper is the primary data source for SunnyNest. It fetches rental listings from the "ZLLW Working API" by ONEAPI on RapidAPI, searching by ZIP code across 4 Sunnyvale ZIP codes (94085, 94086, 94087, 94089). It extends `BaseScraper(ABC)` and follows the [Adapter Pattern](../concepts/adapter-pattern.md).

The scraper queries the `/search/byaddress` endpoint, normalizes the response into the standard listing format, and passes results to the [Orchestrator](orchestrator.md) for the full pipeline (geocode → enrich → upsert → dedup).

## Architecture

- Extends `BaseScraper` ABC with `async scrape() -> list[dict]` and `normalize(raw: dict) -> dict | None` (returning `None` signals "skip this item" — see "Response-side status validation" below)
- Uses `httpx` async HTTP client with custom SSL context from `BaseScraper._build_ssl_context()` — loads PANW Enterprise Root CA for TLS decryption proxy, clears `VERIFY_X509_STRICT` for OpenSSL 3.6+ (see [Security Patterns](../concepts/security-patterns.md))
- API key resolution: `RAPIDAPI_KEY` env var → `config.yaml` fallback (env var preferred per [Security Patterns](../concepts/security-patterns.md))
- Budget guard: checks `get_api_call_count("zillow")` against 500/month limit before making calls
- Pagination with configurable random delay (3-8s) between pages to avoid rate limiting
- `homeType` restricted to `"Houses"` only — no apartments, condos, or townhomes
- `_map_property_type()` defaults unknown/empty types to `"house"` to prevent silent data loss

## Current State

- **Working:** Fully operational, fetching daily at 06:00 via [launchd scheduler](scheduler-launchd.md)
- **Free tier:** 500 requests/month — with daily scraping at max_pages=3, uses ~90 calls/month
- **Known issue:** If `RAPIDAPI_KEY` env var is not set, scraper silently returns `[]` with a warning log (see [Silent Failure Pattern](../concepts/silent-failure-pattern.md))
- **API call logging:** All calls logged to `api_call_log` table via `log_api_call("zillow", endpoint, status_code)`

## Response-side status validation (Bug A — 2026-06-04)

> **Lesson:** Sending `listingStatus=For_Rent` as a *request parameter* does NOT guarantee the provider's response only contains rentals. The RapidAPI provider's index occasionally returns off-market for-sale properties (with stale rental prices) under the `For_Rent` filter. **Always re-validate status on the response.**

[`normalize()`](../../../src/scrapers/zillow_scraper.py:268) now rejects items at the top of the function when **either** of these conditions fails (case-insensitive):

1. `property.listing.listingStatus == "forRent"`
2. `property.listing.marketingStatus == "active"`

When either condition fails (or either field is missing/non-string), `normalize()` returns `None`. The [`Orchestrator`](orchestrator.md) treats `None` as a skip signal (per-source `normalize_filtered` counter logged at debug level when > 0).

**⚠️ Field paths that DON'T work (verified):**
- `property.homeStatus` — key IS present but value is **always `null`** in our experience. Do NOT rely on it.
- Top-level `listingStatus` / `status` — not exposed; the canonical fields are nested under `property.listing`.

**Defense-in-depth:** This guard catches the *easy* case (provider correctly labels a row as `forSale`). If the provider lies and returns `forRent` for a stale withdrawn rental, the new `consecutive_misses` hysteresis counter in [`Database Schema`](database-schema.md) / [`Orchestrator`](orchestrator.md) is the second layer that catches it after ~3 daily scrapes.

Tests: [`scripts/test_zillow_status_filter.py`](../../../scripts/test_zillow_status_filter.py) (7 cases incl. missing-subdict / case-insensitive / `forSale` / `inactive`).

## Fields NOT exposed by `/search/byaddress`

> Verified 2026-06-03 via a one-shot debug probe (3 sample listings, see [`docs/memory/wiki/archive/zillow-avail-probe-findings-2026-06-03.md`](../archive/zillow-avail-probe-findings-2026-06-03.md)). **Before opening a feature that depends on any of the fields below, re-probe with a fresh sample — RapidAPI providers occasionally extend their response schema.**

| Wanted field | Status in `/search/byaddress` | Notes |
|--------------|------------------------------|-------|
| `availabilityDate` / `dateAvailable` / `whatIWant.availabilityDate` | ❌ Not returned | The Zillow web UI shows "Available [date]" but the ZLLW Working API mirror does not expose it. Only `listingDateTimeOnZillow` (listing-creation Unix-ms) matches the `avail\|date\|move` pattern — that's the **posted date**, semantically equal to `daysOnZillow`, NOT the move-in date. |
| `unitsGroup[n].availabilityDate` (for `propertyGroup`) | ❓ Untested | Sample probe (2026-06-03) contained zero `resultType=propertyGroup` items because [`zillow_scraper.py:169`](../../../src/scrapers/zillow_scraper.py:169) filters `homeType=Houses`. No evidence either way for apartment-complex listings. |
| `whatIWant.*` (any rental-specific subdict) | ❌ Key absent | The probe explicitly checked `prop.get("whatIWant", {}).keys()` — `whatIWant` did not exist on any sample. |

**Top-level keys actually returned** (stable across the 3-sample probe):
`address, bathrooms, bedrooms, bestGuessTimeZone, country, currency, daysOnZillow, estimates, hasFloorPlan, hdpView, isFeatured, isPreforeclosureAuction, isShowcaseListing, isUnmappable, listCardRecommendation, listing, listingDateTimeOnZillow, livingArea, location, media, personalizedResult, price, propertyDisplayRules, propertyHasLasViolation, propertyType, region, rental, ssid, taxAssessment, zillowOwnedProperty, zpid`.

**Paths to availability data if a future feature is reopened:**
1. **Per-listing detail endpoint** (e.g. `/property?zpid=…`) — would add 1 call per result × pagination = ~+25 calls/scrape ≈ ~750/mo, **blows the free tier**. Requires paid RapidAPI plan or scrape-frequency reduction.
2. **Switch RapidAPI provider** — other ZLLW wrappers may expose availability in their search response. Evaluation = new Architect task.
3. **Drop Zillow availability and source it elsewhere** — but Realtor and Craigslist are also ❌ / ⚠️ per [`plans/available-date-feature.md`](../../../../plans/available-date-feature.md) (KILLED 2026-06-03).

## Configuration

| Key | Default | Description |
|-----|---------|-------------|
| `zillow_api.rapidapi_key` | `""` | Set via `RAPIDAPI_KEY` env var |
| `zillow_api.rapidapi_host` | `zllw-working-api.p.rapidapi.com` | RapidAPI host header |
| `scraper.request_delay_min` | `3` | Min seconds between paginated requests |
| `scraper.request_delay_max` | `8` | Max seconds between paginated requests |
| `scraper.max_pages` | `3` | Max pages to fetch per search |

## Key Files

| File | Purpose |
|------|---------|
| `src/scrapers/zillow_scraper.py` | Main scraper implementation |
| `src/scrapers/base.py` | `BaseScraper` ABC definition + `_build_ssl_context()` |
| `data/certs/panw-root-ca.pem` | PANW Enterprise Root CA for TLS proxy |
| `config.yaml` → `zillow_api` | API configuration |
| `.env` → `RAPIDAPI_KEY` | API key (secret) |

## History

- [2026-06-04] **Response-side status validation added (Bug A) + lifecycle-hysteresis counter coordinated with [`Orchestrator`](orchestrator.md) (Bug B).** User reported 1525 Bittern Dr (zpid 19615280) appearing as a $6,200/mo active rental — but the property is "Off market" / for sale at $2.98M on Zillow.com. Debug-mode RCA found two layered bugs: (A) [`normalize()`](../../../src/scrapers/zillow_scraper.py:268) trusted the upstream `For_Rent` filter without re-checking response-side status; (B) [`mark_inactive()`](../../../src/database.py:824) deactivated on a single missing scrape, but the provider's index is flaky enough that one daily "hit" keeps stale rows active forever. Code mode fixed both (TDD, 15/15 tests green, signature changed to `dict | None`, `consecutive_misses` column + N=3 threshold). Reviewer ✅ APPROVED 0 P1/P2, 4 P3s → backlog. RapidAPI budget: 8/500 (Debug used 3 probes). User runs [`scripts/deactivate_stale_zillow.py --apply`](../../../scripts/deactivate_stale_zillow.py) once to clear listing id=327 immediately. See [log entry](../log.md#zillow-stale-for-sale-rental-bug-bug-a--bug-b--approved-4-p3s--backlog).
- [2026-06-03] **Field-availability probe (NEGATIVE RESULT)** — one-shot debug log on [`normalize()`](../../../src/scrapers/zillow_scraper.py:268) confirmed `/search/byaddress` returns **no** availability/move-in-date field; only `listingDateTimeOnZillow` matches the search pattern and that's a posted-date duplicate. Probe code added → 1 scrape call run (4/500 monthly budget) → log inspected → probe code fully reverted (`git diff` empty). Findings archived at [`docs/memory/wiki/archive/zillow-avail-probe-findings-2026-06-03.md`](../archive/zillow-avail-probe-findings-2026-06-03.md). Killed the [Available-Date feature](../../../../plans/available-date-feature.md) Phase 1 plan. New "Fields NOT exposed" section above documents the dead end so this investigation isn't repeated.
- [2026-04-14] `max_pages` increased from 1 → 3 in config.yaml to capture more listings (user reported 6 vs 18 on Zillow)
- [2026-04-06] SSL fix — custom SSL context with PANW root CA + relaxed VERIFY_X509_STRICT for OpenSSL 3.6 compatibility. APPROVED (0 P1, 0 P2, 3 P3)
- [2026-04-06] Scheduler migrated from APScheduler to launchd — scraper now runs via standalone `scripts/run-scraper.py`
- [2026-03-31] API counter fix — `RAPIDAPI_KEY` env var was lost after frontend migration restart; added `python-dotenv` support
- [2026-03-28] Scrape interval changed from 24h to 6h (4 scrapes/day); `homeType` restricted to Houses only
- [2026-03-28] Default property type changed from "apartment" to "house" to prevent silent data loss
- [2026-03-27] API key moved from `config.yaml` to `RAPIDAPI_KEY` env var (security fix)
- [2026-03-27] TLS verification restored (was disabled with `verify=False`)
- [2026-03-27] Initial implementation

## Related

- [Craigslist Scraper](craigslist-scraper.md) — secondary data source
- [Realtor Scraper](realtor-scraper.md) — third data source, also uses RapidAPI
- [Orchestrator](orchestrator.md) — coordinates the scrape→normalize→geocode→enrich→upsert→dedup pipeline
- [Config (YAML)](config-yaml.md) — central configuration
- [Adapter Pattern](../concepts/adapter-pattern.md) — BaseScraper ABC pattern
- [Silent Failure Pattern](../concepts/silent-failure-pattern.md) — credential-dependent features fail silently
- [Security Patterns](../concepts/security-patterns.md) — env vars for secrets, TLS verification
