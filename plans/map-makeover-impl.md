# Map Makeover — Implementation Plan

> **Type**: Engineering Implementation Plan  
> **Date**: 2026-03-30  
> **Author**: Architect  
> **Status**: DRAFT — Awaiting product owner approval  
> **UX Specs**: [`plans/map-improvement.md`](map-improvement.md)  
> **Design Tokens**: [`docs/design/design-bible.md`](../docs/design/design-bible.md)  
> **Estimated Total Effort**: ~14 hours across 3 sprints

---

## Executive Summary

This plan turns the remaining UX specs from [`plans/map-improvement.md`](map-improvement.md) into concrete, implementable tasks organized into 3 sprints. Each task specifies exact files, code patterns, dependencies, acceptance criteria, and effort estimates.

### Current State

The map already has: OSM tiles, price pill markers (`L.divIcon`), city boundary overlay, bidirectional card↔map sync (hover + click), HTMX-aware marker refresh, and light-theme styling. See [`map.js`](../web/static/js/map.js) (167 lines) and [`style.css:568-636`](../web/static/css/style.css:568).

### What This Plan Adds

| Sprint | Theme | Items | Effort |
|--------|-------|-------|--------|
| **Sprint 1** | Map Polish (P2) | Marker clustering, selected state, layer control, rich popups | ~4h |
| **Sprint 2** | POI System + Workplace Pin (P3) | POI storage, API, markers, management UI, Palo Alto Networks pin | ~5h |
| **Sprint 3** | Advanced Features (P3-P4) | Satellite toggle, commute radius, search-as-I-move, premium tiles | ~5h |

---

## Sprint 1: Map Polish (P2 — ~4h)

### 1.1 Marker Clustering

**Goal**: When zoomed out, nearby price pills merge into cluster badges showing a count.

**Files to modify**:
- [`web/templates/base.html`](../web/templates/base.html) — add MarkerCluster CDN assets (CSS + JS)
- [`web/static/js/map.js`](../web/static/js/map.js) — wrap markers in `L.markerClusterGroup()`
- [`web/static/css/style.css`](../web/static/css/style.css) — add `.cluster-icon` styles

**Technical approach**:

1. **CDN assets** — Add to [`base.html`](../web/templates/base.html) after the Leaflet CSS/JS:
   ```html
   <!-- MarkerCluster CSS (after Leaflet CSS, line 16) -->
   <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css">
   <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css">
   
   <!-- MarkerCluster JS (after Leaflet JS, line 30) -->
   <script src="https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js"></script>
   ```

2. **Cluster group** — In [`map.js`](../web/static/js/map.js), create a `L.markerClusterGroup` and add markers to it instead of directly to the map:
   ```javascript
   // Replace: marker.addTo(map)  →  clusterGroup.addLayer(marker)
   var clusterGroup = L.markerClusterGroup({
       maxClusterRadius: 50,
       showCoverageOnHover: false,
       iconCreateFunction: function(cluster) {
           return L.divIcon({
               className: 'cluster-icon',
               html: '<span>' + cluster.getChildCount() + '</span>',
               iconSize: [36, 36]
           });
       }
   });
   ```

3. **Cluster styles** — Add to [`style.css`](../web/static/css/style.css) after the price pill section (~line 609):
   ```css
   .cluster-icon {
       background: #2563eb;
       color: white;
       border-radius: 50%;
       font-size: 13px;
       font-weight: 700;
       font-family: 'Inter', sans-serif;
       display: flex;
       align-items: center;
       justify-content: center;
       box-shadow: 0 2px 6px rgba(0, 0, 0, 0.25);
       border: 2px solid white;
   }
   ```

4. **HTMX refresh** — Update the `htmx:afterSwap` handler in [`map.js:154-166`](../web/static/js/map.js:154) to clear and re-add the cluster group instead of removing individual markers:
   ```javascript
   // Clear: clusterGroup.clearLayers() instead of map.eachLayer removal
   // Re-add: addMarkers() adds to clusterGroup, then map.addLayer(clusterGroup)
   ```

**Dependencies**: None — first task in sprint.

**Acceptance criteria**:
- [ ] Zooming out to level 11 or below merges nearby markers into blue circle badges with count
- [ ] Clicking a cluster zooms in to reveal individual markers
- [ ] Cluster badges use Inter font, brand blue (`#2563eb`), white text, white border
- [ ] HTMX filter changes correctly clear and re-populate clusters
- [ ] No visual regression on individual price pills at zoom level 13+

**Effort**: 1.5h

---

### 1.2 Selected Marker State

**Goal**: Clicking a price pill gives it a persistent "selected" style (darker blue + scale) until another pill is clicked.

**Files to modify**:
- [`web/static/js/map.js`](../web/static/js/map.js) — add selected state logic in marker click handler
- [`web/static/css/style.css`](../web/static/css/style.css) — add `.price-pill.selected` class

**Technical approach**:

1. **CSS class** — Add to [`style.css`](../web/static/css/style.css) after `.price-pill.highlighted` (~line 609):
   ```css
   .price-pill.selected {
       background: #1d4ed8 !important;
       color: white !important;
       border-color: #1e40af !important;
       transform: scale(1.1);
       z-index: 1000 !important;
   }
   ```

2. **Click handler** — In [`map.js`](../web/static/js/map.js), modify the existing `marker.on('click')` handler (~line 91) to:
   - Remove `.selected` from all pills: `document.querySelectorAll('.price-pill.selected').forEach(p => p.classList.remove('selected'))`
   - Add `.selected` to the clicked pill: `marker.getElement().querySelector('.price-pill').classList.add('selected')`
   - Keep the existing scroll-to-card + highlight behavior

3. **Deselect on map click** — Add `map.on('click', ...)` to remove `.selected` from all pills when clicking empty map area.

