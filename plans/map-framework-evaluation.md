# Map Framework Evaluation — SunnyNest

> **Type**: Architecture Decision Record  
> **Date**: 2026-03-30  
> **Author**: Architect  
> **Status**: RECOMMENDATION — Awaiting product owner decision  
> **Related**: [`plans/map-makeover-impl.md`](map-makeover-impl.md) | [`plans/map-improvement.md`](map-improvement.md)  
> **Current impl**: [`web/static/js/map.js`](../web/static/js/map.js) (167 lines of Leaflet.js)  
> **Design tokens**: [`docs/design/design-bible.md`](../docs/design/design-bible.md)

---

## Executive Summary

We evaluated 6 map frameworks against 12 criteria weighted for SunnyNest's specific context: a **single-user rental listing aggregator** for Sunnyvale, CA with 20–50 listings, running on **FastAPI + HTMX + Jinja2** (no React/Vue), loaded via **CDN** (no bundler), with a **~14h implementation plan** already drafted.

**Recommendation: Stay with Leaflet.js.** It scores highest for our use case, and switching frameworks would consume 3–5h of the 14h budget on migration alone — with marginal visual improvement. The "Zillow look" comes from **tile choice + marker styling + UI polish**, not the map library.

---

## Context & Constraints

| Factor | Value | Impact on Decision |
|--------|-------|--------------------|
| Stack | FastAPI + HTMX + Jinja2 (server-rendered) | No React/Vue — eliminates React-wrapper libraries |
| Module system | CDN `<script>` tags, no bundler | Must work via CDN or single-file UMD build |
| Current code | [`map.js`](../web/static/js/map.js) — 167 lines, vanilla JS | Low migration cost FROM Leaflet, but also low sunk cost |
| Listing volume | 20–50 markers (single city) | No need for WebGL-level performance |
| User count | 1 (product owner) | No API rate-limit concerns |
| Budget | Free/open-source preferred | Eliminates paid-only options |
| Planned features | Clustering, POI pins, commute radius, satellite toggle, search-as-I-move, rich popups | All achievable with any framework |
| Design goal | "Look like Zillow" | Zillow uses Google Maps, but the look comes from custom overlays, not the base library |
| Implementation plan | ~14h across 3 sprints ([`map-makeover-impl.md`](map-makeover-impl.md)) | Already written for Leaflet — switching adds rewrite cost |

---

## Framework Profiles

### 1. Leaflet.js (Current)

| Attribute | Detail |
|-----------|--------|
| Version | 1.9.4 (loaded via CDN in [`base.html:14,28`](../web/templates/base.html:14)) |
| License | BSD-2-Clause (fully open) |
| Bundle size | ~42 KB gzipped (JS + CSS) |
| GitHub stars | ~41K |
| Last release | 2023 (stable, mature) |

**What it does well**: Lightweight, battle-tested, enormous plugin ecosystem (800+ plugins), works perfectly with vanilla JS + CDN, excellent documentation. Our existing [`map.js`](../web/static/js/map.js) already implements price pills via [`L.divIcon`](../web/static/js/map.js:74), city boundary via [`L.geoJSON`](../web/static/js/map.js:40), and bidirectional card↔map sync.

**What it lacks**: Raster-only rendering (no vector tiles natively), no smooth fractional zoom, no 3D terrain, no built-in drawing tools. Tile styling is limited to what the tile provider offers — you can't restyle tiles client-side.

**For SunnyNest**: Already working. The [`map-makeover-impl.md`](map-makeover-impl.md) plan adds clustering, POI system, satellite toggle, commute radius, and search-as-I-move — all via well-maintained plugins.

---

### 2. Mapbox GL JS

| Attribute | Detail |
|-----------|--------|
| Version | 3.x |
| License | Proprietary (Mapbox ToS) — free tier: 50K map loads/month |
| Bundle size | ~230 KB gzipped |
| GitHub stars | ~11K |
| API key | **Required** — even for the library itself |

**What it does well**: Vector tiles (client-side styling!), buttery-smooth animations, 3D terrain/buildings, Mapbox Studio for custom tile styles, built-in geocoding, excellent mobile performance.

