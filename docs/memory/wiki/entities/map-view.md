# Map View

> Leaflet.js-based interactive map with price pill markers, Sunnyvale boundary overlay, and bidirectional card-map sync.

**Status:** Active
**Owner files:** `web/static/js/map.js`, `web/templates/dashboard.html`
**Config:** N/A
**Added:** 2026-03-29
**Last updated:** 2026-06-03

## Overview

The map view is the right panel of the dashboard, showing rental listings as interactive price pill markers on an OpenStreetMap base layer. It includes a Sunnyvale city boundary GeoJSON overlay and bidirectional sync with listing cards (hover card → highlight marker, click marker → scroll to card).

The map framework was evaluated against 6 alternatives — **Leaflet.js was confirmed as the right choice** (168 weighted points, highest score) due to zero migration cost, best plugin ecosystem, lightest bundle (42KB), and free/open-source licensing.

## Architecture

- **Framework:** Leaflet.js (client-side, loaded via CDN)
- **Tile layer:** OpenStreetMap Standard (shows parks, transit, POIs, building footprints)
- **Price pill markers:** `L.divIcon` with custom CSS for price display (no clustering — individual markers)
- **Boundary overlay:** Sunnyvale city boundary from `data/sunnyvale-boundary.geojson`
- **Card-map sync:** Bidirectional — hover card highlights marker, click marker scrolls to card
- **Scroll wheel zoom:** Disabled (`scrollWheelZoom: false`) to prevent accidental zoom
- **Image fallback:** `onerror` handler for broken listing images
- **XSS prevention:** All scraped data escaped with `html.escape()` before rendering in map popups

## Current State

- **Working:** Fully operational with Leaflet.js + OpenStreetMap tiles
- **Default zoom:** Level 12 (zoomed out for wider area view)
- **Tile history:** CartoDB Positron → OpenStreetMap (2026-03-29) — OSM shows parks, transit, POIs
- **Future upgrade:** Stadia Outdoors recommended as optional tile upgrade (1-line change)
- **Clustering:** Removed (2026-04-13) — markers shown individually via `L.layerGroup`. MarkerCluster CDN removed from `base.html`. Orphaned `.cluster-icon` CSS remains for cleanup.
- **School POI overlay (2026-06-03, extended later same day to 15 schools):** 15 public elementary schools rendered as static, hover-tooltip-only 🏫 pins (24×24, Option A from UX mockup). **6 are user favorites** (Cherry Chase, Cumberland, Stocklmeir, West Valley, Montclaire, Laurelwood) — rendered in green `#16a34a` (reuses `--color-poi-park` token; see SCHOOL-P3-8 for dedicated-token formalization) with ⭐ tooltip prefix for color-independence. The other 9 are amber `#f59e0b`. Hardcoded `SCHOOLS` constant in [`map.js:50-69`](../../../../web/static/js/map.js:50) with `{name, lat, lng, isFavorite}` schema. Geocoded via [`scripts/geocode_schools.py`](../../../../scripts/geocode_schools.py) + manual fallbacks for the 6 schools Nominatim missed/mis-located. Layer is **always on, all zoom levels, no toggle, no click handler**; `zIndexOffset: -100` keeps schools beneath price pills. District polygons in `data/school-boundaries/elementary.geojson` are **not** drawn (used only for per-listing assignment lookup).
- **Favorite-school price-pill highlight (2026-06-03, dormant since 2026-06-04):** When a listing's assigned elementary school (`listing.school_elementary` after read-time `" School"` suffix strip) matches one of the 6 favorites, the price-pill marker renders in green `#15803d` with white text + ★ prefix (Option C from UX mockup). Server emits `data-fav-school="1"` on the listing card; [`map.js:277`](../../../../web/static/js/map.js:277) reads it and applies the `.price-pill-marker.is-fav-school` CSS modifier. Single source of truth: `FAVORITE_SCHOOLS` in [`web/dependencies.py:75`](../../../../web/dependencies.py:75) (NOT duplicated in JS). **DORMANT 2026-06-04** — listing-card template no longer emits the `data-fav-school` attribute when [`SCHOOLS_UI_ENABLED`](../../../../web/dependencies.py:107) is `False`, so the JS ternary always picks the non-favorite branch. CSS rule has `/* DISABLED 2026-06-04 */` marker above it but is kept (dormant). Re-enable when [`plans/school-boundaries-nces.md`](../../../../plans/school-boundaries-nces.md) ships.
- **Featured POI variant (2026-06-04):** Per-entry `featured: true` flag in [`data/interest-points.json`](../../../../data/interest-points.json) promotes a POI to a 36×36 ringed pin (vs regular 24×24 dot) with an always-shown label pill below (Option A from UX mockup). First instance: **Ortega Park** (Sunnyvale city park, OSM way `22462667`). `createPOIMarker` branches inline on `poi.featured` in [`map.js:395`](../../../../web/static/js/map.js:395). `zIndexOffset: -50` keeps featured POIs ABOVE schools (`-100`) but BELOW price pills (`0`) — price stays the dominant scanning element per Design Bible. Tooltip enriched to `"Name · Category"` for ALL POIs (both regular + featured — intentional consistency). Featured POIs are still members of their category layer group, so existing category toggles (e.g., "🌳 Parks") still control their visibility. CSS at [`style.css:1445-1517`](../../../../web/static/css/style.css:1445). No UI for toggling the flag yet (POI-P3-1 + POI-P3-2 in backlog).
- **Map makeover:** Next planned work (`plans/map-makeover-impl.md`)