**Dependencies**: None (can be done in parallel with 1.1).

**Acceptance criteria**:
- [ ] Clicking a price pill turns it darker blue (`#1d4ed8`) with `scale(1.1)`
- [ ] Selected state persists until another pill is clicked
- [ ] Clicking empty map area deselects the current pill
- [ ] Selected state is visually distinct from hover state (darker blue vs. regular blue)
- [ ] Card scroll + highlight still works on marker click

**Effort**: 0.5h

---

### 1.3 Layer Control

**Goal**: Add a Leaflet layer control for toggling base layers and overlay layers.

**Files to modify**:
- [`web/static/js/map.js`](../web/static/js/map.js) — refactor tile layer and markers into named layer groups, add `L.control.layers`
- [`web/static/css/style.css`](../web/static/css/style.css) — style the layer control to match the design system

**Technical approach**:

1. **Refactor tile layer** — In [`map.js`](../web/static/js/map.js), assign the OSM tile layer to a variable instead of chaining `.addTo(map)`:
   ```javascript
   var osmLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
       attribution: '&copy; OpenStreetMap contributors',
       maxZoom: 19
   }).addTo(map);
   ```

2. **Wrap markers in layer group** — The `clusterGroup` from task 1.1 already serves as the listings layer group. Wrap the boundary in its own layer group:
   ```javascript
   var boundaryLayer = L.layerGroup().addTo(map);
   // In the fetch callback: L.geoJSON(...).addTo(boundaryLayer)
   ```

3. **Add layer control** — After all layers are defined:
   ```javascript
   var baseLayers = { 'Street': osmLayer };
   var overlays = {
       'Listings': clusterGroup,
       'City Boundary': boundaryLayer
   };
   L.control.layers(baseLayers, overlays, { collapsed: true, position: 'topright' }).addTo(map);
   ```
   POI layers will be added to this control in Sprint 2.

4. **Style the control** — Add to [`style.css`](../web/static/css/style.css):
   ```css
   .leaflet-control-layers {
       font-family: 'Inter', sans-serif;
       font-size: 13px;
       border-radius: 8px !important;
       box-shadow: 0 2px 8px rgba(0,0,0,0.12) !important;
   }
   .leaflet-control-layers-toggle {
       width: 36px !important;
       height: 36px !important;
   }
   ```

**Dependencies**: Task 1.1 (cluster group must exist for the overlays object).

**Acceptance criteria**:
- [ ] Layer control icon appears in top-right corner of map
- [ ] Expanding the control shows "Street" base layer and "Listings" / "City Boundary" overlays
- [ ] Toggling "Listings" off hides all price pills; toggling back on restores them
- [ ] Toggling "City Boundary" off hides the dashed blue boundary
- [ ] Layer control uses Inter font, 8px border-radius, matches design system
- [ ] Layer control is keyboard-accessible (Tab + Enter)

**Effort**: 1h

---

### 1.4 Better Popup Styling

**Goal**: Replace the plain text popup with a rich mini-card showing image, price, specs, and source link.

**Files to modify**:
- [`web/static/js/map.js`](../web/static/js/map.js) — build rich HTML popup content from card data attributes
- [`web/static/css/style.css`](../web/static/css/style.css) — add `.map-popup` and `.custom-popup` styles
- [`web/templates/partials/listing-card.html`](../web/templates/partials/listing-card.html) — add `data-*` attributes for popup data

**Technical approach**:

1. **Add data attributes to cards** — In [`listing-card.html`](../web/templates/partials/listing-card.html), add data attributes to the `.listing-card` div for popup content:
   ```html
   <div class="listing-card" data-id="{{ listing.id }}"
        data-lat="{{ listing.latitude }}" data-lng="{{ listing.longitude }}"
        data-price="{{ listing.price }}"
        data-address="{{ listing.address or '' }}"
        data-beds="{{ listing.bedrooms or '' }}"
        data-baths="{{ listing.bathrooms or '' }}"
        data-sqft="{{ listing.sqft or '' }}"
        data-sqm="{{ listing.sqm|int if listing.sqm else '' }}"
        data-img="{{ listing.image_urls | first_image or '' }}"
        data-url="{{ listing.url or '' }}"
        data-source="{{ listing.source or '' }}">
   ```

2. **Build rich popup** — In [`map.js`](../web/static/js/map.js), replace the simple `bindPopup(priceText || 'Listing')` (~line 83) with:
   ```javascript
   var address = card.dataset.address || '';
   var beds = card.dataset.beds;
   var baths = card.dataset.baths;
   var sqft = card.dataset.sqft;
   var sqm = card.dataset.sqm;
   var imgUrl = card.dataset.img;
   var sourceUrl = card.dataset.url;
   var sourceName = card.dataset.source;

   var specsArr = [];
   if (beds) specsArr.push(beds + ' bd');
   if (baths) specsArr.push(baths + ' ba');
   if (sqft) {
       var sqftFormatted = Number(sqft).toLocaleString();
       specsArr.push(sqftFormatted + ' sqft' + (sqm ? ' (' + sqm + ' m²)' : ''));
   }

   var popupHtml = '<div class="map-popup">';
   if (imgUrl) {
       popupHtml += '<img src="' + imgUrl + '" class="popup-thumb" alt="" loading="lazy">';
   }
   popupHtml += '<div class="popup-content">';
   popupHtml += '<div class="popup-price">' + label + '</div>';
   if (address) popupHtml += '<div class="popup-address">' + address + '</div>';
   if (specsArr.length) popupHtml += '<div class="popup-specs">' + specsArr.join(' · ') + '</div>';
   if (sourceUrl) {
       popupHtml += '<a href="' + sourceUrl + '" target="_blank" rel="noopener" class="popup-source">'
           + (sourceName || 'View') + ' ↗</a>';
   }
   popupHtml += '</div></div>';

   marker.bindPopup(popupHtml, { maxWidth: 300, className: 'custom-popup' });
   ```