**What it lacks**: Proprietary license (was open-source until v2), requires API key for every map load, heavier bundle, vendor lock-in to Mapbox tile services.

**For SunnyNest**: Overkill. The 50K free loads/month is generous for a single user, but the API key requirement, proprietary license, and 5.5× larger bundle don't justify the upgrade for 20–50 markers. The visual improvement comes from Mapbox Studio tile styling — but we can get similar results with free tile providers on Leaflet.

---

### 3. MapLibre GL JS

| Attribute | Detail |
|-----------|--------|
| Version | 4.x |
| License | BSD-3-Clause (fully open) |
| Bundle size | ~220 KB gzipped |
| GitHub stars | ~7K |
| API key | **Not required** for the library (tile providers may require one) |

**What it does well**: Open-source fork of Mapbox GL v1, vector tiles, smooth animations, client-side tile styling, growing ecosystem, no vendor lock-in. Can use free vector tile providers (MapTiler free tier, Protomaps, self-hosted).

**What it lacks**: Smaller plugin ecosystem than Leaflet, fewer Stack Overflow answers, some Mapbox GL plugins need porting, slightly steeper learning curve for style specs.

**For SunnyNest**: The strongest alternative to Leaflet. Vector tiles enable dark mode tile switching without changing providers, and the smooth zoom is noticeably better. However, the 5× larger bundle, need to learn the Mapbox Style Spec, and rewrite of all 167 lines of [`map.js`](../web/static/js/map.js) make it a significant investment. Clustering requires `supercluster` (separate library) instead of the drop-in `Leaflet.markercluster` plugin.

---

### 4. Google Maps JavaScript API

| Attribute | Detail |
|-----------|--------|
| Version | Weekly channel |
| License | Proprietary (Google ToS) |
| Bundle size | ~150 KB (loaded from Google CDN, not self-hostable) |
| API key | **Required** — billing account mandatory (even for free tier) |
| Free tier | $200/month credit (~28K map loads) |

**What it does well**: The gold standard for map UX — this is what Zillow, Redfin, and Realtor.com use. Best geocoding, best Street View, best satellite imagery, best mobile gestures, best accessibility. `AdvancedMarkerElement` supports fully custom HTML markers (like our price pills). Built-in clustering via `@googlemaps/markerclusterer`.

**What it lacks**: Requires billing account (credit card), proprietary, no self-hosting, no offline support, no custom tile styling (limited to Cloud-based Map Styling), heavier than Leaflet.

**For SunnyNest**: Would give us the closest Zillow look, but requires a Google Cloud billing account, API key management, and compliance with Google's ToS (attribution requirements, usage limits). For a single-user tool, the overhead of managing a Google Cloud project isn't justified. The visual gap between Google Maps and Leaflet+OSM is smaller than people think — it's the **overlay UI** (price pills, popups, filters) that makes Zillow look like Zillow, not the base map.

---

### 5. OpenLayers

| Attribute | Detail |
|-----------|--------|
| Version | 9.x |
| License | BSD-2-Clause (fully open) |
| Bundle size | ~160 KB gzipped (full build) |
| GitHub stars | ~11K |
| API key | Not required |

**What it does well**: Enterprise-grade, supports every projection/coordinate system, vector tiles, WMS/WFS/WMTS, drawing tools, measurement tools, print layouts. Used by government/GIS applications.

**What it lacks**: Steepest learning curve of all options, verbose API, smaller community for web-app use cases (most users are GIS professionals), fewer "pretty" examples, heavier than Leaflet.

**For SunnyNest**: Massive overkill. OpenLayers is designed for GIS applications that need multiple projections, WMS layers, and measurement tools. Our use case (show 20–50 rental markers on a city map) doesn't need any of these capabilities. The learning curve would slow development significantly.

---

### 6. Deck.gl

| Attribute | Detail |
|-----------|--------|
| Version | 9.x |
| License | MIT (fully open) |
| Bundle size | ~300 KB gzipped (core + layers) |
| GitHub stars | ~12K |
| API key | Not required (but typically used with Mapbox/MapLibre as base map) |