## Key Files

| File | Purpose |
|------|---------|
| `web/static/js/map.js` | Leaflet.js map initialization, markers, interactions (incl. featured-POI branch in `createPOIMarker` at line 395) |
| `web/templates/dashboard.html` | Map container HTML |
| `web/static/css/style.css` | Price pill + POI + featured-POI CSS |
| `data/sunnyvale-boundary.geojson` | City boundary overlay |
| `data/interest-points.json` | User POIs (work, parks, etc.) with optional `featured: true` flag |

## History

- [2026-06-04] **Featured POI variant added (Option A)** — Ortega Park ([`data/interest-points.json`](../../../../data/interest-points.json)) shipped as first instance. `createPOIMarker` branches on `poi.featured` ([`map.js:395`](../../../../web/static/js/map.js:395)); new `.poi-marker--featured` + `.poi-featured-label` CSS ([`style.css:1445-1517`](../../../../web/static/css/style.css:1445)); `zIndexOffset: -50` (between schools and price pills); tooltip enriched to `"Name · Category"` for all POIs. Cache `style.css ?v=16 → v=17`, `map.js ?v=14 → v=15`. ✅ APPROVED (0 P1/P2). 5 P3s → backlog (POI-P3-1 through POI-P3-5). **Coord-correction note:** Code mode rejected task-brief's `37.3496/-122.0184` and used Nominatim-verified `37.3422/-122.0256` (1 km off in the brief). Reviewer independently validated.
- [2026-06-04] **Favorite-school price-pill DISABLED via natural chain** — listing-card no longer emits `data-fav-school` (parent `SCHOOLS_UI_ENABLED=False` flag). JS untouched; CSS rule kept dormant with `/* DISABLED 2026-06-04 */` marker. Cache `style.css ?v=15 → v=16`. ✅ APPROVED.
- [2026-06-03] **Favorite-school price-pill green variant added (Option C)** — `.price-pill-marker.is-fav-school` CSS modifier + JS dataset wiring; matches single source of truth in [`web/dependencies.py`](../../../../web/dependencies.py:75). Cache `style.css ?v=14 → v=15`, `map.js ?v=13 → v=14`. ✅ APPROVED (0 P1/P2).
- [2026-06-03] **School POI overlay extended 13 → 15** — Added Montclaire (Los Altos) + Laurelwood (Santa Clara). Added `isFavorite: true/false` flag, 6 favorites rendered in green `#16a34a` with ⭐ tooltip prefix. New CSS modifier `.school-poi-icon--favorite`. Geocode helper bbox widened. Cache `style.css ?v=13 → v=14`, `map.js ?v=12 → v=13`. ✅ APPROVED (0 P1/P2). 2 new P3s (SCHOOL-P3-10 geocoder unavail + SCHOOL-P3-11 ARIA double-announce) + 2 logged inline by Code mode (SCHOOL-P3-8 dedicated token + SCHOOL-P3-9 per-user favorites).
- [2026-06-03] **School POI overlay added** — Option A (Minimal POI pin) from UX mockup ([`docs/temp/mockups/school-icons-map.html`](../../../../docs/temp/mockups/school-icons-map.html)) shipped. New `SCHOOLS` const ([`map.js:21-57`](../../../../web/static/js/map.js:21)) + `.school-poi-icon` CSS ([`style.css:1396-1430`](../../../../web/static/css/style.css:1396)). CSS `?v=12→v=13`, `map.js ?v=10→v=12` across 2 review cycles (round-1 Code Reviewer flagged 4 wrong-by-1-3km coords → Code mode round-2 geocoded via [`scripts/geocode_schools.py`](../../../../scripts/geocode_schools.py)). 7 P3s → backlog. ✅ APPROVED.
- [2026-04-13] Zoom level changed from 13 → 12 (one level wider)
- [2026-04-13] Marker clustering removed — `L.markerClusterGroup` replaced with `L.layerGroup`, MarkerCluster CDN (2 CSS + 1 JS) removed from `base.html`
- [2026-03-31] School info added to map popups
- [2026-03-30] Map framework evaluation — Leaflet.js confirmed (168 points, highest score)
- [2026-03-30] Phase 1 Sprint 2: boundary overlay, card-map bidirectional sync
- [2026-03-30] Phase 1 Sprint 1: OSM tiles, price pill markers, scroll wheel zoom disabled
- [2026-03-29] Map tiles changed: CartoDB Positron → OpenStreetMap
- [2026-03-29] Map improvement UX consultation (`plans/map-improvement.md`)

## Related

- [Filter Bar](filter-bar.md) — filter changes update map markers
- [Listing Card](listing-card.md) — bidirectional sync with map markers
- [Geocoder](geocoder.md) — provides lat/lng for marker placement
- [Plan: Map Framework Evaluation](../../../../plans/map-framework-evaluation.md) — framework comparison
- [Plan: Map Makeover](../../../../plans/map-makeover-impl.md) — next planned implementation
- [Plan: Map Improvement](../../../../plans/map-improvement.md) — UX consultation