3. **Popup CSS** — Add to [`style.css`](../web/static/css/style.css):
   ```css
   .custom-popup .leaflet-popup-content-wrapper {
       border-radius: 8px;
       padding: 0;
       overflow: hidden;
       box-shadow: 0 4px 12px rgba(0,0,0,0.15);
   }
   .custom-popup .leaflet-popup-content { margin: 0; }
   .map-popup { display: flex; gap: 10px; padding: 10px; min-width: 200px; max-width: 300px; }
   .popup-thumb { width: 80px; height: 60px; object-fit: cover; border-radius: 6px; flex-shrink: 0; }
   .popup-content { display: flex; flex-direction: column; gap: 2px; }
   .popup-price { color: #2563eb; font-weight: 700; font-size: 15px; }
   .popup-address { color: #1a202c; font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 180px; }
   .popup-specs { color: #4a5568; font-size: 12px; }
   .popup-source { color: #2563eb; font-size: 11px; text-decoration: none; }
   .popup-source:hover { text-decoration: underline; }
   ```

**Dependencies**: None (can be done in parallel with 1.1–1.3).

**Acceptance criteria**:
- [ ] Clicking a price pill opens a popup with: thumbnail image, price (blue, bold), address, specs (beds · baths · sqft (m²)), source link
- [ ] Area shows BOTH sqft AND m² (design bible rule)
- [ ] Popup has 8px border-radius, white background, subtle shadow
- [ ] Source link opens original listing in new tab
- [ ] Popup renders correctly even when image is missing (graceful fallback)
- [ ] Popup max-width is 300px, doesn't overflow the map

**Effort**: 1h

---

## Sprint 2: POI System + Workplace Pin (P3 — ~5h)

### 2.1 POI Data Storage

**Goal**: Store user-defined Points of Interest with category, name, coordinates, and address.

**Recommendation**: Use a **JSON file** (`data/interest-points.json`) rather than a SQLite table. Rationale:
- POIs are user-preference data, not listing data — different lifecycle
- Typically <50 records — no need for SQL query power
- Simpler to seed, backup, and version-control
- No schema migration needed
- If the app later supports multiple users, migrate to SQLite then

**Files to create**:
- `data/interest-points.json` — POI data file (created on first write)

**Files to modify**:
- `src/poi.py` — **NEW** — POI CRUD module (read/write JSON, geocoding)

**Technical approach**:

1. **JSON schema** — `data/interest-points.json`:
   ```json
   {
     "points": [
       {
         "id": "poi_1",
         "category": "work",
         "name": "Palo Alto Networks HQ",
         "address": "3000 Tannery Way, Santa Clara, CA 95054",
         "latitude": 37.3861,
         "longitude": -121.9637,
         "created_at": "2026-03-30T20:00:00Z"
       }
     ]
   }
   ```

2. **POI module** — `src/poi.py`:
   ```python
   """POI (Points of Interest) CRUD operations backed by JSON file."""
   import json, uuid
   from pathlib import Path
   from datetime import datetime, timezone
   from src.geocoder import geocode_address

   _POI_FILE = Path(__file__).parent.parent / "data" / "interest-points.json"

   def _read() -> dict:
       if not _POI_FILE.exists():
           return {"points": []}
       return json.loads(_POI_FILE.read_text())

   def _write(data: dict) -> None:
       _POI_FILE.write_text(json.dumps(data, indent=2))

   def list_pois() -> list[dict]:
       return _read()["points"]

   def add_poi(category: str, name: str, address: str,
               lat: float | None = None, lng: float | None = None) -> dict:
       data = _read()
       if lat is None or lng is None:
           coords = geocode_address(address)
           if coords:
               lat, lng = coords
           else:
               raise ValueError(f"Could not geocode address: {address}")
       poi = {
           "id": f"poi_{uuid.uuid4().hex[:8]}",
           "category": category,
           "name": name,
           "address": address,
           "latitude": lat,
           "longitude": lng,
           "created_at": datetime.now(timezone.utc).isoformat(),
       }
       data["points"].append(poi)
       _write(data)
       return poi

   def delete_poi(poi_id: str) -> bool:
       data = _read()
       original_len = len(data["points"])
       data["points"] = [p for p in data["points"] if p["id"] != poi_id]
       if len(data["points"]) < original_len:
           _write(data)
           return True
       return False
   ```

3. **Seed the Palo Alto Networks HQ** — Pre-populate `data/interest-points.json` with the workplace pin (see task 2.5).

**Dependencies**: None — first task in Sprint 2.

**Acceptance criteria**:
- [ ] `src/poi.py` provides `list_pois()`, `add_poi()`, `delete_poi()` functions
- [ ] POIs are persisted in `data/interest-points.json`
- [ ] `add_poi()` geocodes the address if lat/lng not provided (uses existing [`src/geocoder.py`](../src/geocoder.py))
- [ ] `add_poi()` raises `ValueError` if geocoding fails
- [ ] Each POI has a unique `id` (UUID-based)
- [ ] Valid categories: `work`, `school`, `park`, `transit`, `shopping`, `custom`

**Effort**: 1h

---

### 2.2 POI API Endpoints

**Goal**: REST API for managing POIs — list, create, delete.

**Files to modify**:
- [`web/routes/api.py`](../web/routes/api.py) — add POI endpoints
- [`web/main.py`](../web/main.py) — ensure `api` router is already included (it is)

**Technical approach**:

Add three endpoints to [`web/routes/api.py`](../web/routes/api.py):

