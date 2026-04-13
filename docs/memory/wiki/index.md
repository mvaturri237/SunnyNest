# SunnyNest Wiki Index

> Last updated: 2026-04-13 | Entities: 16 | Concepts: 10 | Last sync: 2026-04-13T12:54Z

## Entity Pages

### Data Pipeline

| Entity | Status | Summary | Last Updated |
|--------|--------|---------|--------------|
| [Zillow Scraper](entities/zillow-scraper.md) | Active | RapidAPI source, 500 req/mo, primary data source | 2026-04-06 |
| [Craigslist Scraper](entities/craigslist-scraper.md) | Active | HTML scraping via Playwright, free, secondary source | 2026-04-06 |
| [Realtor Scraper](entities/realtor-scraper.md) | Active | RapidAPI source, 150 req/mo, third data source | 2026-04-06 |
| [Orchestrator](entities/orchestrator.md) | Active | Coordinates scrape→normalize→geocode→enrich→upsert→dedup pipeline | 2026-04-06 |
| [Deduplication](entities/deduplication.md) | Active | Cross-source dedup via multi-signal scoring, threshold ≥75 | 2026-04-06 |
| [Geocoder](entities/geocoder.md) | Active | Nominatim + LRU cache + circuit breaker | 2026-03-27 |

### User-Facing UI

| Entity | Status | Summary | Last Updated |
|--------|--------|---------|--------------|
| [Filter Bar](entities/filter-bar.md) | Active | Price/Beds/Baths/More dropdowns, HTMX-driven, default ≤30d | 2026-04-13 |
| [Map View](entities/map-view.md) | Active | Leaflet.js, price pills, boundary overlay, card-map sync, no clustering | 2026-04-13 |
| [Listing Card](entities/listing-card.md) | Active | Horizontal card with image, price, schools, source pills | 2026-03-31 |

### Admin / Backend

| Entity | Status | Summary | Last Updated |
|--------|--------|---------|--------------|
| [Admin Dashboard](entities/admin-dashboard.md) | Active | System health, sync button, scrape heatmap, 5 admin pages | 2026-04-06 |
| [API Usage Page](entities/api-usage-page.md) | Active | Donut charts, success trends, sparklines | 2026-04-06 |
| [Notification System](entities/notification-system.md) | Active | Email + WhatsApp channels, config-filtered, anti-spam guard | 2026-04-12 |
| [Scheduler (launchd)](entities/scheduler-launchd.md) | Active | 6 plists: scraper, notify-am/pm, dashboard, backoffice, log-rotate | 2026-04-13 |
| [Database Schema](entities/database-schema.md) | Active | SQLite, 5 tables, manual migrations | 2026-04-06 |
| [School Districts](entities/school-districts.md) | Active | GeoJSON boundaries, shapely point-in-polygon | 2026-03-31 |
| [Config (YAML)](entities/config-yaml.md) | Active | Central config: filters, API keys, notification settings | 2026-04-12 |

## Concept Pages

| Concept | Applies To | Summary |
|---------|-----------|---------|
| [Adapter Pattern](concepts/adapter-pattern.md) | Scrapers, Orchestrator | BaseScraper ABC, source-agnostic orchestrator |
| [App Isolation](concepts/app-isolation.md) | Dashboard, Backoffice | Separate Streamlit apps, no st.sidebar in app.py |
| [CSS Cache Versioning](concepts/css-cache-versioning.md) | All CSS files | Bump ?v=N on every CSS change |
| [Environment Validation](concepts/environment-validation.md) | Startup, Admin | Validate env vars at boot, show in System Health |
| [Jinja2 Safety](concepts/jinja2-safety.md) | All templates | Unicode chars only, no HTML entities in {{ }} |
| [launchd Patterns](concepts/launchd-patterns.md) | Scheduler, Dashboard | macOS process management, TCC, Homebrew Python |
| [Review Cycle](concepts/review-cycle.md) | All code changes | Code→Review→Fix mandatory cycle |
| [Security Patterns](concepts/security-patterns.md) | XSS, TLS, secrets | html.escape, verify=True, env vars for secrets |
| [Silent Failure Pattern](concepts/silent-failure-pattern.md) | Scrapers, SMTP | Credential-dependent features fail silently |
| [Upsert Exclusion Pattern](concepts/upsert-exclusion-pattern.md) | Database | User-managed flags excluded from scraper updates |

