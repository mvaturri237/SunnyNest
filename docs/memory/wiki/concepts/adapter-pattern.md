# Adapter Pattern

> All data source scrapers extend `BaseScraper(ABC)` with standardized `scrape()` and `normalize()` methods, enabling the orchestrator to treat all sources identically.

**Applies to:** [Zillow Scraper](../entities/zillow-scraper.md), [Craigslist Scraper](../entities/craigslist-scraper.md), [Realtor Scraper](../entities/realtor-scraper.md), [Orchestrator](../entities/orchestrator.md), [Notification System](../entities/notification-system.md)  
**Learned:** 2026-03-27  
**Source:** `docs/memory/shared/systemPatterns.md` — Multi-Source Scraper Pattern

## Pattern

All scrapers extend `BaseScraper(ABC)` defined in `src/scrapers/base.py`. The ABC requires two methods:
- `async scrape() -> list[dict]` — fetch raw listings from the source
- `normalize(raw: dict) -> dict` — convert source-specific format to standard listing format

The [Orchestrator](../entities/orchestrator.md) registers scrapers as `(name, instance)` tuples and runs them concurrently via `asyncio.gather`. It never contains source-specific logic — all source differences are encapsulated in the scraper adapters.

## Rules

1. **Never hardcode source-specific logic in shared components** — use the adapter pattern
2. **Adding a new source requires 5 steps:**
   - Create `src/scrapers/<source>_scraper.py` with `<Source>Scraper(BaseScraper)`
   - Add `(name, instance)` to `self._scrapers` in `src/orchestrator.py`
   - Add `<source>_api` section to `config.yaml`
   - Extend `_validate_environment()` and `get_env_status()` for the new env var
   - Add source to `API_BUDGET_LIMITS` dict in `web/routes/admin.py`
3. **Admin UI is source-agnostic:** API Usage page uses `{% for source in sources %}` loop — zero template changes for new sources
4. **Source filter auto-populates:** Dashboard source dropdown queries `listing_sources` table with `GROUP BY source`
5. **Budget guard pattern:** Each scraper checks `get_api_call_count(source)` against configurable threshold before making API calls
6. **API key resolution:** Source-specific env var → shared `RAPIDAPI_KEY` fallback → config.yaml fallback

## Examples

- **Zillow:** `ZillowScraper(BaseScraper)` — RapidAPI httpx client, 500 req/mo
- **Craigslist:** `CraigslistScraper(BaseScraper)` — Playwright HTML scraping, free
- **Realtor.com:** `RealtorScraper(BaseScraper)` — RapidAPI httpx client, 150 req/mo
- **Next recommended source:** Apartments.com (Playwright-based, ~40-50% unique listings)

## Related

- [Zillow Scraper](../entities/zillow-scraper.md), [Craigslist Scraper](../entities/craigslist-scraper.md), [Realtor Scraper](../entities/realtor-scraper.md) — implementations
- [Orchestrator](../entities/orchestrator.md) — source-agnostic coordinator
- [Config (YAML)](../entities/config-yaml.md) — per-source configuration sections