```python
from pydantic import BaseModel, field_validator
from src.poi import list_pois, add_poi, delete_poi

class POICreate(BaseModel):
    category: str
    name: str
    address: str
    latitude: float | None = None
    longitude: float | None = None

    @field_validator("category")
    @classmethod
    def validate_category(cls, v):
        allowed = {"work", "school", "park", "transit", "shopping", "custom"}
        if v not in allowed:
            raise ValueError(f"Category must be one of: {allowed}")
        return v

@router.get("/poi")
async def get_pois():
    """Return all saved Points of Interest."""
    return list_pois()

@router.post("/poi", status_code=201)
async def create_poi(poi: POICreate):
    """Create a new Point of Interest. Geocodes address if coords not provided."""
    try:
        result = add_poi(
            category=poi.category,
            name=poi.name,
            address=poi.address,
            lat=poi.latitude,
            lng=poi.longitude,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

@router.delete("/poi/{poi_id}")
async def remove_poi(poi_id: str):
    """Delete a Point of Interest by ID."""
    if not delete_poi(poi_id):
        raise HTTPException(status_code=404, detail="POI not found")
    return {"status": "deleted", "id": poi_id}
```

**Dependencies**: Task 2.1 (`src/poi.py` must exist).

**Acceptance criteria**:
- [ ] `GET /api/poi` returns JSON array of all POIs
- [ ] `POST /api/poi` with `{category, name, address}` creates a POI and returns it with coordinates
- [ ] `POST /api/poi` with invalid category returns 422
- [ ] `POST /api/poi` with un-geocodable address returns 422
- [ ] `DELETE /api/poi/{id}` removes the POI and returns 200
- [ ] `DELETE /api/poi/{nonexistent}` returns 404
- [ ] No new Python dependencies required (Pydantic is already a FastAPI dependency)

**Effort**: 0.75h

---

### 2.3 POI Markers on Map

**Goal**: Render POI markers as colored emoji circles on the map, organized into per-category layer groups.

**Files to modify**:
- [`web/static/js/map.js`](../web/static/js/map.js) — add POI marker rendering, layer groups, fetch from `/api/poi`
- [`web/static/css/style.css`](../web/static/css/style.css) — add `.poi-marker` and `.poi-circle` styles

**Technical approach**:

1. **POI layer groups** — In [`map.js`](../web/static/js/map.js), create per-category layer groups and add them to the layer control:
   ```javascript
   var poiCategories = {
       work:     { color: '#6366f1', icon: '🏢', label: 'Work' },
       school:   { color: '#f59e0b', icon: '🏫', label: 'Schools' },
       park:     { color: '#16a34a', icon: '🌳', label: 'Parks' },
       transit:  { color: '#8b5cf6', icon: '🚉', label: 'Transit' },
       shopping: { color: '#ec4899', icon: '🛒', label: 'Shopping' },
       custom:   { color: '#64748b', icon: '📍', label: 'Custom' }
   };
   var poiLayers = {};
   Object.keys(poiCategories).forEach(function(cat) {
       poiLayers[cat] = L.layerGroup().addTo(map);
   });
   ```

2. **Create POI marker function** — Per the design specs in [`design-bible.md`](../docs/design/design-bible.md) (POI Markers section):
   ```javascript
   function createPOIMarker(poi) {
       var cat = poiCategories[poi.category] || poiCategories.custom;
       var icon = L.divIcon({
           className: 'poi-marker',
           html: '<div class="poi-circle" style="background:' + cat.color + '"'
               + ' title="' + poi.name + '"'
               + ' aria-label="' + cat.label + ': ' + poi.name + '">'
               + cat.icon + '</div>',
           iconSize: [24, 24],
           iconAnchor: [12, 12]
       });
       return L.marker([poi.latitude, poi.longitude], { icon: icon })
           .bindTooltip(poi.name, { direction: 'top', offset: [0, -14] });
   }
   ```

3. **Fetch and render POIs** — On page load, fetch `/api/poi` and add markers:
   ```javascript
   function loadPOIs() {
       fetch('/api/poi')
           .then(function(r) { return r.json(); })
           .then(function(pois) {
               // Clear existing POI markers
               Object.values(poiLayers).forEach(function(lg) { lg.clearLayers(); });
               pois.forEach(function(poi) {
                   var marker = createPOIMarker(poi);
                   var layer = poiLayers[poi.category] || poiLayers.custom;
                   layer.addLayer(marker);
               });
           });
   }
   loadPOIs();
   ```

4. **Add POI layers to layer control** — Update the overlays object from task 1.3:
   ```javascript
   // Add POI category layers to the overlays
   Object.keys(poiCategories).forEach(function(cat) {
       overlays[poiCategories[cat].icon + ' ' + poiCategories[cat].label] = poiLayers[cat];
   });
   ```

5. **POI CSS** — Add to [`style.css`](../web/static/css/style.css) per the specs in [`map-improvement.md:249-261`](map-improvement.md:249):
   ```css
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
   @media (prefers-reduced-motion: reduce) {
       .poi-circle { transition: none; }
   }
   ```

**Dependencies**: Task 1.3 (layer control must exist), Task 2.1 + 2.2 (API must serve POI data).

**Acceptance criteria**:
- [ ] POI markers appear as 24×24px colored circles with emoji icons (per [`design-bible.md`](../docs/design/design-bible.md) POI Markers section)
- [ ] Each category has its own color: work=indigo, school=amber, park=green, transit=purple, shopping=pink, custom=slate
- [ ] POI markers are visually distinct from price pills (circles vs. pills)
- [ ] Hovering a POI marker shows a tooltip with the POI name
- [ ] POI markers have `aria-label` with category and name (WCAG AA)
- [ ] Each POI category appears as a toggleable overlay in the layer control
- [ ] POI markers have white 2px border for contrast
- [ ] `prefers-reduced-motion` disables hover animation

**Effort**: 1.25h

---

### 2.4 POI Management UI

**Goal**: Collapsible HTMX form panel in the dashboard for adding/deleting POIs.

