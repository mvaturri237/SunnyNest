# SunnyNest Wiki Index

> Last updated: 2026-06-04 | Entities: 16 | Concepts: 12 | Last sync: 2026-06-04T12:20Z

## Entity Pages

### Data Pipeline

| Entity | Status | Summary | Last Updated |
|--------|--------|---------|--------------|
| [Zillow Scraper](entities/zillow-scraper.md) | Active | RapidAPI source, 500 req/mo, primary data source. `/search/byaddress` does NOT expose availability date (verified 2026-06-03 probe). **2026-06-04: response-side status guard added in `normalize()` after off-market for-sale rows leaked into rental results (Bug A).** | 2026-06-04 |
| [Craigslist Scraper](entities/craigslist-scraper.md) | Active | HTML scraping via Playwright, free, secondary source | 2026-04-06 |
| [Realtor Scraper](entities/realtor-scraper.md) | Active | RapidAPI source, 150 req/mo, third data source | 2026-04-06 |
| [Orchestrator](entities/orchestrator.md) | Active | Coordinates scrape→normalize→geocode→enrich→upsert→dedup pipeline. **2026-06-04: handles `normalize()→None` as skip; `mark_inactive()` now hysteresis-based (N=3 consecutive misses) — Bug B coordination.** | 2026-06-04 |
| [Deduplication](entities/deduplication.md) | Active | Cross-source dedup via multi-signal scoring, threshold ≥75; query-then-reassign on merge to avoid `uq_ls_source_external_id` collision | 2026-05-08 |
| [Geocoder](entities/geocoder.md) | Active | Nominatim + LRU cache + circuit breaker. ⚠️ Known P2: `geocode_address()` silent city-centroid fallback corrupts production listing coords (open, 2026-06-03) | 2026-06-03 |

### User-Facing UI

| Entity | Status | Summary | Last Updated |
|--------|--------|---------|--------------|
| [Filter Bar](entities/filter-bar.md) | Active | Price/Beds/Baths/More dropdowns, HTMX-driven, default ≤30d | 2026-05-14 |
| [Map View](entities/map-view.md) | Active | Leaflet.js, price pills, boundary overlay, card-map sync, no clustering, 15 school POI pins (6 green favorites, hover tooltip, always on), **NEW 2026-06-04: featured POI variant** (Ortega Park, 36×36 ringed pin + always-shown label, per-entry `featured: true` flag in JSON). Green price-pill favorite-school variant **dormant** via `SCHOOLS_UI_ENABLED=False` | 2026-06-04 |
| [Listing Card](entities/listing-card.md) | Active | Horizontal card with image, price, source pills. Schools row + `.school-pill-fav` chip **hidden** 2026-06-04 via `SCHOOLS_UI_ENABLED=False` flag (DB assignments wrong — see [`plans/school-boundaries-nces.md`](../../../plans/school-boundaries-nces.md)) | 2026-06-04 |

### Admin / Backend

| Entity | Status | Summary | Last Updated |
|--------|--------|---------|--------------|
| [Admin Dashboard](entities/admin-dashboard.md) | Active | System health, sync button, scrape heatmap, 5 admin pages, Telegram + WhatsApp credential banners | 2026-05-10 |
| [API Usage Page](entities/api-usage-page.md) | Active | Donut charts, success trends, sparklines | 2026-04-06 |
| [Notification System](entities/notification-system.md) | Active | Email + Telegram (primary) + WhatsApp (disabled) channels, config-filtered, anti-spam counts successes only, silence-detector banner | 2026-06-03 |
| [Scheduler (launchd)](entities/scheduler-launchd.md) | Active | 6 plists: scraper, notify-am (10:00), notify-pm (20:00), dashboard, backoffice, log-rotate | 2026-06-03 |
| [Database Schema](entities/database-schema.md) | Active | SQLite, 5 tables, manual migrations, notification_log error columns, naive-UTC storage convention. **2026-06-04: `consecutive_misses INTEGER NOT NULL DEFAULT 0` added to `listings` table for `mark_inactive()` hysteresis.** | 2026-06-04 |
| [School Districts](entities/school-districts.md) | Active | GeoJSON boundaries, shapely point-in-polygon. 15 schools rendered as POI markers on map. ⚠️ **DB assignments wrong** (approximate-rectangle polygons) — UI hidden 2026-06-04 via `SCHOOLS_UI_ENABLED=False`. Fix planned in [`plans/school-boundaries-nces.md`](../../../plans/school-boundaries-nces.md) (hybrid CUSD ArcGIS + manual PDF trace, 8–18 h) | 2026-06-04 |
| [Config (YAML)](entities/config-yaml.md) | Active | Central config: filters, API keys, notification settings (email/telegram/whatsapp) | 2026-06-03 |

