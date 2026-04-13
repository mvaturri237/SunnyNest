# Listing Card

> Horizontal card component displaying listing image, price, specs, school assignments, source pills, and action buttons with HTMX-powered interactions.

**Status:** Active  
**Owner files:** `web/templates/partials/listing-card.html`, `web/templates/partials/listing-cards.html`, `web/static/css/style.css`  
**Config:** N/A  
**Added:** 2026-03-27  
**Last updated:** 2026-03-31

## Overview

The listing card is the primary UI component for displaying rental listings in the dashboard's left panel. It uses a horizontal layout (image left, details right) with price as the dominant element (20px/800 weight per design bible). Each card shows the listing image, price, address, specs (beds/baths/sqft with m² conversion), school assignments, source pills, and favorite/dislike action buttons.

Cards are rendered as HTMX partials — filter changes swap the entire card list, while favorite/dislike actions swap individual cards.

## Architecture

- **Horizontal layout:** Image (140×130px fixed) left, details right — `flex-shrink: 0` on thumbnail
- **Image handling:** `object-fit: cover` for aspect ratio, `onerror` fallback handler, `overflow: hidden` on container
- **Price dominant:** 20px/800 weight, max 3 badges per card (per design bible)
- **School display:** `🏫 Cherry Chase Elem · Columbia Middle · Fremont HS` with `abbreviate_school` Jinja2 filter
- **Source pills:** Multi-source badges from `listing.sources` relationship with brand colors (`.source-zillow`, `.source-craigslist`, `.source-realtor`)
- **HTMX interactions:**
  - Favorite toggle: renders `favorite-button.html` partial with `is_fav` state
  - Dislike: empty HTML + `hx-target="closest .listing-card"` + `hx-swap="outerHTML"` (card disappears)
  - OOB result count update on filter change
- **Image URL parsing:** `first_image` Jinja2 custom filter using `json.loads()` (replaces brittle string slicing)
- **Area display:** Shows BOTH sqft AND m² — e.g., "1,200 sqft (111 m²)" per design bible

## Current State

- **Working:** Fully operational with all features
- **Design bible compliant:** Inter font, blue accent (#2563eb), horizontal layout, price dominant
- **Accessibility:** Semantic HTML, focus-visible states
- **Known P3:** `.tag-price-drop` uses same green as `.tag-new` — consider amber/orange for distinction

## Key Files

| File | Purpose |
|------|---------|
| `web/templates/partials/listing-card.html` | Single card template |
| `web/templates/partials/listing-cards.html` | Card list wrapper (HTMX swap target) |
| `web/templates/partials/favorite-button.html` | Favorite toggle partial |
| `web/static/css/style.css` | Card CSS styles |
| `web/dependencies.py` | `first_image`, `abbreviate_school` Jinja2 filters |

## History

- [2026-03-31] School assignment display added (🏫 with abbreviations)
- [2026-03-31] Multi-source pill badges from `listing.sources` relationship
- [2026-03-30] Bug fix round: dislike card disappear, favorite toggle, image URL parsing
- [2026-03-30] Phase 1 Sprint 2: functional favorites and dislikes with HTMX
- [2026-03-30] Light mode switch — CSS custom properties updated
- [2026-03-27] Initial implementation

## Related

- [Filter Bar](filter-bar.md) — filter changes swap card list
- [Map View](map-view.md) — bidirectional card-map sync
- [School Districts](school-districts.md) — school data displayed on cards
- [Deduplication](deduplication.md) — multi-source pills from `listing_sources`
