# Listing Card

> Horizontal card component displaying listing image, price, specs, school assignments, source pills, and action buttons with HTMX-powered interactions.

**Status:** Active
**Owner files:** `web/templates/partials/listing-card.html`, `web/templates/partials/listing-cards.html`, `web/static/css/style.css`
**Config:** `FAVORITE_SCHOOLS` constant in `web/dependencies.py:75`
**Added:** 2026-03-27
**Last updated:** 2026-06-04

## Overview

The listing card is the primary UI component for displaying rental listings in the dashboard's left panel. It uses a horizontal layout (image left, details right) with price as the dominant element (20px/800 weight per design bible). Each card shows the listing image, price, address, specs (beds/baths/sqft with m² conversion), school assignments, source pills, and favorite/dislike action buttons.

Cards are rendered as HTMX partials — filter changes swap the entire card list, while favorite/dislike actions swap individual cards.

## Architecture

- **Horizontal layout:** Image (140×130px fixed) left, details right — `flex-shrink: 0` on thumbnail
- **Image handling:** `object-fit: cover` for aspect ratio, `onerror` fallback handler, `overflow: hidden` on container
- **Price dominant:** 20px/800 weight, max 3 badges per card (per design bible)
- **School display:** `🏫 Cherry Chase Elem · Columbia Middle · Fremont HS` with `abbreviate_school` Jinja2 filter — **HIDDEN 2026-06-04** via [`SCHOOLS_UI_ENABLED`](../../../../web/dependencies.py:107) flag (DB assignments are inaccurate; see [`plans/school-boundaries-nces.md`](../../../../plans/school-boundaries-nces.md))
- **Favorite-school highlight (Option C, 2026-06-03 — dormant since 2026-06-04):** When `listing.school_elementary | is_favorite_school`, the matching school in the schools row is wrapped in `<span class="school-pill-fav">★ …</span>` (green-700 on green-100, AA 4.71:1, ★ U+2605 literal NOT HTML entity per AGENTS.md §5). The card root gets `is-fav-school` class + `data-fav-school="1"` attribute (the latter consumed by [`map.js`](../../../../web/static/js/map.js:277) to apply the `.price-pill-marker.is-fav-school` green variant). Single source of truth: `FAVORITE_SCHOOLS` frozenset in [`web/dependencies.py:75`](../../../../web/dependencies.py:75). Elementary-only for v1. **Currently disabled** via the flag — all CSS rules + JS dataset wiring + Python helpers preserved, dormant. Re-enable is a 1-line flip per the plan's Definition-of-Done.
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
- **Known P3s (favorite-school highlight):** SCHOOL-P3-12 unit-test pin Python↔JS favorite lists; SCHOOL-P3-13 move name normalization to ingest-time; SCHOOL-P3-14 `.is-fav-school` card root has no CSS treatment yet; SCHOOL-P3-15 `_normalize_school_name` should `.strip()` for whitespace defense

## Key Files

| File | Purpose |
|------|---------|
| `web/templates/partials/listing-card.html` | Single card template |
| `web/templates/partials/listing-cards.html` | Card list wrapper (HTMX swap target) |
| `web/templates/partials/favorite-button.html` | Favorite toggle partial |
| `web/static/css/style.css` | Card CSS styles (including `.school-pill-fav` at lines 1126-1163) |
| `web/dependencies.py` | `first_image`, `abbreviate_school`, `is_favorite_school` Jinja2 filters/tests + `FAVORITE_SCHOOLS` frozenset |

## History

- [2026-06-04] **Schools row + favorite-school chip DISABLED via `SCHOOLS_UI_ENABLED` flag.** User screenshot showed wrong school assignments (Mountain View listing tagged `Cherry Chase`). Root cause is upstream (approximate-rectangle boundary polygons + geocoder centroid fallback). Flag gates both the entire `.card-schools` row AND the `data-fav-school` attribute. Map green pill goes dormant via natural-disable chain (no JS edit needed). Re-enable when [`plans/school-boundaries-nces.md`](../../../../plans/school-boundaries-nces.md) completes. ✅ APPROVED (0 P1/P2, +1 P3 SCHOOL-P3-17).
- [2026-06-03] **Favorite-school highlight added (Option C)** — `.school-pill-fav` chip in schools row + `is-fav-school` class + `data-fav-school` attr on card root. `FAVORITE_SCHOOLS` frozenset in `web/dependencies.py` is the single source of truth (mirrors `map.js` SCHOOLS `isFavorite:true` set). 36 listings in DB match (3 rendered on default homepage). ✅ APPROVED (0 P1/P2, 4 new P3s).
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
