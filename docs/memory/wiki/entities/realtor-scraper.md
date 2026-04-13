# Realtor.com Scraper

> Third data source fetching MLS-sourced rental listings via RapidAPI "Realtor Search", catching listings 12-24h before Zillow with ~30% unique coverage.

**Status:** Active  
**Owner files:** `src/scrapers/realtor_scraper.py`, `src/scrapers/base.py`  
**Config:** `config.yaml` → `realtor_api`  
**Added:** 2026-04-01  
**Last updated:** 2026-04-06

## Overview

The Realtor.com scraper is the third data source for SunnyNest, added to increase listing coverage beyond Zillow and Craigslist. It uses the "Realtor Search" API by API_Jeeves on RapidAPI, searching by city (not per-ZIP) to optimize the free tier budget. MLS-sourced data catches listings 12-24h before they appear on Zillow.

The scraper extends `BaseScraper(ABC)` following the [Adapter Pattern](../concepts/adapter-pattern.md) and mirrors the ZillowScraper pattern with improvements: configurable budget from config, `enabled` flag, and defensive JSON parsing.

## Architecture

- Extends `BaseScraper` ABC (~580 lines)
- API: `realtor-search.p.rapidapi.com`, `GET /properties/search-rent` endpoint with `propertyType=single_family` filter
- Search by city (Sunnyvale) instead of per-ZIP → 1 call/page instead of 4
- Max 2 pages per sync → ~60 calls/month (well within 150 free tier)
- API key resolution: `REALTOR_RAPIDAPI_KEY` env var → shared `RAPIDAPI_KEY` fallback
- `enabled: true` by default — scraper skips gracefully when API key is missing
- Budget guard: configurable `monthly_budget` and `budget_threshold` from `config.yaml`
- Pet policy keyword extraction with negative-before-positive ordering
- API call logging prevents double-counting on error responses
- SSL: Uses custom SSL context from `BaseScraper._build_ssl_context()` — loads PANW Enterprise Root CA for TLS decryption proxy compatibility, clears `VERIFY_X509_STRICT` for OpenSSL 3.6+ AKI compatibility (see [Security Patterns](../concepts/security-patterns.md))

## Current State

- **Working:** Fully operational, runs daily at 06:00 via [launchd scheduler](scheduler-launchd.md)
- **Free tier:** 150 req/month — daily sync with max 2 pages uses ~60 calls/month
- **Action needed:** User must subscribe to "Realtor Search" API on RapidAPI and set API key
- **24h delay:** New Realtor.com listings have 24h delay vs 6h for Zillow — acceptable since main value is catching listings Zillow misses entirely

## Configuration

| Key | Default | Description |
|-----|---------|-------------|
| `realtor_api.rapidapi_key` | `""` | Set via `REALTOR_RAPIDAPI_KEY` env var (or `RAPIDAPI_KEY` fallback) |
| `realtor_api.rapidapi_host` | `realtor-search.p.rapidapi.com` | RapidAPI host header |
| `realtor_api.monthly_budget` | `150` | API call limit per month |
| `realtor_api.budget_threshold` | `90` | Stop scraping at 90% of budget |
| `realtor_api.enabled` | `true` | Can disable without removing config |

## Key Files

| File | Purpose |
|------|---------|
| `src/scrapers/realtor_scraper.py` | Main scraper implementation (~580 lines) |
| `src/scrapers/base.py` | `BaseScraper` ABC definition + `_build_ssl_context()` |
| `data/certs/panw-root-ca.pem` | PANW Enterprise Root CA for TLS proxy |
| `config.yaml` → `realtor_api` | API configuration |
| `.env` → `REALTOR_RAPIDAPI_KEY` | API key (optional, falls back to `RAPIDAPI_KEY`) |

## History

- [2026-04-06] Added `propertyType=single_family` API filter — now fetches only houses (17 vs 171 mixed types). APPROVED (0 P1, 0 P2, 3 P3)
- [2026-04-06] SSL fix — custom SSL context with PANW root CA + relaxed VERIFY_X509_STRICT for OpenSSL 3.6 compatibility. APPROVED (0 P1, 0 P2, 3 P3)
- [2026-04-06] Budget updated from 100 to 150 calls/month; scheduler migrated to launchd
- [2026-04-06] Admin API Usage page redesigned with donut charts showing Realtor.com quota
- [2026-04-01] Initial implementation — APPROVED (0 P1, 0 P2, 8 P3 after fix cycle)
- [2026-04-01] Architecture plan created (`plans/realtor-scraper.md`)

## Related

- [Zillow Scraper](zillow-scraper.md) — primary data source, shares `RAPIDAPI_KEY`
- [Craigslist Scraper](craigslist-scraper.md) — secondary data source (HTML scraping)
- [Orchestrator](orchestrator.md) — coordinates the full pipeline
- [API Usage Page](api-usage-page.md) — displays Realtor.com budget/usage
- [Config (YAML)](config-yaml.md) — `realtor_api` section
- [Adapter Pattern](../concepts/adapter-pattern.md) — BaseScraper ABC pattern
- [Plan: Realtor Scraper](../../../../plans/realtor-scraper.md) — architecture plan
