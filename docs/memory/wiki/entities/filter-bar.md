# Filter Bar

> HTMX-driven filter bar with Price, Beds/Baths, More, and Sort dropdowns, featuring dropdown panels, keyboard navigation, and WCAG AA accessibility.

**Status:** Active  
**Owner files:** `web/static/js/filters.js`, `web/templates/dashboard.html`, `web/routes/__init__.py`  
**Config:** `config.yaml` → `filters`  
**Added:** 2026-03-31  
**Last updated:** 2026-05-14

## Overview

The filter bar is the primary search refinement UI on the dashboard. It provides dropdown panels for Price, Beds & Baths, More (sqft, amenities, favorites), and a Sort control. All filters trigger HTMX requests that update the listing cards and result count without full page reloads.

The implementation was a complete redesign from the original Streamlit filter widgets, built in 6 phases with full WCAG AA accessibility compliance.

## Architecture

- **Dropdown infrastructure:** `.filter-dropdown` wrapper, `.filter-pill` button, `.filter-panel` panel
- **Interaction patterns:**
  - Click outside → close without applying
  - Escape → close
  - Focus trap within open panels
  - `aria-expanded`, `aria-haspopup="dialog"`, `role="dialog"`
- **HTMX integration:** Apply button dispatches custom `"apply"` event after updating hidden inputs; HTMX listens via `hx-trigger="apply"` to ensure values are committed before the request fires
- **Backend:** `parse_filters()` in `web/routes/__init__.py` handles 8+ filter params
- **Source filter:** Multi-select checkbox dropdown with Zillow, Craigslist, Realtor.com (all checked by default)
- **Snapshot/revert:** Filter state is snapshot on panel open, reverted on close-without-apply

## Current State

- **Working:** All 6 phases implemented and approved
- **Filters available:**
  - **Price:** Min/Max text inputs + 5 quick-range radios (Under $4K, $4K–$5K, $5K–$7.5K, $6.5K–$8K, $8K+)
  - **Beds & Baths:** Segmented button groups (Any/1+/2+/3+/4+ beds, Any/1+/2+/3+ baths) with `role="radiogroup"` and arrow key navigation
  - **Source:** Multi-select checkbox dropdown (3 sources, all selected by default)
  - **Days Listed:** Radio presets (Any/≤7d/≤14d/≤30d/≤60d) + custom numeric input, filters by `days_on_market` column
  - **More:** Sqft min/max with m² conversion preview, Pet/AC/Furnished checkboxes, Favorites Only, "Reset all filters"
  - **Sort:** Moved to right side with vertical divider
- **Mobile responsive:** 3 breakpoints (1024px, 768px, 480px) with bottom-sheet pattern on mobile
- **Accessibility:** `prefers-reduced-motion` respected, focus trap, keyboard navigation

## Configuration

Default filter values come from `config.yaml` → `filters` and `_DROPDOWN_DEFAULTS` in `web/routes/dashboard.py`:

| Key | Default | Description |
|-----|---------|-------------|
| `filters.min_price` | `5000` | Default minimum price |
| `filters.max_price` | `7500` | Default maximum price |
| `filters.min_bedrooms` | `3` | Default minimum bedrooms |
| `filters.max_bedrooms` | `4` | Default maximum bedrooms |
| `_DROPDOWN_DEFAULTS.filter_max_days` | `"30"` | Default max days on market (hardcoded in dashboard.py) |

## Key Files

| File | Purpose |
|------|---------|
| `web/static/js/filters.js` | Filter logic (669 lines) — snapshot/revert, focus trap, keyboard nav |
| `web/templates/dashboard.html` | Filter bar HTML structure |
| `web/routes/__init__.py` | `parse_filters()` — parses 8+ filter params from request |
| `web/routes/listings.py` | Listing query with applied filters |
| `web/static/css/style.css` | Filter bar CSS with 10 design tokens |

## History

- [2026-04-13] Filter bar left-aligned — removed `max-width: 1920px` and `margin: 0 auto` from `.filter-bar-inner` in `style.css`. Logo and filters now flush-left instead of centered.
- [2026-04-10] Default "📅 Days Listed" filter changed from "Any" to ≤30 days — `_DROPDOWN_DEFAULTS["filter_max_days"]` in `dashboard.py` set to `"30"`. Hides old listings (e.g., 500+ day Realtor.com listings) by default; user can still select "Any" or custom value
- [2026-04-06] "📅 Days Listed" dropdown added between Source and More — radio presets (Any/≤7d/≤14d/≤30d/≤60d) + custom input, filters by `days_on_market` column, full snapshot/revert/apply pattern
- [2026-04-06] Fixed HTMX race condition — Apply buttons now use `hx-trigger="apply"` custom event to ensure hidden inputs are updated before HTMX fires
- [2026-04-06] Multi-select source filter verified + `.source-realtor` CSS class added
- [2026-03-31] All 6 phases implemented — APPROVED (0 P1, 0 P2 after fix cycle)
- [2026-03-31] Architecture plan created (`plans/filter-bar-redesign.md`)
- [2026-03-28] "More Filters" expander removed from old Streamlit app

## Related

- [Listing Card](listing-card.md) — filtered results displayed as cards
- [Map View](map-view.md) — map markers update with filter changes
- [Config (YAML)](config-yaml.md) — default filter values
- [Plan: Filter Bar Redesign](../../../../plans/filter-bar-redesign.md) — architecture plan
