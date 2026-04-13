# Craigslist Scraper

> Secondary data source that scrapes Craigslist rental listings via HTML parsing with Playwright, providing free supplementary coverage.

**Status:** Active  
**Owner files:** `src/scrapers/craigslist_scraper.py`, `src/scrapers/base.py`  
**Config:** `config.yaml` → `scraper`  
**Added:** 2026-03-27  
**Last updated:** 2026-04-06

## Overview

The Craigslist scraper is the secondary data source for SunnyNest. Unlike the API-based Zillow and Realtor scrapers, it uses Playwright for HTML scraping of Craigslist search results and individual listing pages. It extends `BaseScraper(ABC)` following the [Adapter Pattern](../concepts/adapter-pattern.md).

The scraper searches for Sunnyvale house rentals, optionally visiting detail pages to extract street addresses (configurable via `scrape_detail_pages`). It's free with no API budget constraints.

## Architecture

- Extends `BaseScraper` ABC with `async scrape() -> list[dict]` and `normalize(raw: dict) -> dict`
- Uses Playwright for browser-based HTML scraping (handles JavaScript-rendered content)
- `_normalize_property_type()` defaults unknown/empty types to `"house"`
- API call logging added via `log_api_call("craigslist", ...)` on 3 code paths: success, navigation error, fatal error
- `url` variable initialized to `None` before try block to prevent `UnboundLocalError` in outer except

## Current State

- **Working:** Fully operational, runs daily at 06:00 via [launchd scheduler](scheduler-launchd.md)
- **Free:** No API costs — direct HTML scraping
- **Known caveat:** Craigslist renewal dates overwrite original `listed_date` — the search results meta text shows the renewal date, not the original posting date. Fixed via monotonic date protection in `upsert_listing()` (see [Upsert Exclusion Pattern](../concepts/upsert-exclusion-pattern.md))
- **Detail page scraping:** When `scrape_detail_pages: true`, visits each listing page for street addresses (slower but more accurate)

## Configuration

| Key | Default | Description |
|-----|---------|-------------|
| `scraper.scrape_detail_pages` | `true` | Visit individual listing pages for street addresses |
| `scraper.request_delay_min` | `3` | Min seconds between requests |
| `scraper.request_delay_max` | `8` | Max seconds between requests |

## Key Files

| File | Purpose |
|------|---------|
| `src/scrapers/craigslist_scraper.py` | Main scraper implementation |
| `src/scrapers/base.py` | `BaseScraper` ABC definition |
| `config.yaml` → `scraper` | Shared scraper configuration |

## History

- [2026-04-06] Scheduler migrated to launchd — runs via `scripts/run-scraper.py`
- [2026-03-31] Renewal date overwrite fix — `listed_date` excluded from generic update loop, min-date logic applied
- [2026-03-28] API call logging added on 3 code paths; `url` initialization fix for `UnboundLocalError`
- [2026-03-28] Default property type changed from "apartment" to "house"
- [2026-03-28] Scrape interval changed from 24h to 6h
- [2026-03-27] Initial implementation

## Related

- [Zillow Scraper](zillow-scraper.md) — primary data source
- [Realtor Scraper](realtor-scraper.md) — third data source
- [Orchestrator](orchestrator.md) — coordinates the full pipeline
- [Deduplication](deduplication.md) — cross-source dedup catches same property on Craigslist + Zillow
- [Adapter Pattern](../concepts/adapter-pattern.md) — BaseScraper ABC pattern
- [Upsert Exclusion Pattern](../concepts/upsert-exclusion-pattern.md) — renewal date protection