**Files to create**:
- `web/templates/partials/poi-list.html` — **NEW** — HTMX partial for the POI list
- `web/templates/partials/poi-panel.html` — **NEW** — the full collapsible panel (form + list)

**Files to modify**:
- [`web/templates/dashboard.html`](../web/templates/dashboard.html) — include the POI panel below the map
- [`web/routes/api.py`](../web/routes/api.py) — add HTMX-aware response for `POST /api/poi` and `DELETE /api/poi/{id}`
- [`web/static/css/style.css`](../web/static/css/style.css) — add `.poi-panel` styles
- [`web/static/js/map.js`](../web/static/js/map.js) — listen for `htmx:afterSwap` on `#poi-list` to refresh map markers

**Technical approach**:

1. **POI panel template** — `web/templates/partials/poi-panel.html`:
   ```html
   <details class="poi-panel">
       <summary>📍 My Interest Points</summary>
       <form hx-post="/api/poi" hx-target="#poi-list" hx-swap="innerHTML"
             hx-on::after-request="if(event.detail.successful) this.reset()">
           <div class="poi-form-row">
               <select name="category" class="filter-select" aria-label="POI category" required>
                   <option value="work">🏢 Work</option>
                   <option value="school">🏫 School</option>
                   <option value="park">🌳 Park</option>
                   <option value="transit">🚉 Transit</option>
                   <option value="shopping">🛒 Shopping</option>
                   <option value="custom">📍 Custom</option>
               </select>
               <input type="text" name="name" placeholder="Name" required
                      aria-label="Point of interest name" class="poi-input">
               <input type="text" name="address" placeholder="Address" required
                      aria-label="Address" class="poi-input">
               <button type="submit" class="poi-add-btn">+ Add</button>
           </div>
       </form>
       <div id="poi-list" aria-live="polite">
           {% include "partials/poi-list.html" %}
       </div>
   </details>
   ```

2. **POI list partial** — `web/templates/partials/poi-list.html`:
   ```html
   {% for poi in pois %}
   <div class="poi-item" data-poi-id="{{ poi.id }}">
       <span class="poi-item-icon">{{ poi_icons[poi.category] }}</span>
       <span class="poi-item-name">{{ poi.name }}</span>
       <span class="poi-item-address">{{ poi.address }}</span>
       <button class="poi-delete-btn"
               hx-delete="/api/poi/{{ poi.id }}"
               hx-target="#poi-list"
               hx-swap="innerHTML"
               hx-confirm="Delete '{{ poi.name }}'?"
               aria-label="Delete {{ poi.name }}">✕</button>
   </div>
   {% endfor %}
   {% if not pois %}
   <div class="poi-empty">No interest points yet. Add your workplace, schools, or parks above.</div>
   {% endif %}
   ```

3. **Dashboard integration** — In [`dashboard.html`](../web/templates/dashboard.html), add inside `.right-panel` after `#map-container` (~line 80):
   ```html
   {% include "partials/poi-panel.html" %}
   ```

4. **HTMX-aware API responses** — Modify `POST /api/poi` and `DELETE /api/poi/{id}` in [`api.py`](../web/routes/api.py) to detect HTMX requests (`HX-Request` header) and return the `poi-list.html` partial instead of JSON:
   ```python
   @router.post("/api/poi")
   async def create_poi(request: Request, ...):
       # ... create POI ...
       if request.headers.get("HX-Request"):
           pois = list_pois()
           return templates.TemplateResponse(request, "partials/poi-list.html",
               context={"pois": pois, "poi_icons": POI_ICONS})
       return result  # JSON for non-HTMX clients
   ```

5. **Map refresh on POI change** — In [`map.js`](../web/static/js/map.js), listen for HTMX swaps on `#poi-list`:
   ```javascript
   document.body.addEventListener('htmx:afterSwap', function(event) {
       if (event.detail.target && event.detail.target.id === 'poi-list') {
           loadPOIs();  // Re-fetch and re-render POI markers
       }
   });
   ```

6. **POI panel CSS** — Add to [`style.css`](../web/static/css/style.css):
   ```css
   .poi-panel { padding: 8px 12px; border-top: 1px solid var(--border-card); }
   .poi-panel summary { cursor: pointer; font-weight: 600; font-size: 14px; color: var(--text-primary); }
   .poi-form-row { display: flex; gap: 6px; margin-top: 8px; flex-wrap: wrap; }
   .poi-input { flex: 1; min-width: 100px; padding: 6px 10px; border: 1px solid var(--border-card);
                border-radius: 6px; font-size: 13px; font-family: 'Inter', sans-serif; }
   .poi-add-btn { background: #2563eb; color: white; border: none; border-radius: 6px;
                  padding: 6px 12px; font-size: 13px; font-weight: 600; cursor: pointer; }
   .poi-add-btn:hover { background: #1d4ed8; }
   .poi-item { display: flex; align-items: center; gap: 8px; padding: 6px 0;
               border-bottom: 1px solid var(--border-card); font-size: 13px; }
   .poi-item-icon { font-size: 16px; }
   .poi-item-name { font-weight: 600; color: var(--text-primary); }
   .poi-item-address { color: var(--text-muted); flex: 1; overflow: hidden;
                       text-overflow: ellipsis; white-space: nowrap; }
   .poi-delete-btn { background: none; border: none; color: var(--text-muted);
                     cursor: pointer; font-size: 14px; padding: 4px 8px; min-width: 44px;
                     min-height: 44px; display: flex; align-items: center; justify-content: center; }
   .poi-delete-btn:hover { color: #dc2626; }
   .poi-empty { color: var(--text-muted); font-size: 13px; padding: 12px 0; }
   ```

**Dependencies**: Tasks 2.1, 2.2, 2.3 (POI storage, API, and map markers must exist).