## Plans

| Plan | Status | Summary |
|------|--------|---------|
| [`architecture.md`](../../../plans/architecture.md) | REFERENCE | System architecture overview |
| [`backoffice.md`](../../../plans/backoffice.md) | IMPLEMENTED | Backoffice admin panel (5 pages) |
| [`cloud-scheduler.md`](../../../plans/cloud-scheduler.md) | EVALUATED | GitHub Actions + git-committed DB recommended |
| [`deduplication.md`](../../../plans/deduplication.md) | IMPLEMENTED | Cross-source dedup system |
| [`filter-bar-redesign.md`](../../../plans/filter-bar-redesign.md) | IMPLEMENTED | 6-phase filter bar redesign |
| [`frontend-migration.md`](../../../plans/frontend-migration.md) | IMPLEMENTED | FastAPI + HTMX migration |
| [`frontend-migration-arch-review.md`](../../../plans/frontend-migration-arch-review.md) | IMPLEMENTED | Architecture review for migration |
| [`frontend-migration-final.md`](../../../plans/frontend-migration-final.md) | IMPLEMENTED | Final migration plan |
| [`frontend-migration-ux-review.md`](../../../plans/frontend-migration-ux-review.md) | IMPLEMENTED | UX review for migration |
| [`listing-lifecycle.md`](../../../plans/listing-lifecycle.md) | IMPLEMENTED | Listing lifecycle analytics, deactivated_at, days-on-market filter |
| [`llm-wiki.md`](../../../plans/llm-wiki.md) | IN PROGRESS | LLM Wiki implementation (this wiki) |
| [`map-framework-evaluation.md`](../../../plans/map-framework-evaluation.md) | RECOMMENDATION | Stay with Leaflet.js |
| [`map-improvement.md`](../../../plans/map-improvement.md) | PARTIAL | Map UX consultation (tiles done, POI planned) |
| [`map-makeover-impl.md`](../../../plans/map-makeover-impl.md) | PLANNED | Map makeover implementation |
| [`notification-scheduler.md`](../../../plans/notification-scheduler.md) | IMPLEMENTED | Notification scheduling |
| [`phase1-ux-spec.md`](../../../plans/phase1-ux-spec.md) | IMPLEMENTED | Phase 1 UX specification |
| [`price-history.md`](../../../plans/price-history.md) | PLANNED | Price history tracking |
| [`realtor-scraper.md`](../../../plans/realtor-scraper.md) | IMPLEMENTED | Realtor.com scraper |
| [`scheduler-fix.md`](../../../plans/scheduler-fix.md) | IMPLEMENTED | APScheduler → launchd migration |
| [`school-assignment.md`](../../../plans/school-assignment.md) | IMPLEMENTED | School assignment lookup |
| [`ui-makeover.md`](../../../plans/ui-makeover.md) | SUPERSEDED | UI makeover (superseded by frontend migration) |
| [`ui-polish.md`](../../../plans/ui-polish.md) | SUPERSEDED | UI polish (superseded by frontend migration) |
| [`ui-redesign.md`](../../../plans/ui-redesign.md) | SUPERSEDED | UI redesign (superseded by frontend migration) |

## Quick Reference

- **Log:** [log.md](log.md) — chronological record of all changes
- **Shared files:** [decisionLog](../shared/decisionLog.md) · [lessonsLearned](../shared/lessonsLearned.md) · [systemPatterns](../shared/systemPatterns.md)
- **Design Bible:** [design-bible.md](../../design/design-bible.md)
- **Active Context:** [activeContext.md](../tasks/default/activeContext.md)
- **Progress:** [progress.md](../tasks/default/progress.md)