**What it does well**: WebGL-powered data visualization, handles millions of data points, beautiful heatmaps/arcs/hexbins, 3D visualization, excellent for large-scale geospatial analytics.

**What it lacks**: Designed for React (vanilla JS usage is possible but awkward), requires a base map library (Mapbox GL or MapLibre), no built-in UI controls (popups, layer control), massive bundle, steep learning curve.

**For SunnyNest**: Wrong tool entirely. Deck.gl is for visualizing large datasets (100K+ points) with WebGL. We have 20–50 markers. Using Deck.gl would be like using a fire hose to water a houseplant. The React-centric API also conflicts with our HTMX + vanilla JS stack.

---

## Scored Comparison

### Scoring Method

Each criterion is scored 1–5 (5 = best) and weighted by importance to SunnyNest's specific use case. Weights reflect our constraints: single user, 20–50 listings, CDN-loaded, no bundler, vanilla JS, free/open-source preference.

| Criterion | Weight | Leaflet | Mapbox GL | MapLibre GL | Google Maps | OpenLayers | Deck.gl |
|-----------|--------|---------|-----------|-------------|-------------|------------|---------|
| **Visual quality** | 3 | 3 | 5 | 5 | 5 | 3 | 4 |
| **Tile provider flexibility** | 3 | 5 | 2 | 4 | 2 | 5 | 2 |
| **Marker customization** | 4 | 5 | 4 | 4 | 5 | 4 | 3 |
| **Performance (20–50 markers)** | 2 | 5 | 5 | 5 | 5 | 5 | 5 |
| **Plugin ecosystem** | 4 | 5 | 4 | 3 | 4 | 3 | 2 |
| **Bundle size / CDN** | 3 | 5 | 2 | 2 | 3 | 3 | 1 |
| **Learning curve** | 4 | 5 | 3 | 3 | 4 | 2 | 1 |
| **Cost** | 3 | 5 | 3 | 5 | 2 | 5 | 5 |
| **Dark mode support** | 2 | 3 | 5 | 5 | 4 | 3 | 4 |
| **Mobile/touch** | 2 | 4 | 5 | 5 | 5 | 4 | 3 |
| **Community & docs** | 2 | 5 | 4 | 3 | 5 | 3 | 3 |
| **Our specific features** ¹ | 4 | 5 | 4 | 4 | 5 | 3 | 2 |

> ¹ POI markers, commute radius, search-as-I-move, satellite toggle, card↔map sync, clustering

### Weighted Scores

| Framework | Raw Score | Weighted Score | Rank |
|-----------|-----------|----------------|------|
| **Leaflet.js** | 55 | **168** | 🥇 **1st** |
| **Google Maps** | 49 | 147 | 🥈 2nd |
| **MapLibre GL JS** | 48 | 143 | 🥉 3rd |
| **Mapbox GL JS** | 46 | 134 | 4th |
| **OpenLayers** | 43 | 127 | 5th |
| **Deck.gl** | 35 | 104 | 6th |

---

## Detailed Criterion Analysis

### Visual Quality (Weight: 3)

The "Zillow look" is composed of three layers:

1. **Base map tiles** — Zillow uses Google Maps tiles. We use OSM. The difference is noticeable but not dramatic for a city-level view.
2. **Custom overlays** — Price pills, POI circles, boundary lines, popups. **This is framework-agnostic** — all frameworks support custom HTML overlays.
3. **Smooth interactions** — Vector tile frameworks (Mapbox/MapLibre) have smoother fractional zoom and rotation. Leaflet's raster zoom is slightly "snappier" (tiles reload at each zoom level).

**Verdict**: The visual gap between Leaflet+OSM and Google Maps is ~20% — and most of that 20% is tile aesthetics, not framework capability. Switching to MapLibre would close ~10% of the gap (smoother zoom), but the remaining 10% (tile quality) depends on the tile provider, not the library.

| Framework | Score | Notes |
|-----------|-------|-------|
| Leaflet | 3 | Raster tiles, snappy zoom, but our price pills + boundary already look great |
| Mapbox GL | 5 | Vector tiles, smooth zoom, 3D buildings, Mapbox Studio styling |
| MapLibre GL | 5 | Same rendering as Mapbox GL, free vector tile providers available |
| Google Maps | 5 | Best satellite imagery, smoothest UX, what users expect |
| OpenLayers | 3 | Can render vector tiles but default examples look dated |
| Deck.gl | 4 | Beautiful WebGL rendering but for data viz, not standard maps |

