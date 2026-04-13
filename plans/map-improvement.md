# Map Improvement Plan — Make SunnyNest Map Look Like Zillow/Google Maps

> **Type**: UX Consultation & Design Recommendations  
> **Original Date**: 2026-03-29  
> **Updated**: 2026-03-30 — Revised for FastAPI + HTMX + Leaflet.js stack  
> **Author**: UX Designer  
> **Status**: Partially implemented — see Migration Status below

---

## Migration Status

The frontend was migrated from **Streamlit + Folium** to **FastAPI + HTMX + Jinja2 + client-side Leaflet.js** on 2026-03-30. Several items from the original plan were implemented during the migration.

### ✅ Completed During Migration

| Item | Original Plan Reference | Implementation | File |
|------|------------------------|----------------|------|
| **OpenStreetMap tiles** | Phase 1 — tile swap | `L.tileLayer('https://{s}.tile.openstreetmap.org/...')` | [`map.js:29`](../web/static/js/map.js:29) |
| **Price pill markers** | Phase 2 — marker improvements | `L.divIcon` with `.price-pill` class, white bg + blue border | [`map.js:74-79`](../web/static/js/map.js:74) |
| **City boundary overlay** | Already done (kept) | `fetch('/api/boundary')` → `L.geoJSON()` with dashed blue stroke | [`map.js:37-52`](../web/static/js/map.js:37) |
| **Card→map sync (hover)** | Phase 2 — interaction gap | `mouseenter`/`mouseleave` on `.listing-card` → `.price-pill.highlighted` | [`map.js:123-148`](../web/static/js/map.js:123) |
| **Map→card sync (click)** | Phase 2 — interaction gap | `marker.on('click')` → `scrollIntoView` + `.highlighted` class | [`map.js:91-100`](../web/static/js/map.js:91) |
| **Scroll wheel zoom disabled** | Already done (kept) | `scrollWheelZoom: false` in map init options | [`map.js:26`](../web/static/js/map.js:26) |
| **HTMX-aware marker refresh** | N/A (new requirement) | `htmx:afterSwap` listener clears + re-adds markers on filter change | [`map.js:154-166`](../web/static/js/map.js:154) |
| **Hover state on pills** | Phase 2 — marker improvements | `.price-pill:hover` → blue bg, white text, `scale(1.1)` | [`style.css:590-595`](../web/static/css/style.css:590) |
| **Highlighted pill state** | Phase 2 — marker improvements | `.price-pill.highlighted` → blue bg, `scale(1.15)` | [`style.css:604-609`](../web/static/css/style.css:604) |
| **Highlighted card state** | Phase 2 — interaction gap | `.listing-card.highlighted` → blue border + shadow ring | [`style.css:598-602`](../web/static/css/style.css:598) |
| **Leaflet control styling** | N/A (new) | Custom CSS for zoom controls, attribution on light theme | [`style.css:614-636`](../web/static/css/style.css:614) |

### 🔶 Remaining (Not Yet Implemented)

| Item | Original Phase | New Effort | Priority | Notes |
|------|---------------|------------|----------|-------|
| **Marker clustering** | Phase 2 | 1–2h | P2 | `Leaflet.markercluster` plugin — straightforward with direct Leaflet |
| **Selected marker state** | Phase 2 | 0.5h | P2 | Click pill → darker blue + scale, persist until another click |
| **Layer control** | Phase 2 | 1h | P2 | `L.control.layers` — native Leaflet, no plugin needed |
| **Satellite/street toggle** | Phase 2 | 0.5h | P3 | Add satellite `TileLayer` + layer control |
| **Custom interest points (POI)** | Phase 3 | 3–5h | P3 | Direct Leaflet markers — much simpler than Folium approach |
| **Commute radius overlay** | Phase 4 | 2–4h | P4 | `L.circle()` — trivial in Leaflet |
| **Premium tiles (Stadia/Mapbox)** | Phase 5 | 1–2h | P4 | Tile URL swap + API key config |
| **Search as I move the map** | Not in original | 2–3h | P3 | Now possible: `map.on('moveend')` + HTMX request |
| **Draw boundary search** | Not in original | 3–4h | P4 | `Leaflet.draw` plugin + HTMX |
| **Better popup styling** | Phase 2 | 1h | P2 | Direct CSS — no iframe isolation |

---

## Table of Contents

