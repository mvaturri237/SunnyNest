# Map View

> Leaflet.js-based interactive map with price pill markers, Sunnyvale boundary overlay, and bidirectional card-map sync.

**Status:** Active  
**Owner files:** `web/static/js/map.js`, `web/templates/dashboard.html`  
**Config:** N/A  
**Added:** 2026-03-29  
**Last updated:** 2026-04-13

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
- **Map makeover:** Next planned work (`plans/map-makeover-impl.md`)

## Key Files

| File | Purpose |
|------|---------|
| `web/static/js/map.js` | Leaflet.js map initialization, markers, interactions |
| `web/templates/dashboard.html` | Map container HTML |
| `web/static/css/style.css` | Price pill marker CSS |
| `data/sunnyvale-boundary.geojson` | City boundary overlay |

## History

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