**Acceptance criteria**:
- [ ] Collapsible "📍 My Interest Points" panel appears below the map
- [ ] Form has category dropdown, name input, address input, and "+ Add" button
- [ ] Submitting the form adds a POI (geocodes address) and updates the list via HTMX
- [ ] Each POI in the list shows icon, name, address, and a delete button (✕)
- [ ] Delete button shows confirmation dialog before deleting
- [ ] After add/delete, map markers refresh automatically (no page reload)
- [ ] Form resets after successful submission
- [ ] Delete button meets 44×44px minimum touch target (WCAG AA)
- [ ] `aria-live="polite"` on `#poi-list` announces changes to screen readers
- [ ] Empty state shows helpful guidance text

**Effort**: 1.5h

---

### 2.5 Palo Alto Networks Office Pin (Pre-seed)

**Goal**: Pre-populate the first POI so the map shows the workplace immediately after implementation.

**Files to create**:
- `data/interest-points.json` — seed file with the Palo Alto Networks HQ entry

**Technical approach**:

1. **Verify coordinates** — The approximate coordinates for 3000 Tannery Way, Santa Clara, CA 95054 are `37.3861, -121.9637`. Verify using the existing [`geocode_address()`](../src/geocoder.py) function:
   ```python
   # Quick verification script (run once during implementation)
   from src.geocoder import geocode_address
   coords = geocode_address("3000 Tannery Way, Santa Clara, CA 95054")
   print(coords)  # Should be close to (37.3861, -121.9637)
   ```

2. **Create seed file** — `data/interest-points.json`:
   ```json
   {
     "points": [
       {
         "id": "poi_panw_hq",
         "category": "work",
         "name": "Palo Alto Networks HQ",
         "address": "3000 Tannery Way, Santa Clara, CA 95054",
         "latitude": 37.3861,
         "longitude": -121.9637,
         "created_at": "2026-03-30T20:00:00Z"
       }
     ]
   }
   ```
   > **Note**: Use the geocoder-verified coordinates. The values above are approximate and should be replaced with the actual geocoder output during implementation.

**Dependencies**: Task 2.1 (JSON schema must be defined).

**Acceptance criteria**:
- [ ] `data/interest-points.json` exists with the Palo Alto Networks HQ entry
- [ ] The workplace pin appears on the map as a 🏢 indigo circle marker
- [ ] Hovering the marker shows tooltip "Palo Alto Networks HQ"
- [ ] The pin is visible in the POI management panel list
- [ ] Coordinates are verified via geocoder (not just the approximate values)

**Effort**: 0.5h

---

## Sprint 3: Advanced Features (P3-P4 — ~5h)

### 3.1 Satellite/Street Toggle

**Goal**: Add a satellite imagery tile layer as an alternative base layer.

**Files to modify**:
- [`web/static/js/map.js`](../web/static/js/map.js) — add Esri World Imagery tile layer to `baseLayers`

**Technical approach**:

In [`map.js`](../web/static/js/map.js), add a satellite tile layer and include it in the base layers object (from task 1.3):

```javascript
var satelliteLayer = L.tileLayer(
    'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    {
        attribution: '&copy; Esri, Maxar, Earthstar Geographics',
        maxZoom: 18
    }
);

// Update baseLayers (from task 1.3):
var baseLayers = {
    'Street': osmLayer,
    'Satellite': satelliteLayer
};
```

No additional CSS needed — the layer control from task 1.3 handles the toggle UI.

**Dependencies**: Task 1.3 (layer control must exist).

**Acceptance criteria**:
- [ ] Layer control shows "Street" and "Satellite" as base layer options (radio buttons)
- [ ] Selecting "Satellite" switches to Esri World Imagery tiles
- [ ] Selecting "Street" switches back to OpenStreetMap
- [ ] Price pills and POI markers remain visible on satellite view
- [ ] Attribution updates correctly for each tile provider
- [ ] No API key required (Esri World Imagery is free with attribution)

**Effort**: 0.5h

---

### 3.2 Commute Radius Overlay

**Goal**: Draw a configurable radius circle around the work location to visualize commute distance.

**Files to modify**:
- [`web/static/js/map.js`](../web/static/js/map.js) — add `L.circle()` around work POI, radius selector
- [`web/static/css/style.css`](../web/static/css/style.css) — style the radius control
- [`web/templates/partials/poi-panel.html`](../web/templates/partials/poi-panel.html) — add radius dropdown

**Technical approach**:

1. **Radius circle** — In [`map.js`](../web/static/js/map.js), after loading POIs, find the first "work" POI and draw a radius circle:
   ```javascript
   var commuteCircle = null;

   function updateCommuteRadius(radiusKm) {
       if (commuteCircle) map.removeLayer(commuteCircle);
       if (radiusKm <= 0) return;

       // Find the first work POI
       var workPoi = null;
       // (iterate loaded POIs to find category === 'work')

       if (!workPoi) return;

       commuteCircle = L.circle([workPoi.latitude, workPoi.longitude], {
           radius: radiusKm * 1000,  // Leaflet uses meters
           color: '#6366f1',
           fillColor: '#6366f1',
           fillOpacity: 0.08,
           weight: 2,
           dashArray: '6, 4'
       }).addTo(map);
   }
   ```

2. **Radius selector** — Add a dropdown in the POI panel (inside `poi-panel.html`):
   ```html
   <div class="commute-radius-row">
       <label for="commute-radius">🏢 Commute radius:</label>
       <select id="commute-radius" class="filter-select" onchange="updateCommuteRadius(Number(this.value))">
           <option value="0">Off</option>
           <option value="5">5 km</option>
           <option value="10" selected>10 km</option>
           <option value="15">15 km</option>
           <option value="20">20 km</option>
           <option value="25">25 km</option>
       </select>
   </div>
   ```