### Tile Provider Flexibility (Weight: 3)

| Framework | Score | Notes |
|-----------|-------|-------|
| Leaflet | 5 | Any raster tile URL works: OSM, Stadia, Mapbox raster, ESRI, Thunderforest, custom |
| Mapbox GL | 2 | Locked to Mapbox vector tiles (ToS prohibits using other providers with Mapbox GL) |
| MapLibre GL | 4 | Any vector tile source (MapTiler, Protomaps, self-hosted), plus raster fallback |
| Google Maps | 2 | Google tiles only (can overlay custom tiles but base is always Google) |
| OpenLayers | 5 | Everything: raster, vector, WMS, WMTS, any provider |
| Deck.gl | 2 | Needs a base map library; tile flexibility depends on that library |

### Marker Customization (Weight: 4)

This is critical for SunnyNest — our price pills ([`L.divIcon`](../web/static/js/map.js:74)) and planned POI circles are the most visible map elements.

| Framework | Score | Notes |
|-----------|-------|-------|
| Leaflet | 5 | [`L.divIcon`](../web/static/js/map.js:74) = arbitrary HTML/CSS. Already working beautifully for price pills. |
| Mapbox GL | 4 | Custom HTML markers via `Marker` class, but symbol layers use sprite sheets (less flexible) |
| MapLibre GL | 4 | Same as Mapbox GL — HTML markers work, symbol layers need sprites |
| Google Maps | 5 | `AdvancedMarkerElement` supports full HTML content, excellent clustering |
| OpenLayers | 4 | `ol/Overlay` for HTML markers, `ol/style/Style` for canvas-rendered markers |
| Deck.gl | 3 | `IconLayer` / `TextLayer` — powerful but requires WebGL thinking, no HTML markers |

### Performance at 20–50 Markers (Weight: 2)

Low weight because **all frameworks handle 50 markers effortlessly**. This would matter at 10K+ markers.

| Framework | Score | Notes |
|-----------|-------|-------|
| All | 5 | 50 markers is trivial for any framework. Even 500 would be fine. |

### Plugin Ecosystem (Weight: 4)

High weight because our planned features (clustering, commute radius, search-as-I-move) rely on plugins.

| Framework | Score | Clustering | Drawing/Radius | Geocoding |
|-----------|-------|------------|----------------|-----------|
| Leaflet | 5 | `Leaflet.markercluster` (drop-in) | `Leaflet.draw`, `L.circle` | `leaflet-control-geocoder` |
| Mapbox GL | 4 | Built-in `cluster` source | `@mapbox/mapbox-gl-draw` | Built-in geocoding API |
| MapLibre GL | 3 | `supercluster` (manual integration) | `@mapbox/mapbox-gl-draw` (needs fork) | No built-in, use external |
| Google Maps | 4 | `@googlemaps/markerclusterer` | `google.maps.Circle`, Drawing Manager | Built-in Geocoding API |
| OpenLayers | 3 | `ol/source/Cluster` (basic) | `ol/interaction/Draw` | No built-in |
| Deck.gl | 2 | Manual via `supercluster` | Manual WebGL layers | No built-in |

### Bundle Size / CDN Availability (Weight: 3)

We load everything via CDN in [`base.html`](../web/templates/base.html) — no webpack/vite/rollup. Size directly impacts page load.

| Framework | Size (gzipped) | CDN? | Score |
|-----------|---------------|------|-------|
| Leaflet | ~42 KB | ✅ unpkg, cdnjs | 5 |
| Mapbox GL | ~230 KB | ✅ Mapbox CDN | 2 |
| MapLibre GL | ~220 KB | ✅ unpkg | 2 |
| Google Maps | ~150 KB | ✅ Google CDN (async) | 3 |
| OpenLayers | ~160 KB | ⚠️ Full build only; tree-shaking needs bundler | 3 |
| Deck.gl | ~300 KB+ | ⚠️ Needs bundler for reasonable size | 1 |

