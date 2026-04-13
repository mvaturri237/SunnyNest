# Zillow Scraper

> Primary data source for rental listings via RapidAPI "ZLLW Working API", fetching Sunnyvale house rentals with a 500 req/month free tier.

**Status:** Active  
**Owner files:** `src/scrapers/zillow_scraper.py`, `src/scrapers/base.py`  
**Config:** `config.yaml` → `zillow_api`  
**Added:** 2026-03-27  
**Last updated:** 2026-04-06

## Overview

The Zillow scraper is the primary data source for SunnyNest. It fetches rental listings from the "ZLLW Working API" by ONEAPI on RapidAPI, searching by ZIP code across 4 Sunnyvale ZIP codes (94085, 94086, 94087, 94089). It extends `BaseScraper(ABC)` and follows the [Adapter Pattern](../concepts/adapter-pattern.md).

The scraper queries the `/search/byaddress` endpoint, normalizes the response into the standard listing format, and passes results to the [Orchestrator](orchestrator.md) for the full pipeline (geocode → enrich → upsert → dedup).

## Architecture

- Extends `BaseScraper` ABC with `async scrape() -> list[dict]` and `normalize(raw: dict) -> dict`
- Uses `httpx` async HTTP client with custom SSL context from `BaseScraper._build_ssl_context()` — loads PANW Enterprise Root CA for TLS decryption proxy, clears `VERIFY_X509_STRICT` for OpenSSL 3.6+ (see [Security Patterns](../concepts/security-patterns.md))
- API key resolution: `RAPIDAPI_KEY` env var → `config.yaml` fallback (env var preferred per [Security Patterns](../concepts/security-patterns.md))
- Budget guard: checks `get_api_call_count("zillow")` against 500/month limit before making calls
- Pagination with configurable random delay (3-8s) between pages to avoid rate limiting
- `homeType` restricted to `"Houses"` only — no apartments, condos, or townhomes
- `_map_property_type()` defaults unknown/empty types to `"house"` to prevent silent data loss

## Current State

- **Working:** Fully operational, fetching daily at 06:00 via [launchd scheduler](scheduler-launchd.md)
- **Free tier:** 500 requests/month — with daily scraping across 4 ZIP codes, uses ~120 calls/month
- **Known issue:** If `RAPIDAPI_KEY` env var is not set, scraper silently returns `[]` with a warning log (see [Silent Failure Pattern](../concepts/silent-failure-pattern.md))
- **API call logging:** All calls logged to `api_call_log` table via `log_api_call("zillow", endpoint, status_code)`

## Configuration

| Key | Default | Description |
|-----|---------|-------------|
| `zillow_api.rapidapi_key` | `""` | Set via `RAPIDAPI_KEY` env var |
| `zillow_api.rapidapi_host` | `zllw-working-api.p.rapidapi.com` | RapidAPI host header |
| `scraper.request_delay_min` | `3` | Min seconds between paginated requests |
| `scraper.request_delay_max` | `8` | Max seconds between paginated requests |
| `scraper.max_pages` | `1` | Max pages to fetch per ZIP code |

## Key Files

| File | Purpose |
|------|---------|
| `src/scrapers/zillow_scraper.py` | Main scraper implementation |
| `src/scrapers/base.py` | `BaseScraper` ABC definition + `_build_ssl_context()` |
| `data/certs/panw-root-ca.pem` | PANW Enterprise Root CA for TLS proxy |
| `config.yaml` → `zillow_api` | API configuration |
| `.env` → `RAPIDAPI_KEY` | API key (secret) |

## History

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