3. **Add to layer control** — Add the commute circle as a toggleable overlay:
   ```javascript
   overlays['🏢 Commute Radius'] = commuteCircle ? L.layerGroup([commuteCircle]) : L.layerGroup();
   ```

**Dependencies**: Tasks 2.1–2.5 (work POI must exist on the map).

**Acceptance criteria**:
- [ ] Radius dropdown appears in the POI panel with options: Off, 5km, 10km, 15km, 20km, 25km
- [ ] Selecting a radius draws a dashed indigo circle around the work location
- [ ] Circle uses `fillOpacity: 0.08` (subtle, doesn't obscure map)
- [ ] Changing the radius updates the circle immediately (no page reload)
- [ ] "Off" removes the circle
- [ ] Circle is centered on the first "work" category POI
- [ ] If no work POI exists, the dropdown is disabled or shows a hint

**Effort**: 1.5h

---

### 3.3 Search as I Move the Map

**Goal**: Automatically refresh listing cards when the user pans or zooms the map, filtering to only show listings visible in the current map viewport.

**Files to modify**:
- [`web/static/js/map.js`](../web/static/js/map.js) — add `map.on('moveend')` handler with debounce
- [`web/routes/listings.py`](../web/routes/listings.py) — add bounding box filter parameters
- [`web/routes/__init__.py`](../web/routes/__init__.py) — extend `parse_filters()` with bounds
- [`src/database.py`](../src/database.py) — add lat/lng bounds filtering to `get_filtered_listings()`
- [`web/templates/dashboard.html`](../web/templates/dashboard.html) — add toggle checkbox
- [`web/static/css/style.css`](../web/static/css/style.css) — style the toggle

**Technical approach**:

1. **Map moveend handler** — In [`map.js`](../web/static/js/map.js):
   ```javascript
   var searchOnMove = false;  // Off by default
   var moveDebounceTimer = null;

   map.on('moveend', function() {
       if (!searchOnMove) return;
       clearTimeout(moveDebounceTimer);
       moveDebounceTimer = setTimeout(function() {
           var bounds = map.getBounds();
           var params = new URLSearchParams();
           // Include current filter values
           document.querySelectorAll('[name^="filter_"]').forEach(function(el) {
               params.set(el.name, el.value);
           });
           // Add bounds
           params.set('sw_lat', bounds.getSouthWest().lat.toFixed(6));
           params.set('sw_lng', bounds.getSouthWest().lng.toFixed(6));
           params.set('ne_lat', bounds.getNorthEast().lat.toFixed(6));
           params.set('ne_lng', bounds.getNorthEast().lng.toFixed(6));
           htmx.ajax('GET', '/listings?' + params.toString(), '#listing-cards');
       }, 500);  // 500ms debounce
   });
   ```

2. **Toggle checkbox** — Add to [`dashboard.html`](../web/templates/dashboard.html) inside the map area (floating over the map):
   ```html
   <label class="search-on-move-toggle" title="Update listings when map moves">
       <input type="checkbox" id="search-on-move" onchange="searchOnMove = this.checked">
       Search as I move the map
   </label>
   ```

3. **Backend bounds filtering** — In [`listings.py`](../web/routes/listings.py), accept optional bounds parameters:
   ```python
   sw_lat: Optional[float] = Query(None),
   sw_lng: Optional[float] = Query(None),
   ne_lat: Optional[float] = Query(None),
   ne_lng: Optional[float] = Query(None),
   ```
   Pass to `parse_filters()` → `get_filtered_listings()` which adds:
   ```python
   if "bounds" in filters:
       b = filters["bounds"]
       query = query.filter(
           Listing.latitude >= b["sw_lat"],
           Listing.latitude <= b["ne_lat"],
           Listing.longitude >= b["sw_lng"],
           Listing.longitude <= b["ne_lng"],
       )
   ```

4. **Disable fitBounds when search-on-move is active** — When `searchOnMove` is true, skip the `map.fitBounds()` call in `addMarkers()` to prevent the map from jumping back after a pan.

**Dependencies**: None within Sprint 3 (but Sprint 1 should be complete for clustering to work with bounds filtering).

**Acceptance criteria**:
- [ ] Floating "Search as I move the map" checkbox appears on the map (bottom-left or top-left)
- [ ] When enabled, panning or zooming the map refreshes listing cards to show only listings in the visible area
- [ ] Debounced at 500ms to avoid excessive requests
- [ ] Current filter selections (price, beds, baths, source, sort) are preserved during map-move searches
- [ ] When disabled, map panning does not trigger listing refresh
- [ ] Map does NOT auto-fit bounds when search-on-move is active (prevents jarring jumps)
- [ ] Toggle is off by default (opt-in behavior)
- [ ] Loading state (opacity fade) shows during HTMX request

**Effort**: 2.5h

---

### 3.4 Premium Tiles (Optional — Stadia Outdoors)

**Goal**: Add Stadia Outdoors as a higher-quality tile layer option.

**Files to modify**:
- [`web/static/js/map.js`](../web/static/js/map.js) — add Stadia Outdoors tile layer
- [`config.yaml`](../config.yaml) — add optional `stadia_api_key` field

**Technical approach**:

1. **Stadia tile layer** — In [`map.js`](../web/static/js/map.js):
   ```javascript
   // Only add if API key is configured (passed via data attribute on map container)
   var stadiaKey = mapContainer.dataset.stadiaKey;
   if (stadiaKey) {
       var stadiaOutdoors = L.tileLayer(
           'https://tiles.stadiamaps.com/tiles/outdoors/{z}/{x}/{y}{r}.png?api_key=' + stadiaKey,
           {
               attribution: '&copy; Stadia Maps &copy; OpenMapTiles &copy; OpenStreetMap',
               maxZoom: 20,
               detectRetina: true
           }
       );
       baseLayers['Outdoors'] = stadiaOutdoors;
   }
   ```

2. **Pass API key to template** — In [`dashboard.html`](../web/templates/dashboard.html):
   ```html
   <div id="map-container" {% if stadia_api_key %}data-stadia-key="{{ stadia_api_key }}"{% endif %}></div>
   ```

3. **Config** — Add to [`config.yaml`](../config.yaml):
   ```yaml
   map:
     stadia_api_key: ""  # Optional — register at stadiamaps.com for free tier (200K tiles/month)
   ```

**Dependencies**: Task 1.3 (layer control must exist). Requires Stadia Maps account registration (free).

**Acceptance criteria**:
- [ ] If `stadia_api_key` is configured, "Outdoors" appears as a third base layer option
- [ ] If no API key, only "Street" and "Satellite" are available (no error)
- [ ] Stadia Outdoors tiles show parks, terrain shading, and clean typography
- [ ] Retina/HiDPI support enabled (`detectRetina: true`)
- [ ] Attribution is correct for Stadia Maps

**Effort**: 0.5h

---

## Dependency Graph

```
Sprint 1 (can be parallelized):
  1.1 Marker Clustering ──┐
  1.2 Selected State       │──► 1.3 Layer Control
  1.4 Rich Popups          │
                           │
Sprint 2 (sequential):     │
  2.1 POI Storage ──► 2.2 POI API ──► 2.3 POI Markers ──► 2.4 POI UI
  2.5 Seed Data ─────────────────────────┘                      │
                                                                │
Sprint 3:                                                       │
  3.1 Satellite Toggle (needs 1.3) ◄────────────────────────────┘
  3.2 Commute Radius (needs 2.1-2.5)
  3.3 Search as I Move (independent)
  3.4 Premium Tiles (needs 1.3, optional)
```

---

## File Change Summary

### New Files (4)

| File | Purpose |
|------|---------|
| `src/poi.py` | POI CRUD module (JSON file backend) |
| `data/interest-points.json` | POI data storage (seeded with PANW HQ) |
| `web/templates/partials/poi-panel.html` | Collapsible POI management panel |
| `web/templates/partials/poi-list.html` | HTMX partial for POI list items |

### Modified Files (8)

| File | Changes |
|------|---------|
| [`web/templates/base.html`](../web/templates/base.html) | Add MarkerCluster CDN (CSS + JS) |
| [`web/static/js/map.js`](../web/static/js/map.js) | Major refactor: cluster group, layer control, POI markers, rich popups, selected state, search-on-move, commute radius |
| [`web/static/css/style.css`](../web/static/css/style.css) | Add: cluster, selected pill, layer control, popup, POI marker, POI panel, commute, search-on-move styles |
| [`web/templates/dashboard.html`](../web/templates/dashboard.html) | Include POI panel, add search-on-move toggle, optional Stadia key data attribute |
| [`web/templates/partials/listing-card.html`](../web/templates/partials/listing-card.html) | Add `data-*` attributes for popup content |
| [`web/routes/api.py`](../web/routes/api.py) | Add `GET/POST/DELETE /api/poi` endpoints |
| [`web/routes/listings.py`](../web/routes/listings.py) | Add bounding box filter parameters |
| [`src/database.py`](../src/database.py) | Add lat/lng bounds filtering to `get_filtered_listings()` |

### Optionally Modified (1)

| File | Changes |
|------|---------|
| [`config.yaml`](../config.yaml) | Add optional `map.stadia_api_key` field |

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| MarkerCluster CDN unavailable | Low | Medium | Pin version, add `integrity` hash, consider local copy |
| Geocoding fails for POI address | Medium | Low | Show clear error message, allow manual lat/lng entry |
| Nominatim rate limit (1 req/s) | Low | Low | Existing circuit breaker + cache in [`geocoder.py`](../src/geocoder.py) handles this |
| Too many markers slow DOM | Low | Medium | Clustering (task 1.1) reduces visible DOM nodes |
| Search-on-move causes excessive API calls | Medium | Low | 500ms debounce + HTMX request indicator |
| Stadia API key exposure in HTML | Low | Low | Free tier, key is domain-restricted, not a secret |

---

## Testing Strategy

Each sprint should be tested before moving to the next:

### Sprint 1 Tests
- Visual: zoom in/out to verify clustering behavior
- Interaction: click pills to verify selected state persists
- Layer control: toggle each layer on/off
- Popups: verify all data fields render (including sqft + m²)
- HTMX: change filters and verify markers + clusters refresh

### Sprint 2 Tests
- API: `curl` test all three POI endpoints
- UI: add a POI via the form, verify it appears on map
- UI: delete a POI, verify it disappears from map
- Seed: verify PANW HQ pin appears on fresh load
- Accessibility: Tab through POI form, verify focus management

### Sprint 3 Tests
- Satellite: toggle between Street/Satellite, verify markers visible on both
- Commute: select different radii, verify circle updates
- Search-on-move: enable toggle, pan map, verify cards update
- Performance: verify debounce prevents excessive requests

---

## Open Questions for Product Owner

1. **Commute radius default**: Should the commute radius be **10 km** by default, or start as **Off**?
2. **Search-on-move default**: Should "Search as I move the map" be **off** by default (opt-in) or **on** by default?
3. **POI management location**: Should the POI panel be in the **dashboard** (below map) or in the **backoffice** (`/admin/`)? Current plan puts it in the dashboard for convenience.
4. **Sprint priority**: Should we implement all 3 sprints, or stop after Sprint 1 or Sprint 2?
5. **Stadia Maps**: Should we register for a Stadia Maps API key now, or defer premium tiles?

---

*This plan is ready for product owner review. After approval, implementation will follow the Code → Code Review → Fix cycle per [`AGENTS.md`](../AGENTS.md).*
