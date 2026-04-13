# Skill: Data Scraping & Aggregation Best Practices

## Purpose
Guide the design and review of web scraping, API integration, and data aggregation systems.

## When to Use
When building, reviewing, or debugging scrapers, data pipelines, or multi-source aggregation.

## Architecture Principles

### Source Adapter Pattern
Each data source (Zillow, Craigslist, etc.) should have its own adapter that:
- Handles authentication and rate limiting for that source
- Transforms source-specific data into a common internal format
- Handles source-specific error codes and retry logic
- Is independently deployable and testable

### Common Data Model
Define a unified listing schema that all adapters output:
- id (internal), sourceId, source (zillow/craigslist/etc.)
- address, city, state, zip, lat, lng
- price, beds, baths, sqft, propertyType
- images (array), description
- listingUrl (original source link)
- firstSeen, lastSeen, lastUpdated
- status (active/removed/price_changed)

### Deduplication Strategy
- Match by address normalization (lowercase, strip apt/unit, standardize St/Street)
- Secondary match by lat/lng proximity (within 50m)
- When duplicate found: keep both source records, show unified listing to user
- Track price differences across sources

### Sync & Freshness
- Track lastSync per source (shown in your UI header)
- Implement incremental sync (only fetch new/changed listings)
- Mark listings as stale after N hours without confirmation
- Show "Last sync: X min ago" with visual indicator (green/yellow/red)

### Rate Limiting & Ethics
- Respect robots.txt
- Implement exponential backoff on failures
- Add random delays between requests (1-5 seconds)
- Cache aggressively to minimize requests
- Have a circuit breaker: stop scraping if error rate > 50%

### Error Handling
- Source unavailable: show cached data with "stale" indicator
- Partial failure: show available listings, log failed source
- Rate limited: back off and retry with increasing delay
- Data format changed: alert developer, fall back to cached data

## Review Checklist
- [ ] Each source has its own adapter with common interface
- [ ] Common data model is defined and enforced
- [ ] Deduplication logic handles address variations
- [ ] Rate limiting is implemented per source
- [ ] Stale data is detected and flagged
- [ ] Errors are handled gracefully (partial results > no results)
- [ ] Sync status is visible to the user