## Concept Pages

| Concept | Applies To | Summary |
|---------|-----------|---------|
| [Adapter Pattern](concepts/adapter-pattern.md) | Scrapers, Orchestrator | BaseScraper ABC, source-agnostic orchestrator |
| [Agent Failure Discipline](concepts/agent-failure-discipline.md) | All agent modes | 2-failure escalation rule + 7 "never assume" principles (zero-trust) |
| [Agent Mode Tiering](concepts/agent-mode-tiering.md) | All agent modes | Tier 1 (load every task) vs Tier 2 (load on demand) skill loading |
| [App Isolation](concepts/app-isolation.md) | Dashboard, Backoffice | Separate Streamlit apps, no st.sidebar in app.py |
| [CSS Cache Versioning](concepts/css-cache-versioning.md) | All CSS files | Bump ?v=N on every CSS change |
| [Environment Validation](concepts/environment-validation.md) | Startup, Admin | Validate env vars at boot, show in System Health |
| [Jinja2 Safety](concepts/jinja2-safety.md) | All templates | Unicode chars only, no HTML entities in {{ }} |
| [launchd Patterns](concepts/launchd-patterns.md) | Scheduler, Dashboard | macOS process management, TCC, Homebrew Python |
| [Review Cycle](concepts/review-cycle.md) | All code changes | Code→Review→Fix mandatory cycle |
| [Security Patterns](concepts/security-patterns.md) | XSS, TLS, secrets | html.escape, verify=True, env vars for secrets |
| [Silent Failure Pattern](concepts/silent-failure-pattern.md) | Scrapers, Notifier, Anti-spam, Docstrings | Rule #3 inverted 2026-06-03 (count successes for inbox-rationing caps); new docstring-drift + duplication sub-patterns; **2026-06-04 trust-the-provider sub-pattern (scraper response-side validation + lifecycle hysteresis required together)** |
| [Upsert Exclusion Pattern](concepts/upsert-exclusion-pattern.md) | Database | User-managed flags excluded from scraper updates |

## Plans

| Plan | Status | Summary |
|------|--------|---------|
| [`agent-team-cleanup.md`](../../../plans/agent-team-cleanup.md) | PLANNED (2026-05-09) | Wire orphan skills, migrate dev-reviewer + ux-designer to Tier 1/Tier 2, fix routing blind spots, trim memory |
| [`architecture.md`](../../../plans/architecture.md) | REFERENCE | System architecture overview |
| [`available-date-feature.md`](../../../plans/available-date-feature.md) | KILLED (2026-06-03) | "Available date" on listing card — Zillow `/search/byaddress` doesn't expose the field; Realtor/Craigslist also ❌/⚠️. Reopen criteria documented in plan header. |
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
| [`school-boundaries-nces.md`](../../../plans/school-boundaries-nces.md) | PLANNED (2026-06-04) | Replace approximate-rectangle school polygons with hybrid district-direct (CUSD ArcGIS) + manual PDF trace (SSD/SCUSD/FUHSD); ~8–18 h; **re-enables [`SCHOOLS_UI_ENABLED`](../../../web/dependencies.py:107) as last step of Definition-of-Done** |
| [`telegram-channel.md`](../../../plans/telegram-channel.md) | IMPLEMENTED (2026-05-10) | New TelegramChannel notification adapter; replaces WhatsApp as primary push channel (WhatsApp kept but disabled). Code Reviewer ✅ APPROVED, 0 P1/P2, 4 P3s in backlog. |
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