### Learning Curve (Weight: 4)

High weight because we have a ~14h implementation budget and no bundler setup.

| Framework | Score | Notes |
|-----------|-------|-------|
| Leaflet | 5 | We already know it. [`map.js`](../web/static/js/map.js) is working. Zero ramp-up. |
| Mapbox GL | 3 | Different API paradigm (style spec, sources, layers). Need to learn Mapbox Studio. |
| MapLibre GL | 3 | Same API as Mapbox GL. Style spec is powerful but verbose. |
| Google Maps | 4 | Well-documented, familiar API. But need Google Cloud Console setup. |
| OpenLayers | 2 | Verbose, GIS-oriented API. `ol/Map`, `ol/View`, `ol/layer/Tile` — more boilerplate. |
| Deck.gl | 1 | WebGL concepts, layer composition, React-centric docs. Steep curve for vanilla JS. |

### Cost (Weight: 3)

| Framework | Score | Free Tier | Gotchas |
|-----------|-------|-----------|---------|
| Leaflet | 5 | Fully free + open source | Tile providers may have limits (OSM: fair use policy) |
| Mapbox GL | 3 | 50K loads/month free | API key required, proprietary license, overage charges |
| MapLibre GL | 5 | Fully free + open source | Vector tile providers may have limits (MapTiler: 100K free) |
| Google Maps | 2 | $200/month credit (~28K loads) | Billing account + credit card required, overage at $7/1K loads |
| OpenLayers | 5 | Fully free + open source | Same tile provider considerations as Leaflet |
| Deck.gl | 5 | Fully free + open source | Needs base map library (adds that library's cost) |

### Dark Mode Support (Weight: 2)

Lower weight because we're currently on light theme and dark mode is not planned near-term.

| Framework | Score | Notes |
|-----------|-------|-------|
| Leaflet | 3 | Swap tile URL to dark provider (Stadia Dark, CartoDB Dark Matter). Works but abrupt. |
| Mapbox GL | 5 | Change style JSON — tiles re-render client-side. Smooth transition possible. |
| MapLibre GL | 5 | Same as Mapbox GL — client-side style switching. |
| Google Maps | 4 | Cloud-based Map Styling — define dark style in console, apply via map ID. |
| OpenLayers | 3 | Same as Leaflet — swap tile URL. |
| Deck.gl | 4 | Depends on base map library. |

### Mobile/Touch (Weight: 2)

Lower weight because this is primarily a desktop tool for a single user.

| Framework | Score | Notes |
|-----------|-------|-------|
| Leaflet | 4 | Good touch support, pinch-to-zoom, but no inertial panning by default |
| Mapbox GL | 5 | Excellent — inertial panning, smooth pinch-zoom, rotation gestures |
| MapLibre GL | 5 | Same as Mapbox GL |
| Google Maps | 5 | Best-in-class mobile UX |
| OpenLayers | 4 | Adequate touch support |
| Deck.gl | 3 | Touch support depends on base map; Deck.gl layers can interfere |

### Community & Docs (Weight: 2)

| Framework | Stars | SO Questions | Score |
|-----------|-------|-------------|-------|
| Leaflet | ~41K | ~25K | 5 |
| Mapbox GL | ~11K | ~8K | 4 |
| MapLibre GL | ~7K | ~2K | 3 |
| Google Maps | N/A | ~100K+ | 5 |
| OpenLayers | ~11K | ~12K | 3 |
| Deck.gl | ~12K | ~1K | 3 |

### Our Specific Features (Weight: 4)

How well does each framework support the features in [`map-makeover-impl.md`](map-makeover-impl.md)?

| Feature | Leaflet | Mapbox GL | MapLibre GL | Google Maps | OpenLayers | Deck.gl |
|---------|---------|-----------|-------------|-------------|------------|---------|
| Price pill markers | ✅ Working | ✅ HTML Marker | ✅ HTML Marker | ✅ AdvancedMarker | ⚠️ ol/Overlay | ❌ No HTML |
| POI circle markers | ✅ `L.circleMarker` | ✅ Circle layer | ✅ Circle layer | ✅ `google.maps.Circle` | ✅ `ol/geom/Circle` | ✅ ScatterplotLayer |
| Marker clustering | ✅ Plugin (drop-in) | ✅ Built-in source | ⚠️ Manual supercluster | ✅ Library | ⚠️ Basic built-in | ⚠️ Manual |
| Commute radius | ✅ `L.circle` | ✅ Circle layer | ✅ Circle layer | ✅ `google.maps.Circle` | ✅ `ol/geom/Circle` | ✅ ScatterplotLayer |
| Satellite toggle | ✅ Layer control | ✅ Style switch | ✅ Style switch | ✅ Map type control | ✅ Layer switch | ⚠️ Base map dependent |
| Search-as-I-move | ✅ `moveend` event | ✅ `moveend` event | ✅ `moveend` event | ✅ `idle` event | ✅ `moveend` event | ⚠️ Complex |
| Card↔map sync | ✅ Working | ✅ Marker events | ✅ Marker events | ✅ Marker events | ✅ Overlay events | ❌ Difficult |
| Rich popups | ✅ `L.popup` (HTML) | ✅ `Popup` (HTML) | ✅ `Popup` (HTML) | ✅ `InfoWindow` | ⚠️ `ol/Overlay` | ❌ No built-in |
| City boundary | ✅ Working | ✅ GeoJSON source | ✅ GeoJSON source | ✅ `Data` layer | ✅ `ol/format/GeoJSON` | ✅ GeoJsonLayer |

| Framework | Score | Notes |
|-----------|-------|-------|
| Leaflet | 5 | All features supported, most already implemented or have drop-in plugins |
| Mapbox GL | 4 | All features supported but requires API key + rewrite |
| MapLibre GL | 4 | All features supported but clustering needs manual work |
| Google Maps | 5 | All features supported with excellent APIs, but requires billing account |
| OpenLayers | 3 | All features possible but more verbose, fewer ready-made examples |
| Deck.gl | 2 | Missing HTML markers, popups, and card sync — wrong paradigm |

---

## Migration Cost Analysis

If we were to switch from Leaflet, here's what it would cost:

| Task | Leaflet (stay) | MapLibre GL | Google Maps | Mapbox GL |
|------|---------------|-------------|-------------|-----------|
| Rewrite [`map.js`](../web/static/js/map.js) (167 lines) | 0h | 3–4h | 2–3h | 3–4h |
| Update [`base.html`](../web/templates/base.html) CDN links | 0h | 0.5h | 0.5h | 0.5h |
| Update [`style.css`](../web/static/css/style.css) marker styles | 0h | 1–2h | 1h | 1–2h |
| Learn new API / setup account | 0h | 1–2h | 1–2h | 1–2h |
| Rewrite [`map-makeover-impl.md`](map-makeover-impl.md) plan | 0h | 2–3h | 2–3h | 2–3h |
| **Total migration overhead** | **0h** | **7–11h** | **6–9h** | **7–11h** |
| **Remaining for new features** | **14h** | **3–7h** | **5–8h** | **3–7h** |

The ~14h implementation plan in [`map-makeover-impl.md`](map-makeover-impl.md) is already written for Leaflet. Switching frameworks would consume **50–80% of the budget** on migration, leaving little time for the actual features (clustering, POIs, commute radius, satellite toggle, search-as-I-move).

---

## The "Zillow Look" — What Actually Matters

People often attribute Zillow's polished map experience to Google Maps, but the "Zillow look" is actually composed of:

| Layer | Contribution to "Zillow feel" | Framework-dependent? |
|-------|-------------------------------|---------------------|
| **Price pill markers** | 40% | ❌ No — CSS-styled HTML overlays work on any framework. We already have these. |
| **Rich popups** (thumbnail, specs, CTA) | 20% | ❌ No — HTML popups work on any framework. Planned in Sprint 1. |
| **Smooth interactions** (hover sync, selected state) | 15% | ❌ No — JS event handlers. We already have hover sync. |
| **Tile quality** (Google's tiles vs. OSM) | 15% | ⚠️ Partially — Google tiles are slightly better, but Stadia/MapTiler tiles are very close. |
| **Smooth zoom/pan** (vector vs. raster) | 10% | ✅ Yes — vector tile frameworks (MapLibre/Mapbox) are smoother. |

**75% of the Zillow look is framework-agnostic.** We already have price pills and hover sync. Adding rich popups, selected states, and clustering (all in the existing plan) will close most of the remaining gap.

---

## Recommendation

### 🏆 Stay with Leaflet.js

**Confidence: High (8/10)**

| Reason | Detail |
|--------|--------|
| **Already working** | 167 lines of production code with price pills, boundary, card↔map sync |
| **Zero migration cost** | 14h budget goes entirely to new features |
| **Best plugin ecosystem** | `Leaflet.markercluster` is a drop-in; `L.circle` for commute radius; layer control built-in |
| **Lightest bundle** | 42 KB vs. 150–300 KB for alternatives |
| **CDN-friendly** | No bundler needed — matches our HTMX + vanilla JS stack |
| **Free & open** | No API keys, no billing accounts, no usage limits |
| **Sufficient visual quality** | Price pills + rich popups + clustering = 90% of the Zillow look |

### When to Reconsider

Switch to **MapLibre GL JS** if any of these become true:

- [ ] We need **dark mode tile switching** without page reload (MapLibre can restyle tiles client-side)
- [ ] We scale to **500+ markers** and need WebGL rendering performance
- [ ] We want **3D building extrusions** or terrain visualization
- [ ] We add a **bundler** (Vite/webpack) to the project, eliminating the bundle size concern
- [ ] The product owner finds the **raster tile zoom** (slight flicker between zoom levels) unacceptable

### What NOT to Switch To

| Framework | Why Not |
|-----------|---------|
| **Mapbox GL JS** | Proprietary license, API key required, vendor lock-in. If we want vector tiles, MapLibre is the open-source equivalent. |
| **Google Maps** | Requires billing account, credit card, API key management. Overkill for single-user tool. |
| **OpenLayers** | Enterprise GIS tool. Wrong abstraction level for a rental listing map. |
| **Deck.gl** | Data visualization library, not a map framework. Wrong tool entirely. |

---

## Tile Provider Upgrade (Optional, Framework-Independent)

Regardless of framework choice, we can improve tile quality by switching from OSM Standard to a premium free-tier provider. This is a **1-line change** in [`map.js:29`](../web/static/js/map.js:29):

| Provider | Look | Free Tier | Dark Mode Variant | Change Required |
|----------|------|-----------|-------------------|-----------------|
| **OSM Standard** (current) | Good — parks, transit, POIs | Unlimited (fair use) | ❌ None | None |
| **Stadia Outdoors** | Better — cleaner labels, terrain shading | 200K tiles/day | ✅ Stadia Alidade Smooth Dark | Swap tile URL, add API key |
| **MapTiler Streets** | Best — vector-quality raster, clean design | 100K tiles/month | ✅ MapTiler Dark | Swap tile URL, add API key |
| **ESRI World Street Map** | Good — detailed, professional | Unlimited (attribution) | ❌ None | Swap tile URL |

**Recommendation**: Stay with OSM Standard for now. Consider Stadia Outdoors in Sprint 3 when we add the satellite toggle (we'll already be setting up layer switching).

---

## Decision Record

| Question | Answer |
|----------|--------|
| **Should we switch map frameworks?** | **No** — stay with Leaflet.js |
| **Why?** | Best score for our constraints (CDN, no bundler, vanilla JS, 20–50 markers, free, 14h budget) |
| **What's the risk of staying?** | Low — Leaflet is mature, well-maintained, and handles our scale easily |
| **What would change our mind?** | Need for vector tiles, 500+ markers, 3D terrain, or dark mode tile switching |
| **Next step** | Proceed with [`map-makeover-impl.md`](map-makeover-impl.md) Sprint 1 (clustering, selected state, layer control, rich popups) |

---

*This evaluation is specific to SunnyNest's constraints as of 2026-03-30. If the project scales to multiple cities, public users, or adds a bundler, re-evaluate MapLibre GL JS.*