1. [Current State Analysis](#1-current-state-analysis)
2. [Gap Analysis: SunnyNest vs. Zillow](#2-gap-analysis-sunnynest-vs-zillow)
3. [Tile Layer Recommendations](#3-tile-layer-recommendations)
4. [Interest Points / POI Feature UX](#4-interest-points--poi-feature-ux)
5. [Visual Elements: Adopt vs. Skip](#5-visual-elements-adopt-vs-skip)
6. [Design Bible Updates](#6-design-bible-updates)
7. [Phased Implementation Plan](#7-phased-implementation-plan)
8. [Technical Constraints & Risks](#8-technical-constraints--risks)
9. [Accessibility Considerations](#9-accessibility-considerations)
10. [New Opportunities: Leaflet.js Stack](#10-new-opportunities-leafletjs-stack)

---

## 1. Current State Analysis

### What We Have Today (Post-Migration)

| Component | Current Implementation | File Reference |
|-----------|----------------------|----------------|
| **Map library** | Leaflet.js (client-side, direct JS) | [`map.js`](../web/static/js/map.js) |
| **Rendering** | Native `<div id="map-container">` — no iframe | [`dashboard.html:79`](../web/templates/dashboard.html:79) |
| **Tile layer** | OpenStreetMap Standard — parks, transit, POIs visible | [`map.js:29`](../web/static/js/map.js:29) |
| **Markers** | `L.divIcon` price pills — white bg, blue border, dark text | [`map.js:74-79`](../web/static/js/map.js:74) |
| **Boundary** | Sunnyvale city boundary GeoJSON via `/api/boundary` | [`map.js:37-52`](../web/static/js/map.js:37) |
| **Zoom** | Scroll-wheel disabled (`scrollWheelZoom: false`) | [`map.js:26`](../web/static/js/map.js:26) |
| **Overlap handling** | ❌ None — removed during migration (was proximity-offset in Folium) | — |
| **Popups** | Basic text popup (`priceText \|\| 'Listing'`) | [`map.js:83`](../web/static/js/map.js:83) |
| **Card↔Map sync** | ✅ Bidirectional — hover card highlights pill, click pill scrolls to card | [`map.js:91-148`](../web/static/js/map.js:91) |
| **Filter refresh** | ✅ HTMX `afterSwap` clears and re-adds markers | [`map.js:154-166`](../web/static/js/map.js:154) |
| **POI layers** | ❌ None — no parks, schools, transit, or custom points | — |
| **Layer controls** | ❌ None — no toggle for layers | — |
| **Clustering** | ❌ None — planned for future sprint | — |
| **Theme** | Light tiles in light-themed UI ✅ (consistent) | [`style.css:614-636`](../web/static/css/style.css:614) |

### What OpenStreetMap Standard Shows vs. Doesn't Show

| Feature | OSM Standard (current) | Google Maps (Zillow) |
|---------|:---:|:---:|
| Street names | ✅ (clear) | ✅ (clear black) |
| Highway labels | ✅ | ✅ |
| City/neighborhood names | ✅ | ✅ |
| Parks (green areas) | ✅ | ✅ |
| Water bodies (blue) | ✅ | ✅ (clear blue) |
| Building footprints | ✅ (at high zoom) | ✅ |
| Transit stations | ✅ | ✅ |
| Points of interest | ✅ (some) | ✅ (rich) |
| Terrain/elevation | ❌ | ✅ (optional) |
| Satellite imagery | ❌ | ✅ (toggle) |
| Street-level detail | Good | Rich |

**Key improvement from original**: The "dead map" problem identified in the original plan (CartoDB Positron showing blank white space) has been **resolved** by switching to OpenStreetMap Standard. Parks, transit, and POIs are now visible.

---

## 2. Gap Analysis: SunnyNest vs. Zillow

### Visual Richness Gap (~~Critical~~ → Minor)

**Status**: Largely resolved. OpenStreetMap tiles now show parks, transit, POIs, and building footprints. The remaining gap is visual polish — Google Maps has cleaner typography and more refined styling, but the "dead map" problem is gone.

**Remaining visual gaps:**
- Google Maps has slightly more refined typography and color palette
- Google Maps shows more POI labels (restaurants, stores)
- Terrain shading is absent in OSM Standard
- Satellite toggle not yet available

### Marker Quality Gap (~~Minor~~ → Mostly Resolved)

| Aspect | Zillow | SunnyNest | Gap |
|--------|--------|-----------|-----|
| Price pills | Blue rounded rectangles | White pills with blue border | ✅ Close (different style but clean) |
| Pill shadow | Subtle drop shadow | `box-shadow: 0 2px 6px` | ✅ Good |
| Pill font | ~11px bold | 12px/700 Inter | ✅ Match |
| Selected state | Darker/larger pill | ❌ No persistent selected state | 🔶 Missing |
| Hover state | Slight scale-up | ✅ Blue bg + `scale(1.1)` | ✅ Done |
| Highlighted state | N/A | ✅ Blue bg + `scale(1.15)` on card hover | ✅ Done |
| Cluster badges | Count in circle | ❌ No clustering | 🔶 Missing |

### Interaction Gap (~~Moderate~~ → Mostly Resolved)

| Feature | Zillow | SunnyNest | Status |
|---------|--------|-----------|--------|
| Click pill → highlight card | ✅ | ✅ Scroll + highlight | ✅ Done |
| Hover card → highlight pill | ✅ | ✅ Blue bg + scale | ✅ Done |
| "Search as I move the map" | ✅ | ❌ | 🔶 Now feasible with Leaflet events + HTMX |
| Draw boundary to search | ✅ | ❌ | 🔶 Now feasible with Leaflet.draw plugin |
| Satellite/street toggle | ✅ | ❌ | 🔶 Easy — `L.control.layers` |
| Layer controls | ✅ | ❌ | 🔶 Easy — native Leaflet |
| Styled popups | ✅ | ❌ Basic text only | 🔶 Easy — direct CSS (no iframe) |

---

## 3. Tile Layer Recommendations

> **Current**: OpenStreetMap Standard (implemented in Phase 1 of original plan)

### Upgrade Path (Unchanged from Original — Still Valid)

| Phase | Tile Provider | Status | Why |
|-------|--------------|--------|-----|
| **Phase 1** ✅ | **OpenStreetMap Standard** | ✅ **DONE** | Zero-cost, shows parks/POIs, one-line change |
| **Phase 5** | **Stadia Outdoors** | Pending | Best free-tier visual quality, closest to Google Maps |
| **Optional** | **Mapbox Streets** | Pending | Premium quality, requires API key |

### Implementation Change: Leaflet.js (Not Folium)

The original plan showed Folium Python code for tile layers. With client-side Leaflet.js, tile layers are configured directly in JavaScript:

```javascript
// Current (OpenStreetMap Standard) — map.js:29
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors',
    maxZoom: 19
}).addTo(map);

// Future: Stadia Outdoors (Phase 5)
var stadiaOutdoors = L.tileLayer('https://tiles.stadiamaps.com/tiles/outdoors/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; Stadia Maps &copy; OpenMapTiles &copy; OpenStreetMap',
    maxZoom: 20
});

// Future: Satellite toggle
var satellite = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
    attribution: '&copy; Esri',
    maxZoom: 18
});

L.control.layers({
    'Street': osmLayer,
    'Outdoors': stadiaOutdoors,
    'Satellite': satellite
}).addTo(map);
```

**Advantage over Folium**: No Python re-render needed. Tile switching is instant, client-side, with zero server round-trips.

---

## 4. Interest Points / POI Feature UX

### 4.1 Feature Overview (Unchanged)

The user wants to pin custom interest points on the map:
- 🏢 Work location (commute context)
- 🏫 Schools (family context)
- 🌳 Parks (lifestyle context)
- 🚉 Transit stations (commute context)
- 🛒 Shopping/dining (convenience context)
- 📍 Custom pins (anything else)

### 4.2 POI Categories & Visual Design (Unchanged)

| Category | Icon | Color | Marker Style |
|----------|------|-------|-------------|
| 🏢 Work | Briefcase | `#6366f1` (indigo) | Filled circle with icon |
| 🏫 School | Graduation cap | `#f59e0b` (amber) | Filled circle with icon |
| 🌳 Park | Tree | `#16a34a` (green) | Filled circle with icon |
| 🚉 Transit | Train | `#8b5cf6` (purple) | Filled circle with icon |
| 🛒 Shopping | Cart | `#ec4899` (pink) | Filled circle with icon |
| 📍 Custom | Pin | `#64748b` (slate) | Filled circle with icon |

**Design rules** (unchanged):
- POI markers must be **visually distinct from price pills** — use circles with icons, not pills
- POI markers should be **smaller than price pills** (24×24px vs. 50×24px) — listings are primary
- POI markers should have a **white border** (2px) for contrast against any tile background
- Each POI category gets a **unique color** — never reuse the listing blue (`#3b82f6`)
- POI labels appear **on hover only** — keeps the map clean by default
- All POI markers must have **text labels accessible via tooltip** — never color alone (WCAG)

### 4.3 POI Marker Implementation (Updated for Leaflet.js)

```javascript
// POI marker — Leaflet.js DivIcon (direct, no Folium wrapper)
function createPOIMarker(lat, lng, category, name) {
    var colors = {
        work: '#6366f1', school: '#f59e0b', park: '#16a34a',
        transit: '#8b5cf6', shopping: '#ec4899', custom: '#64748b'
    };
    var icons = {
        work: '🏢', school: '🏫', park: '🌳',
        transit: '🚉', shopping: '🛒', custom: '📍'
    };

    var icon = L.divIcon({
        className: 'poi-marker',
        html: '<div class="poi-circle" style="background:' + colors[category] + '"'
            + ' title="' + name + '"'
            + ' aria-label="' + category + ': ' + name + '">'
            + icons[category] + '</div>',
        iconSize: [24, 24],
        iconAnchor: [12, 12]
    });

    return L.marker([lat, lng], { icon: icon })
        .bindTooltip(name, { direction: 'top', offset: [0, -14] });
}
```

```css
/* POI marker styles — add to style.css */
.poi-marker { background: transparent !important; border: none !important; }
.poi-circle {
    width: 24px; height: 24px;
    border: 2px solid white;
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 12px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.3);
    cursor: pointer;
    transition: transform 0.15s ease;
}
.poi-circle:hover { transform: scale(1.15); }
```

**Advantage over Folium**: POI markers are created and destroyed dynamically in JS. No Python re-render, no iframe isolation, direct DOM access for hover/click events.

### 4.4 Layer Control UX (Updated for Leaflet.js)

```javascript
// Native Leaflet layer control — no Folium LayerControl wrapper needed
var listingsLayer = L.layerGroup();  // all price pill markers
var boundaryLayer = L.layerGroup();  // city boundary GeoJSON
var poiLayers = {
    '🏢 Work': L.layerGroup(),
    '🏫 Schools': L.layerGroup(),
    '🌳 Parks': L.layerGroup(),
    '🚉 Transit': L.layerGroup(),
    '🛒 Shopping': L.layerGroup(),
    '📍 Custom': L.layerGroup()
};

// Base layers (tile providers)
var baseLayers = {
    'Street': osmLayer,
    'Satellite': satelliteLayer
};

// Overlay layers (toggleable)
var overlays = {
    'Listings': listingsLayer,
    'City Boundary': boundaryLayer,
    ...poiLayers
};

L.control.layers(baseLayers, overlays, { collapsed: true }).addTo(map);
```

**Advantage over Folium**: Layer control is interactive and instant. Adding/removing layers doesn't trigger a page reload. Item counts can be updated dynamically via JS.

### 4.5 Add/Edit POI Flow (Updated for FastAPI + HTMX)

#### Recommended: HTMX Form in Dashboard

With FastAPI + HTMX, we can add a collapsible POI management panel directly in the dashboard — no need for a separate backoffice page or Streamlit workarounds.

```html
<!-- Collapsible POI panel below the map -->
<details class="poi-panel">
    <summary>📍 My Interest Points</summary>
    <form hx-post="/api/poi" hx-target="#poi-list" hx-swap="innerHTML">
        <select name="category" class="filter-select" aria-label="POI category">
            <option value="work">🏢 Work</option>
            <option value="school">🏫 School</option>
            <option value="park">🌳 Park</option>
            <option value="transit">🚉 Transit</option>
            <option value="shopping">🛒 Shopping</option>
            <option value="custom">📍 Custom</option>
        </select>
        <input type="text" name="name" placeholder="Name" required aria-label="Point name">
        <input type="text" name="address" placeholder="Address" required aria-label="Address">
        <button type="submit">+ Add Point</button>
    </form>
    <div id="poi-list" aria-live="polite">
        <!-- HTMX-swapped list of saved POIs with edit/delete buttons -->
    </div>
</details>
```

**Flow:**
1. User expands the POI panel (collapsible `<details>` element)
2. Selects category, types name and address
3. HTMX `POST /api/poi` → server geocodes address → saves to DB/JSON → returns updated list
4. Client-side JS listens for `htmx:afterSwap` on `#poi-list` → adds marker to map
5. Edit/delete via inline HTMX buttons (same pattern as favorites)

**Advantages over Streamlit approach:**
- No sidebar restriction (Streamlit's `st.sidebar` was forbidden in `app.py`)
- No full-page rerender — HTMX swaps only the POI list
- Direct Leaflet marker creation — no iframe boundary
- Collapsible panel keeps the UI clean by default

#### Alternative: Backoffice Management + Dashboard Display

Still valid — manage POIs in the admin panel (`/admin/`) and display read-only on the dashboard map. This keeps the dashboard focused on browsing.

### 4.6 Commute Radius Overlay (Updated for Leaflet.js)

```javascript
// Simple radius circle — trivial in Leaflet.js
function showCommuteRadius(workLat, workLng, radiusKm) {
    var circle = L.circle([workLat, workLng], {
        radius: radiusKm * 1000,  // Leaflet uses meters
        color: '#6366f1',
        fillColor: '#6366f1',
        fillOpacity: 0.08,
        weight: 2,
        dashArray: '6, 4'
    }).addTo(map);

    // Badge listings inside radius
    markersByListingId.forEach(function(marker, id) {
        var distance = map.distance(marker.getLatLng(), L.latLng(workLat, workLng));
        if (distance <= radiusKm * 1000) {
            // Add "🏢 Near Work" badge to card
        }
    });
}
```

**Advantage over Folium**: `L.circle()` is a one-liner. Dynamic radius changes (slider) update instantly without Python re-render.

---

## 5. Visual Elements: Adopt vs. Skip

### ✅ Adopt from Zillow

| Element | Why | Effort | Status |
|---------|-----|--------|--------|
| **Rich tile layer** (parks, streets, POIs) | #1 visual gap — makes map feel alive | Low (tile swap) | ✅ **Done** |
| **Hover state on pills** | Interactive feedback | Low | ✅ **Done** |
| **Highlighted pill state** | Card-map sync feedback | Low | ✅ **Done** |
| **Card↔map bidirectional sync** | Click pill → scroll card, hover card → highlight pill | Medium | ✅ **Done** |
| **Boundary overlay** | City context | Done | ✅ **Done** |
| **Price pill markers** | Core map feature | Done | ✅ **Done** |
| **Selected marker state** | Clicking a listing should persist highlight on pill | Low (0.5h) | 🔶 Remaining |
| **Marker clustering** | When zoomed out, show cluster count badges | Medium (1–2h) | 🔶 Remaining |
| **Satellite/street toggle** | Users want to see actual terrain sometimes | Low (0.5h) | 🔶 Remaining |
| **Styled popups** | Rich popup with price, specs, image | Low (1h) | 🔶 Remaining |

### 🔶 Adapt (Don't Copy Exactly)

| Element | Zillow Does | SunnyNest Should Do | Why Different |
|---------|-------------|---------------------|---------------|
| **Map theme** | Always light (Google Maps) | Light tiles for light UI ✅ (already consistent) | Design bible: match app theme |
| **POI icons** | Google's built-in POI markers | Custom emoji-based circle markers | We can't use Google's POI rendering; emoji icons are more distinctive |
| **Search as I move** | Auto-refreshes listings on pan | ~~Manual "Search this area" button~~ → **Now feasible as auto-refresh** | Leaflet `moveend` event + HTMX makes this straightforward |
| **Draw boundary** | Freehand polygon drawing | ~~Skip for now~~ → **Feasible with Leaflet.draw plugin** | No longer blocked by Streamlit limitations |

### ❌ Skip (Not Worth the Effort)

| Element | Why Skip |
|---------|----------|
| **Google Maps branding** | Can't use Google Maps tiles legally without their SDK |
| **Street View integration** | Requires Google Maps API, not available in Leaflet |
| **3D building view** | Not supported in Leaflet |
| **Real-time traffic overlay** | Requires Google Traffic API |
| **Indoor maps** | Irrelevant for rental search |
| **Directions/routing** | Out of scope — this is a listing browser, not a navigation app |

---

## 6. Design Bible Updates

The Design Bible ([`design-bible.md`](../docs/design/design-bible.md)) was updated during the original consultation (2026-03-29) with the Map section, POI tokens, and anti-patterns. The following **additional updates** are needed for the new stack:

### Updates Needed

1. **Map section — file references**: Update from `app.py` to `web/static/js/map.js` and `web/static/css/style.css`
2. **Price pill style**: Document the current light-theme pill style (white bg + blue border, not blue bg + white text as originally planned) — this was a design decision during the light-mode migration
3. **New pattern: HTMX-aware map refresh**: Document the `htmx:afterSwap` pattern for re-syncing markers after filter changes
4. **New pattern: Layer groups**: Document the `L.layerGroup` pattern for organizing markers into toggleable layers
5. **New tokens (if POI feature is built)**:
   - `.poi-marker` — transparent background DivIcon container
   - `.poi-circle` — 24×24px circle with category color
   - `.poi-circle:hover` — scale(1.15) transform

### Price Pill Token Correction

The current implementation uses a **light pill** style (white background, dark text, blue border) rather than the **blue pill** style (blue background, white text) documented in the original plan. The Design Bible should reflect the actual implementation:

```markdown
#### Price Pill Markers (Current — Light Theme)
- Background: `#ffffff` (white)
- Text: `#1a202c` (dark), 12px, 700 weight
- Border: `1.5px solid rgba(59, 130, 246, 0.4)` (blue tint)
- Border radius: 12px
- Shadow: `0 2px 6px rgba(0, 0, 0, 0.15)`
- Hover state: `#2563eb` bg, white text, `scale(1.1)`
- Highlighted state (card hover): `#2563eb` bg, white text, `scale(1.15)`
- Selected state (planned): `#1d4ed8` bg, white text, `scale(1.1)`, z-index boost
```

---

## 7. Phased Implementation Plan (Revised)

### Phase 1: Rich Tiles — ✅ COMPLETE

**Goal**: Replace CartoDB Positron with a tile layer that shows parks, streets, and POIs.

**What was done:**
1. ✅ Switched to OpenStreetMap Standard tiles ([`map.js:29`](../web/static/js/map.js:29))
2. ✅ Map now shows parks (green), transit stations, POIs, building footprints
3. ✅ Light tiles match light UI theme (no more dark/light mismatch)

**Impact**: The "dead map" problem is resolved. Parks, streets, and transit are visible.

### Phase 2: Marker & Interaction Improvements — 🔶 PARTIALLY COMPLETE

**Goal**: Add selected/hover states, clustering, layer control, and styled popups.

**What was done:**
- ✅ Hover state on price pills (blue bg + scale)
- ✅ Highlighted state for card-map sync (bidirectional)
- ✅ Click marker → scroll to card + highlight
- ✅ Hover card → highlight marker pill
- ✅ HTMX-aware marker refresh on filter change

**What remains:**

| Item | Effort | Approach |
|------|--------|----------|
| **Selected marker state** | 0.5h | Add `.price-pill.selected` CSS class. On marker click, remove `.selected` from all pills, add to clicked pill. Persist until another marker is clicked or map is clicked. |
| **Marker clustering** | 1–2h | Add `Leaflet.markercluster` plugin via CDN. Wrap markers in `L.markerClusterGroup()` instead of adding directly to map. Style cluster icons with Inter font + brand blue. |
| **Layer control** | 1h | Wrap listings in `L.layerGroup`, boundary in `L.layerGroup`. Add `L.control.layers` with base layers (Street/Satellite) and overlays (Listings/Boundary). |
| **Satellite toggle** | 0.5h | Add Esri World Imagery or similar free satellite tile layer as base layer option. |
| **Styled popups** | 1h | Replace basic text popup with HTML popup showing: thumbnail, price (bold blue), address, beds/baths/sqft(m²), source link. Style with direct CSS (no iframe isolation). |

**Total remaining Phase 2 effort: ~4–5 hours**

**Risk**: Low — all items are straightforward with client-side Leaflet.js. No Streamlit state sync issues. No iframe CSS isolation. The `markercluster` plugin is mature and well-documented.

### Phase 3: Custom Interest Points — MVP (3–5 hours)

**Goal**: Let users add work location, schools, parks as pins on the map.

**Approach (updated for FastAPI + HTMX):**
1. Create `data/interest-points.json` schema for storing POIs (or `interest_points` SQLite table)
2. Add `POST /api/poi`, `DELETE /api/poi/{id}` FastAPI endpoints
3. Add collapsible POI panel in dashboard (HTMX form, see §4.5)
4. Geocode addresses using existing `geopy` integration
5. Render POI markers as `L.divIcon` circles with emoji icons (see §4.3)
6. Organize POI markers into `L.layerGroup` per category
7. Add POI layers to `L.control.layers` overlay section

**Impact**: Users can see listings in context of their daily life (work, schools, parks).

**Risk**: Low-Medium — geocoding reliability is the main risk. Storage is simple (JSON file or SQLite table). All map interactions are client-side Leaflet.js — no Streamlit limitations.

**Effort reduction from original**: 4–8h → 3–5h. The Folium/Streamlit workarounds (form-based entry, iframe isolation, no click-to-place) are eliminated. Direct Leaflet.js allows click-to-place POIs if desired.

### Phase 4: Commute & Radius Overlays (2–3 hours)

**Goal**: Show distance/commute context from work location.

**Approach (updated for Leaflet.js):**
1. Add `L.circle()` overlay around work location (5/10/15 km options) — one-liner in Leaflet
2. Add radius selector dropdown in POI panel (HTMX or client-side JS)
3. Filter/badge listings within radius using `map.distance()` — client-side, no server call
4. Optional: isochrone overlay using OSRM or Mapbox Isochrone API (external dependency)

**Impact**: Powerful commute-aware search — "show me rentals within 10 km of my office."

**Risk**: Low for simple radius (pure client-side). Higher for isochrone (external API dependency).

**Effort reduction from original**: 4–6h → 2–3h. `L.circle()` is trivial. Distance calculation is client-side via `map.distance()`. No Python re-render needed.

### Phase 5: Premium Tiles & Polish (1–2 hours)

**Goal**: Upgrade to Stadia or Mapbox for best visual quality.

**Approach (updated for Leaflet.js):**
1. Register for Stadia Maps free account, get API key
2. Add Stadia Outdoors as a tile layer option in `L.control.layers`
3. Add retina/HiDPI tile support (`{r}` in URL template + `detectRetina: true`)
4. Fine-tune layer control styling to match Inter font + brand colors

**Impact**: Map looks professional and polished — closest to Google Maps without using Google.

**Risk**: Low — API key management, free tier limits (200K tiles/month is plenty for single-user).

**Effort reduction from original**: 2–4h → 1–2h. Tile layer swap is a URL change in JS, not a Python code change + Streamlit rerun.

### Summary Timeline (Revised)

```
Phase 1 ──► Phase 2 ──► Phase 3 ──► Phase 4 ──► Phase 5
  ✅          ~4-5h       3-5h        2-3h        1-2h
 DONE       Markers      POIs       Commute     Premium
  
 ◄── Done ──►  ◄── Core features ──►  ◄── Polish ──►
```

**Total remaining effort**: ~10–15 hours across Phases 2–5.  
**Original total estimate**: 13–24 hours. **Savings**: ~30–40% due to Leaflet.js eliminating Streamlit/Folium workarounds.

---

## 8. Technical Constraints & Risks

### ~~Streamlit + Folium Limitations~~ → Eliminated

The original plan identified 5 major Streamlit + Folium constraints. **All are eliminated** by the migration to FastAPI + HTMX + Leaflet.js:

| Original Constraint | Status | New Reality |
|---------------------|--------|-------------|
| Map renders in iframe → limited JS interaction | ✅ **Eliminated** | Map is a native `<div>` — full JS access |
| No real-time map events → can't do "search as I move" | ✅ **Eliminated** | `map.on('moveend')` + HTMX fetch is straightforward |
| `st_folium` state sync → limited bidirectional sync | ✅ **Eliminated** | Direct JS event listeners, no state sync layer |
| No custom JS in Folium → can't add complex interactions | ✅ **Eliminated** | Full JS control — any Leaflet plugin works |
| Iframe CSS isolation → can't style map from app CSS | ✅ **Eliminated** | Map elements are in the same DOM — direct CSS styling |

### Current Technical Considerations

| Consideration | Impact | Mitigation |
|--------------|--------|------------|
| **Leaflet plugin CDN dependencies** | Clustering, draw plugins loaded from CDN | Pin versions, add `integrity` hashes, consider local copies |
| **Marker count performance** | >100 markers may slow DOM rendering | Use `markerClusterGroup` to reduce visible DOM nodes |
| **HTMX swap timing** | Markers must be re-added after HTMX swaps listing cards | Already handled via `htmx:afterSwap` listener ([`map.js:154`](../web/static/js/map.js:154)) |
| **Geocoding rate limits** | `geopy` Nominatim has 1 req/sec limit | Cache geocoded results, batch requests |
| **Mobile touch events** | Leaflet touch handling differs from desktop | Test on mobile; `scrollWheelZoom: false` already set |

### Tile Provider Considerations (Unchanged)

| Provider | Free Tier | API Key | ToS Risk |
|----------|-----------|---------|----------|
| OpenStreetMap | Unlimited (fair use) | None | ✅ Safe |
| Stadia Maps | 200K tiles/month | Required | ✅ Safe |
| Mapbox | 200K loads/month | Required | ✅ Safe |
| Esri World Imagery | Unlimited (attribution) | None | ✅ Safe |
| Google Maps tiles | N/A | N/A | ❌ ToS violation in Leaflet |

### Performance (Updated)

- Tile layers are loaded on-demand by the browser — no server-side impact
- POI markers add minimal overhead (typically <20 markers)
- Layer control toggle is client-side — no server round-trip
- Marker clustering reduces DOM nodes when zoomed out — improves performance
- **New**: HTMX partial swaps mean only listing cards are re-rendered on filter change, not the entire page. Map state (zoom, pan, layers) is preserved.

---

## 9. Accessibility Considerations

### Map Accessibility (WCAG AA) — Updated

| Requirement | Implementation | Status |
|-------------|---------------|--------|
| **Color independence** | POI markers use both color AND emoji icon — never color alone | 🔶 Planned (POI not built yet) |
| **Tooltips** | All POI markers will have `title` attribute with name and category | 🔶 Planned |
| **ARIA labels** | POI markers will include `aria-label="Category: Name"` | 🔶 Planned |
| **Keyboard navigation** | Layer control must be keyboard-accessible (Tab + Enter) | 🔶 Planned — Leaflet's native `L.control.layers` is keyboard-accessible by default |
| **Screen reader** | Map container should have `aria-label` | 🔶 Add `aria-label="Interactive map showing rental listings in Sunnyvale"` to `#map-container` |
| **Contrast** | POI marker colors all pass 3:1 contrast against white border | 🔶 Verified in original plan |
| **Text alternatives** | Listing count available as text above map | ✅ Done — `#result-count` shows count |
| **Reduced motion** | Marker animations respect `prefers-reduced-motion` | 🔶 Add `@media (prefers-reduced-motion: reduce)` to disable `.price-pill` transitions |
| **Card highlight feedback** | Highlighted card has both border color AND shadow change | ✅ Done — blue border + shadow ring |
| **Price pill text** | Price pills show text labels (not just colored dots) | ✅ Done — `$5.5K` text in each pill |

### POI Form Accessibility (Updated for HTMX)

- All form inputs have visible `<label>` elements (not just placeholders)
- Error messages associated with inputs via `aria-describedby`
- Category dropdown uses semantic `<select>` element
- Delete confirmation before removing a POI
- Focus management: after HTMX swap, focus returns to the form (use `htmx:afterSwap` + `focus()`)
- `aria-live="polite"` on `#poi-list` container for screen reader announcements

---

## 10. New Opportunities: Leaflet.js Stack

The migration to client-side Leaflet.js unlocks several features that were impossible or impractical with Streamlit + Folium:

### 10.1 Marker Clustering (`Leaflet.markercluster`)

**What**: When zoomed out, nearby markers merge into cluster badges showing count.  
**Why**: Reduces visual clutter, improves performance with many listings.  
**How**: Drop-in plugin — wrap markers in `L.markerClusterGroup()`.  
**Effort**: 1–2 hours.

```javascript
// Add via CDN in base.html
// <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css">
// <script src="https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js"></script>

var clusterGroup = L.markerClusterGroup({
    maxClusterRadius: 50,
    iconCreateFunction: function(cluster) {
        return L.divIcon({
            className: 'cluster-icon',
            html: '<span>' + cluster.getChildCount() + '</span>',
            iconSize: [36, 36]
        });
    }
});
// Add markers to clusterGroup instead of map
clusterGroup.addLayer(marker);
map.addLayer(clusterGroup);
```

### 10.2 "Search as I Move the Map"

**What**: Automatically refresh listings when the user pans/zooms the map.  
**Why**: Zillow's signature feature — users explore by moving the map.  
**How**: `map.on('moveend')` → get visible bounds → HTMX request with bounds as query params.  
**Effort**: 2–3 hours (includes debouncing, loading state, toggle).

```javascript
var searchOnMove = true;  // toggle via checkbox

map.on('moveend', function() {
    if (!searchOnMove) return;
    var bounds = map.getBounds();
    var params = new URLSearchParams({
        sw_lat: bounds.getSouthWest().lat,
        sw_lng: bounds.getSouthWest().lng,
        ne_lat: bounds.getNorthEast().lat,
        ne_lng: bounds.getNorthEast().lng
    });
    htmx.ajax('GET', '/listings?' + params.toString(), '#listing-cards');
});
```

### 10.3 Draw Boundary Search (`Leaflet.draw`)

**What**: User draws a polygon on the map → listings inside the polygon are shown.  
**Why**: Power-user feature for precise area search.  
**How**: `Leaflet.draw` plugin for drawing, `turf.js` for point-in-polygon test.  
**Effort**: 3–4 hours.

### 10.4 Layer Control (`L.control.layers`)

**What**: Toggle between base layers (Street/Satellite) and overlay layers (Listings/Boundary/POIs).  
**Why**: Standard map UX — users expect layer toggles.  
**How**: Native Leaflet — no plugin needed.  
**Effort**: 1 hour.

### 10.5 Better Popup Styling

**What**: Rich HTML popups with thumbnail, price, specs, source link.  
**Why**: Current popups are plain text. Zillow shows mini-cards in popups.  
**How**: Direct CSS styling — no iframe isolation to fight.  
**Effort**: 1 hour.

```javascript
marker.bindPopup(
    '<div class="map-popup">'
    + '<img src="' + imageUrl + '" class="popup-thumb" alt="">'
    + '<div class="popup-content">'
    + '<div class="popup-price">' + priceText + '</div>'
    + '<div class="popup-address">' + address + '</div>'
    + '<div class="popup-specs">' + beds + ' bd | ' + baths + ' ba | ' + sqft + ' sqft (' + sqm + ' m²)</div>'
    + '</div></div>',
    { maxWidth: 300, className: 'custom-popup' }
);
```

### 10.6 Geolocation ("Near Me")

**What**: Button to center map on user's current location.  
**Why**: Mobile users want to see listings near their current position.  
**How**: `map.locate()` — built into Leaflet.  
**Effort**: 0.5 hours.

### 10.7 Fullscreen Map Toggle

**What**: Button to expand map to full viewport (hide listing cards).  
**Why**: Users sometimes want to focus on the map.  
**How**: `Leaflet.fullscreen` plugin or custom CSS toggle.  
**Effort**: 0.5 hours.

### Priority Ranking of New Opportunities

| # | Feature | Effort | Impact | Priority |
|---|---------|--------|--------|----------|
| 1 | Marker clustering | 1–2h | High — reduces clutter | P2 |
| 2 | Layer control | 1h | Medium — standard UX | P2 |
| 3 | Styled popups | 1h | Medium — richer info | P2 |
| 4 | Search as I move | 2–3h | High — Zillow signature | P3 |
| 5 | Satellite toggle | 0.5h | Low — nice to have | P3 |
| 6 | Geolocation | 0.5h | Low — mobile users | P3 |
| 7 | Fullscreen toggle | 0.5h | Low — power users | P4 |
| 8 | Draw boundary search | 3–4h | Medium — power users | P4 |

---

## Appendix: Tile Layer Visual Comparison (Updated)

| Provider | Parks | Streets | Transit | POIs | Overall Feel | Status |
|----------|:-----:|:-------:|:-------:|:----:|-------------|--------|
| ~~CartoDB Positron~~ | ❌ | ✅ subtle | ❌ | ❌ | Minimal, empty | ❌ Removed |
| **OpenStreetMap Standard** | ✅ | ✅ clear | ✅ | ✅ | Busy but informative | ✅ **Current** |
| Stadia Outdoors | ✅ | ✅ clean | ✅ | ✅ | Clean and detailed | 🔶 Phase 5 |
| Stadia Alidade Smooth | ✅ | ✅ subtle | ✅ | 🔶 | Clean and modern | 🔶 Alternative |
| Mapbox Streets | ✅ | ✅ polished | ✅ | ✅ | Premium, Google-like | 🔶 Optional |
| Esri World Imagery | N/A | N/A | N/A | N/A | Satellite view | 🔶 Satellite toggle |
| Google Maps (illegal in Leaflet) | ✅ | ✅ | ✅ | ✅ | The gold standard | ❌ ToS violation |

---

## Appendix: File Reference Map (New Stack)

| Purpose | Old File (Streamlit + Folium) | New File (FastAPI + Leaflet.js) |
|---------|------------------------------|--------------------------------|
| Map initialization | `app.py:1267` | [`web/static/js/map.js`](../web/static/js/map.js) |
| Map tile layer | `app.py:1267` (Folium `tiles=`) | [`map.js:29`](../web/static/js/map.js:29) (`L.tileLayer`) |
| Price pill markers | `app.py:1409-1423` (Folium `DivIcon`) | [`map.js:74-79`](../web/static/js/map.js:74) (`L.divIcon`) |
| City boundary | `app.py:1316-1326` (Folium `GeoJson`) | [`map.js:37-52`](../web/static/js/map.js:37) (`L.geoJSON`) |
| Scroll zoom control | `app.py:1272-1312` (Folium JS injection) | [`map.js:26`](../web/static/js/map.js:26) (`scrollWheelZoom: false`) |
| Marker overlap offset | `app.py:1328-1362` (Python proximity calc) | ❌ Removed — use clustering instead |
| Map popups | `app.py:1397-1405` (Folium `Popup`) | [`map.js:83`](../web/static/js/map.js:83) (`bindPopup`) |
| Map CSS | `app.py` (injected via `st.markdown`) | [`web/static/css/style.css:570-636`](../web/static/css/style.css:570) |
| Map container | `app.py:1436` (`st_folium` iframe) | [`dashboard.html:79`](../web/templates/dashboard.html:79) (`<div id="map-container">`) |
| Card-map sync | ❌ Not implemented in Streamlit | [`map.js:91-148`](../web/static/js/map.js:91) (bidirectional) |
| Filter-aware refresh | ❌ Full page rerender in Streamlit | [`map.js:154-166`](../web/static/js/map.js:154) (`htmx:afterSwap`) |
| Design tokens | `docs/design/design-bible.md` | [`docs/design/design-bible.md`](../docs/design/design-bible.md) (unchanged location) |

---

*This document was originally a consultation (2026-03-29). Updated on 2026-03-30 to reflect the completed migration to FastAPI + HTMX + Leaflet.js. Phase 1 is complete. Phases 2–5 should follow the revised plan above.*
