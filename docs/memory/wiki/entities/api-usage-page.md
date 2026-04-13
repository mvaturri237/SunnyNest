# API Usage Page

> Admin page at `/admin/api-usage` with donut quota charts, success rate trends, monthly comparison, and daily sparklines for API budget monitoring.

**Status:** Active  
**Owner files:** `web/routes/admin.py`, `web/templates/admin/api-usage.html`, `web/static/css/admin.css`  
**Config:** `config.yaml` → `zillow_api`, `realtor_api`  
**Added:** 2026-03-30  
**Last updated:** 2026-04-06

## Overview

The API Usage page provides at-a-glance monitoring of API budget consumption across all RapidAPI sources (Zillow and Realtor.com). It was completely redesigned on 2026-04-06 from a verbose table-based layout to a scannable visual dashboard.

The page uses CSS-only visualizations (no JavaScript charting libraries) — `conic-gradient` for donut charts, CSS grid for sparklines, and flexbox for comparison bars.

## Architecture

- **Data source:** `api_call_log` table in SQLite, queried via `src/database.py` functions
- **Backend helper:** `_build_budget_data()` DRY helper builds per-source budget data with `prev_month_calls` parameter
- **Source-agnostic template:** `{% for source in sources %}` loop — adding future sources requires zero template changes
- **CSS-only charts:** No JavaScript charting libraries — all visualizations use CSS (`conic-gradient`, grid, flexbox)
- **Budget limits:** `API_BUDGET_LIMITS` dict in `web/routes/admin.py` — must match `config.yaml` values (see [Config Values Override](../concepts/css-cache-versioning.md))

## Current State

### Sections

| Section | Content |
|---------|---------|
| **Quota Overview** | CSS donut charts per source (Zillow 500/mo, Realtor.com 150/mo), status badges (✓ OK / ✗ Failed), last-10-calls dot visualization with tooltips |
| **Success Trends** | 7-day success rate trend chart + monthly comparison bars with delta percentages |
| **Daily Activity** | Daily call volume sparklines per source |

- **Warning banners:** Shown when API key is not configured or last API call is stale (>2 days)
- **Responsive:** Breakpoints at 1024px and 768px
- **Accessibility:** `prefers-reduced-motion`, WCAG AA compliant
- **~500 lines new CSS** added in the redesign

## Key Files

| File | Purpose |
|------|---------|
| `web/routes/admin.py` | Route handler + `_build_budget_data()` helper |
| `web/templates/admin/api-usage.html` | Page template with CSS-only charts |
| `web/static/css/admin.css` | Admin CSS including chart styles |
| `src/database.py` | `get_api_success_rate_by_day()`, `get_api_call_count_for_period()`, `get_api_call_count()` |

## History

- [2026-04-06] Fixed status badge bug — `status_code=None` (connection errors) now shows "Connection Error" (red) instead of false "Last call OK" (green). APPROVED (0 P1, 0 P2, 3 P3)
- [2026-04-06] Complete redesign — APPROVED (0 P1, 0 P2 after 1 fix cycle, 9 P3)
- [2026-04-06] P2 fixes: portable date formatting, removed duplicate DB function, dynamic source loop
- [2026-04-06] Realtor.com budget updated: 100 → 150 calls/month
- [2026-04-01] Refactored to multi-source with `_build_budget_data()` DRY helper (Realtor.com addition)
- [2026-03-31] Warning banner added when API key missing + staleness indicator
- [2026-03-30] Initial implementation as part of Phase 2 backoffice

## Related

- [Admin Dashboard](admin-dashboard.md) — parent admin panel
- [Zillow Scraper](zillow-scraper.md) — Zillow API budget (500/mo)
- [Realtor Scraper](realtor-scraper.md) — Realtor.com API budget (150/mo)
- [Database Schema](database-schema.md) — `api_call_log` table
- [CSS Cache Versioning](../concepts/css-cache-versioning.md) — admin.css version bumping
- [Jinja2 Safety](../concepts/jinja2-safety.md) — Unicode chars in templates (not HTML entities)
