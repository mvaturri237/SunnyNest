# Phase 1 UX Spec — FastAPI Dashboard Visual Polish

> **Date**: 2026-03-30  
> **Author**: UX Designer Agent  
> **Status**: Ready for Implementation  
> **Design Bible**: [`docs/design/design-bible.md`](../docs/design/design-bible.md)  
> **Target Mockup**: [`docs/temp/mockups/sunnynest-dashboard.html`](../docs/temp/mockups/sunnynest-dashboard.html)  
> **Current CSS**: [`web/static/css/style.css`](../web/static/css/style.css)  
> **Current Template**: [`web/templates/dashboard.html`](../web/templates/dashboard.html)  
> **Current Card**: [`web/templates/partials/listing-card.html`](../web/templates/partials/listing-card.html)  
> **Current Map JS**: [`web/static/js/map.js`](../web/static/js/map.js)

---

## Executive Summary

Phase 0 delivered a functional FastAPI + HTMX + Jinja2 dashboard with working filters, listing cards, and a Leaflet map. The foundation is solid — HTMX filter swaps work, card layout is horizontal, design tokens are in CSS variables, and the dark theme is applied. However, **6 significant visual/UX gaps** remain between the current implementation and the design bible target. This spec provides exact, copy-paste-ready fixes ordered by visual impact.

### Phase 0 Scorecard

| Dimension | Score | Notes |
|-----------|-------|-------|
| Layout structure | 7/10 | Split panel works but CSS `width: 42%` is overridden by browser — appears ~20% |
| Card design | 8/10 | Horizontal layout correct, all required content present |
| Filter bar | 8/10 | Functional, pill-style, HTMX wired. Missing reset button |
| Map | 4/10 | Basic markers only — no price pills, no boundary, light tiles on dark UI |
| Interactions | 3/10 | Favorite button visual-only, no card-map sync, no dislike |
| Accessibility | 5/10 | `aria-live` on cards container ✅, but missing `aria-pressed`, `aria-label`, focus states |
| States | 4/10 | Empty state exists, but no loading skeleton, no error state |

---

## 1. Visual Audit — Current vs. Design Bible

### 1.1 Layout Issues

| Issue | Current | Design Bible Target | Severity |
|-------|---------|-------------------|----------|
| **Left panel width** | CSS says `42%` but renders ~20% in browser | `width: 42%; min-width: 380px; max-width: 520px` | 🔴 P0 |
| **Panel divider** | `border-right: 1px solid var(--color-border)` on left panel | Correct — matches design bible | ✅ OK |
| **Filter bar height** | `56px` | Design bible doesn't specify; mockup uses `48px` | ⚪ Minor |
| **Card gap** | `margin-bottom: 8px` | Mockup uses `gap: 8px` in flex column | ⚪ Minor |

**Root cause of ~20% panel width**: The CSS in [`style.css:162`](../web/static/css/style.css:162) correctly sets `width: 42%`, but the Leaflet map container may be forcing the right panel to expand. The `flex: 1` on `.right-panel` combined with Leaflet's internal sizing can compress the left panel. **Fix**: Add `flex-shrink: 0` to `.left-panel`.

### 1.2 Map Issues

| Issue | Current | Design Bible Target | Severity |
|-------|---------|-------------------|----------|
| **Map tiles** | OpenStreetMap Standard (light) | Stadia Alidade Smooth Dark (dark theme) | 🔴 P0 |
| **Markers** | Default blue Leaflet pins | Price pill markers (`#3b82f6`, 11px bold, 12px radius) | 🔴 P0 |
| **City boundary** | Missing | Sunnyvale boundary overlay from `data/sunnyvale-boundary.geojson` | 🟡 P1 |
| **Marker clustering** | None | Cluster when zoomed out with unit count badges | 🟡 P1 |
| **Map popups** | Plain text (just price string) | Styled popup: white bg, price, specs, source link | 🟡 P1 |
| **Card-map sync** | None | Bidirectional: card hover → marker highlight, marker click → card scroll | 🟡 P1 |

### 1.3 Card Issues

| Issue | Current | Design Bible Target | Severity |
|-------|---------|-------------------|----------|
| **Broken images** | Shows "Listing photo" alt text | Should show placeholder emoji (🏠/🏢) via `onerror` fallback | 🟡 P1 |
| **Favorite button** | Visual only, 32×32px, opacity 0 until hover | Functional HTMX toggle, 44×44px min touch target, always visible on mobile | 🟡 P1 |
| **Dislike button** | Missing entirely | Overlay button on image, HTMX `hx-delete` to hide listing | 🟢 P2 |
| **Card semantics** | `<div class="listing-card">` | `<article class="listing-card" role="article" tabindex="0">` | 🟡 P1 |
| **Image alt text** | Generic "Listing photo" | Descriptive: "Photo of {address}" | 🟡 P1 |
| **Source pills** | Only Craigslist visible | Both Zillow and Craigslist should show (data issue, not template) | 🟡 P1 |

### 1.4 Filter Bar Issues

| Issue | Current | Design Bible Target | Severity |
|-------|---------|-------------------|----------|
| **Reset button** | Missing | `✕` button to clear all filters | 🟡 P1 |
| **Active filter state** | No visual change when filter is active | Blue background tint on active filters | 🟢 P2 |
| **URL state** | Filters don't update URL | `hx-push-url="true"` for bookmarkable searches | 🟢 P2 |
| **Result count update** | Static on page load | Should update via HTMX `hx-swap-oob` when filters change | 🟡 P1 |

### 1.5 Missing States

| State | Current | Design Bible Target | Severity |
|-------|---------|-------------------|----------|
| **Loading skeleton** | `opacity: 0.5` during HTMX request | Shimmer skeleton cards (3-4 cards) | 🟡 P1 |
| **Error state** | None | "Failed to load" message + retry button | 🟡 P1 |
| **Selected card** | None | Brand-color border + shadow when marker clicked | 🟡 P1 |
| **Focus states** | Missing from CSS | `:focus-visible` outline on all interactive elements | 🟡 P1 |

---

## 2. Priority-Ordered Fix List

### 🔴 P0 — Critical Visual Impact (Fix First)

| # | Fix | Files | Est. Time |
|---|-----|-------|-----------|
| P0-1 | **Fix left panel width** — add `flex-shrink: 0` to `.left-panel` | [`style.css`](../web/static/css/style.css) | 5 min |
| P0-2 | **Dark map tiles** — switch to Stadia Alidade Smooth Dark | [`map.js`](../web/static/js/map.js) | 10 min |
| P0-3 | **Price pill markers** — replace default pins with styled `L.divIcon` | [`map.js`](../web/static/js/map.js), [`style.css`](../web/static/css/style.css) | 30 min |

### 🟡 P1 — Important UX Improvements

| # | Fix | Files | Est. Time |
|---|-----|-------|-----------|
| P1-1 | **Sunnyvale boundary overlay** — load GeoJSON, style with blue stroke | [`map.js`](../web/static/js/map.js) | 20 min |
| P1-2 | **Image fallback** — add `onerror` handler for broken images | [`listing-card.html`](../web/templates/partials/listing-card.html) | 10 min |
| P1-3 | **Functional favorite toggle** — HTMX `hx-post` with `aria-pressed` | [`listing-card.html`](../web/templates/partials/listing-card.html), new API route | 45 min |
| P1-4 | **Card-map bidirectional sync** — hover/click highlights | [`map.js`](../web/static/js/map.js), [`style.css`](../web/static/css/style.css) | 45 min |
| P1-5 | **Loading skeleton** — shimmer cards during HTMX requests | New partial, [`style.css`](../web/static/css/style.css) | 30 min |
| P1-6 | **Styled map popups** — white bg, price, specs, source link | [`map.js`](../web/static/js/map.js), [`style.css`](../web/static/css/style.css) | 30 min |
| P1-7 | **Result count OOB update** — update count when filters change | [`listing-cards.html`](../web/templates/partials/listing-cards.html), [`dashboard.html`](../web/templates/dashboard.html) | 15 min |
| P1-8 | **Reset filters button** — clear all dropdowns to defaults | [`dashboard.html`](../web/templates/dashboard.html), [`style.css`](../web/static/css/style.css) | 20 min |
| P1-9 | **Focus states** — `:focus-visible` on cards, buttons, selects | [`style.css`](../web/static/css/style.css) | 15 min |
| P1-10 | **Card semantics + accessibility** — `<article>`, `tabindex`, `aria-label` | [`listing-card.html`](../web/templates/partials/listing-card.html) | 15 min |
| P1-11 | **Error state partial** — "Failed to load" with retry button | New partial, [`style.css`](../web/static/css/style.css) | 15 min |
| P1-12 | **Marker clustering** — Leaflet.markercluster with styled clusters | [`map.js`](../web/static/js/map.js), [`base.html`](../web/templates/base.html) | 30 min |

### 🟢 P2 — Polish & Enhancement

| # | Fix | Files | Est. Time |
|---|-----|-------|-----------|
| P2-1 | **Dislike button** — overlay on image, HTMX delete with fade-out | [`listing-card.html`](../web/templates/partials/listing-card.html), new API route | 30 min |
| P2-2 | **Active filter visual state** — blue tint on non-default values | [`style.css`](../web/static/css/style.css), small JS | 20 min |
| P2-3 | **URL-based filter state** — `hx-push-url="true"` | [`dashboard.html`](../web/templates/dashboard.html) | 10 min |
| P2-4 | **Card enter animation** — staggered fade-in on filter change | [`style.css`](../web/static/css/style.css) | 15 min |
| P2-5 | **Responsive breakpoint (768-1024px)** — narrower panel | [`style.css`](../web/static/css/style.css) | 15 min |
| P2-6 | **`prefers-reduced-motion`** — disable animations | [`style.css`](../web/static/css/style.css) | 5 min |

---

## 3. Specific CSS/Layout Recommendations

### 3.1 Fix Left Panel Width (P0-1)

**Problem**: The left panel CSS says `width: 42%` but Leaflet's map container with `flex: 1` on the right panel compresses it. The left panel needs `flex-shrink: 0` to prevent compression.

**File**: [`web/static/css/style.css`](../web/static/css/style.css) — lines 161-168

```css
/* BEFORE */
.left-panel {
    width: 42%;
    min-width: 380px;
    max-width: 520px;
    overflow-y: auto;
    padding: 12px;
    border-right: 1px solid var(--color-border);
}

/* AFTER */
.left-panel {
    width: 440px;           /* Fixed width instead of percentage — more predictable */
    min-width: 380px;
    max-width: 520px;
    flex-shrink: 0;          /* ← KEY FIX: prevent Leaflet from compressing */
    overflow-y: auto;
    padding: 12px;
    border-right: 1px solid var(--color-border);
}
```

**Why `440px` instead of `42%`**: On a 1920px screen, 42% = 806px (too wide). On a 1280px screen, 42% = 538px (exceeds max-width). A fixed `440px` matches the design bible's "440px width on desktop" specification and avoids percentage-based unpredictability.

### 3.2 Selected Card State (P1-4)

**File**: [`web/static/css/style.css`](../web/static/css/style.css) — add after `.listing-card:hover`

```css
/* Selected card — when corresponding map marker is clicked */
.listing-card.selected {
    border-color: var(--color-brand);
    box-shadow: 0 0 0 1px var(--color-brand), 0 4px 16px var(--color-card-shadow-hover);
    background: rgba(59, 130, 246, 0.05);
}
```

### 3.3 Focus States (P1-9)

**File**: [`web/static/css/style.css`](../web/static/css/style.css) — add to base section

```css
/* Focus visible — keyboard navigation */
:focus-visible {
    outline: 2px solid var(--color-brand);
    outline-offset: 2px;
    border-radius: 4px;
}

/* Remove default outline for mouse users */
:focus:not(:focus-visible) {
    outline: none;
}

/* Specific focus for cards */
.listing-card:focus-visible {
    border-color: var(--color-brand);
    box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.3);
}

/* Specific focus for filter selects */
.filter-select:focus-visible {
    border-color: var(--color-brand);
    box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2);
}
```

### 3.4 Loading Skeleton Styles (P1-5)

**File**: [`web/static/css/style.css`](../web/static/css/style.css) — add new section

```css
/* ============================================================
   Loading Skeleton
   ============================================================ */
.skeleton-card {
    display: flex;
    gap: 12px;
    padding: 12px;
    margin-bottom: 8px;
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-card);
}

.skeleton-thumb {
    width: 140px;
    height: 130px;
    border-radius: 8px;
    flex-shrink: 0;
    background: linear-gradient(90deg,
        rgba(255,255,255,0.04) 25%,
        rgba(255,255,255,0.08) 50%,
        rgba(255,255,255,0.04) 75%);
    background-size: 200% 100%;
    animation: shimmer 1.5s infinite;
}

.skeleton-details {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 8px;
    justify-content: center;
}

.skeleton-line {
    height: 14px;
    border-radius: 4px;
    background: linear-gradient(90deg,
        rgba(255,255,255,0.04) 25%,
        rgba(255,255,255,0.08) 50%,
        rgba(255,255,255,0.04) 75%);
    background-size: 200% 100%;
    animation: shimmer 1.5s infinite;
}

.skeleton-line.w60 { width: 60%; }
.skeleton-line.w80 { width: 80%; }
.skeleton-line.w40 { width: 40%; }
.skeleton-line.w50 { width: 50%; }

@keyframes shimmer {
    0% { background-position: 200% 0; }
    100% { background-position: -200% 0; }
}

/* Override HTMX default opacity change */
#listing-cards.htmx-request {
    opacity: 1;  /* Don't dim — show skeleton instead */
}
```

### 3.5 Price Pill Marker Styles (P0-3)

**File**: [`web/static/css/style.css`](../web/static/css/style.css) — add new section

```css
/* ============================================================
   Map Price Pill Markers
   ============================================================ */
.price-marker {
    background: var(--color-brand);
    color: #fff;
    font-family: var(--font-family);
    font-size: 11px;
    font-weight: 700;
    padding: 4px 8px;
    border-radius: 12px;
    white-space: nowrap;
    box-shadow: 0 2px 8px rgba(59, 130, 246, 0.3);
    cursor: pointer;
    transition: transform 0.15s ease, box-shadow 0.15s ease;
    text-align: center;
    line-height: 1;
    border: 2px solid rgba(255, 255, 255, 0.3);
}

.price-marker:hover {
    transform: scale(1.05);
    box-shadow: 0 4px 12px rgba(59, 130, 246, 0.5);
}

.price-marker.selected {
    background: var(--color-brand-dark);
    transform: scale(1.1);
    z-index: 1000 !important;
    box-shadow: 0 4px 16px rgba(29, 78, 216, 0.5);
}

/* Cluster markers */
.marker-cluster {
    background: rgba(59, 130, 246, 0.2);
    border-radius: 50%;
}

.marker-cluster div {
    background: var(--color-brand);
    color: #fff;
    font-family: var(--font-family);
    font-size: 12px;
    font-weight: 700;
    border-radius: 50%;
    width: 36px;
    height: 36px;
    display: flex;
    align-items: center;
    justify-content: center;
    margin: 5px;
    box-shadow: 0 2px 8px rgba(59, 130, 246, 0.3);
}
```

### 3.6 Map Popup Styles (P1-6)

**File**: [`web/static/css/style.css`](../web/static/css/style.css) — add to Leaflet overrides section

```css
/* ============================================================
   Map Popup Styles (Dark Theme)
   ============================================================ */
.leaflet-popup-content-wrapper {
    background: #1a1d26 !important;
    border-radius: 8px !important;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4) !important;
    border: 1px solid var(--color-border) !important;
    padding: 0 !important;
}

.leaflet-popup-tip {
    background: #1a1d26 !important;
    border: 1px solid var(--color-border) !important;
    box-shadow: none !important;
}

.leaflet-popup-content {
    margin: 0 !important;
    min-width: 200px;
    max-width: 280px;
    font-family: var(--font-family);
}

.popup-inner {
    padding: 12px;
}

.popup-price {
    font-size: 16px;
    font-weight: 800;
    color: var(--color-brand);
    margin-bottom: 4px;
}

.popup-address {
    font-size: 13px;
    font-weight: 500;
    color: var(--color-text-primary);
    margin-bottom: 6px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.popup-specs {
    font-size: 12px;
    color: var(--color-text-secondary);
    margin-bottom: 8px;
}

.popup-source {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 11px;
    font-weight: 600;
    color: var(--color-brand);
    text-decoration: none;
    padding: 2px 8px;
    border: 1px solid rgba(59, 130, 246, 0.3);
    border-radius: 10px;
    background: rgba(59, 130, 246, 0.08);
    transition: background 0.2s;
}

.popup-source:hover {
    background: rgba(59, 130, 246, 0.15);
}

.popup-source img {
    width: 12px;
    height: 12px;
    border-radius: 2px;
}

/* Close button */
.leaflet-popup-close-button {
    color: var(--color-text-muted) !important;
    font-size: 18px !important;
    padding: 6px 8px 0 0 !important;
}

.leaflet-popup-close-button:hover {
    color: var(--color-text-primary) !important;
}
```

### 3.7 Reset Button Styles (P1-8)

**File**: [`web/static/css/style.css`](../web/static/css/style.css) — add after `.filter-select` styles

```css
/* Reset filters button */
.reset-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    min-width: 32px;
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: var(--radius-pill);
    color: var(--color-text-muted);
    font-size: 14px;
    cursor: pointer;
    transition: border-color 0.2s, background 0.2s, color 0.2s;
    flex-shrink: 0;
}

.reset-btn:hover {
    border-color: var(--color-danger);
    background: rgba(220, 38, 38, 0.1);
    color: var(--color-danger);
}
```

### 3.8 Error State Styles (P1-11)

Already present in [`style.css`](../web/static/css/style.css) — the empty state styles can be reused. Add:

```css
/* Error state */
.error-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 60px 20px;
    text-align: center;
}

.error-state-icon {
    font-size: 48px;
    margin-bottom: 16px;
}

.error-state-title {
    font-size: 18px;
    font-weight: 600;
    color: var(--color-danger);
    margin-bottom: 8px;
}

.error-state-text {
    font-size: 14px;
    color: var(--color-text-muted);
    margin-bottom: 16px;
    max-width: 280px;
}

.error-state-btn {
    padding: 8px 20px;
    background: transparent;
    border: 1px solid var(--color-danger);
    color: var(--color-danger);
    border-radius: var(--radius-button);
    font-family: var(--font-family);
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    transition: background 0.2s;
}

.error-state-btn:hover {
    background: rgba(220, 38, 38, 0.1);
}
```

### 3.9 Responsive Breakpoint 768-1024px (P2-5)

**File**: [`web/static/css/style.css`](../web/static/css/style.css) — add before the existing `@media (max-width: 768px)` block

```css
@media (max-width: 1024px) {
    .left-panel {
        width: 360px;
        min-width: 320px;
    }

    .card-image {
        width: 120px;
        min-width: 120px;
        height: 110px;
    }

    .card-price {
        font-size: 18px;
    }
}
```

### 3.10 Reduced Motion (P2-6)

**File**: [`web/static/css/style.css`](../web/static/css/style.css) — add at end

```css
@media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
        animation-duration: 0.01ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: 0.01ms !important;
    }
}
```

---

## 4. Map UX Recommendations

### 4.1 Dark Map Tiles (P0-2)

**File**: [`web/static/js/map.js`](../web/static/js/map.js) — replace tile layer

```javascript
// BEFORE (line 14-17)
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    maxZoom: 19,
}).addTo(map);

// AFTER — Stadia Alidade Smooth Dark (shows parks, transit, POIs in dark theme)
L.tileLayer('https://tiles.stadiamaps.com/tiles/alidade_smooth_dark/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; <a href="https://stadiamaps.com/">Stadia Maps</a> &copy; <a href="https://openmaptiles.org/">OpenMapTiles</a> &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    maxZoom: 20,
}).addTo(map);
```

**Fallback** (if Stadia requires API key): Use CartoDB Dark Matter:
```javascript
L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/">CARTO</a>',
    maxZoom: 20,
}).addTo(map);
```

> **Note**: The design bible lists CartoDB Dark Matter as a fallback for Stadia. While the anti-pattern section warns against CartoDB Positron (minimal/light), Dark Matter is acceptable as a dark theme fallback.

### 4.2 Price Pill Markers (P0-3)

**File**: [`web/static/js/map.js`](../web/static/js/map.js) — replace marker creation in `addMarkers()`

```javascript
function formatPrice(priceText) {
    // "$5,500/mo" → "$5.5K"
    const match = priceText.match(/\$?([\d,]+)/);
    if (!match) return priceText;
    const num = parseInt(match[1].replace(/,/g, ''));
    if (num >= 1000) {
        const k = num / 1000;
        return '$' + (k % 1 === 0 ? k.toFixed(0) : k.toFixed(1)) + 'K';
    }
    return '$' + num;
}

function createPriceIcon(priceText, isSelected) {
    return L.divIcon({
        className: '',  // Remove default leaflet-div-icon styling
        html: '<div class="price-marker' + (isSelected ? ' selected' : '') + '">' + priceText + '</div>',
        iconSize: null,  // Auto-size based on content
        iconAnchor: [0, 0],  // Will be adjusted by CSS
    });
}

// In addMarkers():
const priceEl = card.querySelector('.card-price');
const priceText = priceEl ? formatPrice(priceEl.textContent.trim()) : '?';
const marker = L.marker([lat, lng], {
    icon: createPriceIcon(priceText, false)
}).addTo(map);
```

### 4.3 Sunnyvale Boundary Overlay (P1-1)

**File**: [`web/static/js/map.js`](../web/static/js/map.js) — add after tile layer

```javascript
// Load Sunnyvale city boundary
fetch('/static/data/sunnyvale-boundary.geojson')
    .then(response => response.json())
    .then(data => {
        L.geoJSON(data, {
            style: {
                color: '#3b82f6',        // Brand blue
                weight: 2,
                opacity: 0.6,
                fillColor: '#3b82f6',
                fillOpacity: 0.04,
                dashArray: '6, 4',       // Subtle dashed line
            }
        }).addTo(map);
    })
    .catch(err => console.warn('Could not load boundary:', err));
```

**Note**: The GeoJSON file is at [`data/sunnyvale-boundary.geojson`](../data/sunnyvale-boundary.geojson). It needs to be served as a static file. Either:
- **Option A**: Copy/symlink to `web/static/data/sunnyvale-boundary.geojson`
- **Option B**: Add a FastAPI route that serves it: `GET /api/boundary`
- **Option C**: Inline the coordinates in `map.js` (not recommended — 2079 lines)

**Recommendation**: Option A — copy the file to `web/static/data/` and serve as static.

### 4.4 Styled Map Popups (P1-6)

**File**: [`web/static/js/map.js`](../web/static/js/map.js) — replace `.bindPopup(price || 'Listing')`

```javascript
function buildPopupContent(card) {
    const price = card.querySelector('.card-price')?.textContent.trim() || 'Price N/A';
    const title = card.querySelector('.card-title')?.textContent.trim() || '';
    const specs = card.querySelector('.card-specs')?.textContent.trim() || '';
    const sourceLink = card.querySelector('.source-pill');
    
    let sourceHtml = '';
    if (sourceLink) {
        const href = sourceLink.getAttribute('href') || '#';
        const sourceName = sourceLink.textContent.trim();
        const sourceImg = sourceLink.querySelector('img');
        const imgHtml = sourceImg ? '<img src="' + sourceImg.src + '" alt="" width="12" height="12">' : '';
        sourceHtml = '<a href="' + href + '" target="_blank" rel="noopener" class="popup-source">' + imgHtml + sourceName + ' ↗</a>';
    }
    
    return '<div class="popup-inner">' +
        '<div class="popup-price">' + price + '</div>' +
        '<div class="popup-address">' + title + '</div>' +
        '<div class="popup-specs">' + specs + '</div>' +
        sourceHtml +
    '</div>';
}

// Usage:
marker.bindPopup(buildPopupContent(card), {
    maxWidth: 280,
    minWidth: 200,
    closeButton: true,
    className: 'sunnynest-popup'
});
```

### 4.5 Card-Map Bidirectional Sync (P1-4)

**File**: [`web/static/js/map.js`](../web/static/js/map.js) — add after marker creation

```javascript
// Store markers by listing ID for bidirectional sync
const markerMap = new Map();

// In addMarkers(), after creating each marker:
const listingId = card.dataset.listingId;
if (listingId) {
    markerMap.set(listingId, { marker, card, lat, lng });
}

// Marker click → highlight card + scroll into view
marker.on('click', function() {
    // Remove previous selection
    document.querySelector('.listing-card.selected')?.classList.remove('selected');
    markerMap.forEach(({ marker: m }) => {
        const el = m.getElement();
        if (el) el.querySelector('.price-marker')?.classList.remove('selected');
    });
    
    // Select this card
    card.classList.add('selected');
    card.scrollIntoView({ behavior: 'smooth', block: 'center' });
    
    // Select this marker
    const markerEl = marker.getElement();
    if (markerEl) markerEl.querySelector('.price-marker')?.classList.add('selected');
});

// Card hover → highlight marker
card.addEventListener('mouseenter', function() {
    const markerEl = marker.getElement();
    if (markerEl) {
        markerEl.querySelector('.price-marker')?.classList.add('selected');
        markerEl.style.zIndex = 1000;
    }
});

card.addEventListener('mouseleave', function() {
    if (!card.classList.contains('selected')) {
        const markerEl = marker.getElement();
        if (markerEl) {
            markerEl.querySelector('.price-marker')?.classList.remove('selected');
            markerEl.style.zIndex = '';
        }
    }
});

// Card click → pan map to marker + open popup
card.addEventListener('click', function() {
    document.querySelector('.listing-card.selected')?.classList.remove('selected');
    card.classList.add('selected');
    map.panTo([lat, lng], { animate: true });
    marker.openPopup();
});
```

### 4.6 Marker Clustering (P1-12)

**File**: [`web/templates/base.html`](../web/templates/base.html) — add Leaflet.markercluster CDN

```html
<!-- After Leaflet CSS -->
<link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css">
<link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css">

<!-- After Leaflet JS -->
<script src="https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js"></script>
```

**File**: [`web/static/js/map.js`](../web/static/js/map.js) — use cluster group

```javascript
// Replace direct map.addTo with cluster group
const clusterGroup = L.markerClusterGroup({
    maxClusterRadius: 40,
    iconCreateFunction: function(cluster) {
        const count = cluster.getChildCount();
        return L.divIcon({
            html: '<div class="marker-cluster"><div>' + count + '</div></div>',
            className: '',
            iconSize: L.point(46, 46),
        });
    },
    spiderfyOnMaxZoom: true,
    showCoverageOnHover: false,
    zoomToBoundsOnClick: true,
});

// In addMarkers(), replace `.addTo(map)` with `.addTo(clusterGroup)`
// After all markers added:
map.addLayer(clusterGroup);
```

---

## 5. Interaction Recommendations

### 5.1 Favorite Toggle (P1-3)

**Current**: Button shows ☆/★ but does nothing on click.

**Target behavior**:
1. Click heart → immediately toggle icon (optimistic UI)
2. Send `POST /api/favorites/{listing_id}` via HTMX
3. If server returns error, revert icon
4. Update `aria-pressed` attribute
5. Heart should be visible on mobile (not just on hover)

**Template change** ([`listing-card.html`](../web/templates/partials/listing-card.html)):

```html
<button class="fav-btn"
        hx-post="/api/favorites/{{ listing.id }}"
        hx-swap="outerHTML"
        hx-target="this"
        aria-label="{{ 'Remove from favorites' if listing.is_favorite else 'Add to favorites' }}"
        aria-pressed="{{ 'true' if listing.is_favorite else 'false' }}"
        title="{{ 'Remove from favorites' if listing.is_favorite else 'Add to favorites' }}">
    {{ '★' if listing.is_favorite else '☆' }}
</button>
```

**CSS change** — make visible on mobile:

```css
/* Always show on touch devices */
@media (hover: none) {
    .fav-btn {
        opacity: 1;
    }
}

/* Increase touch target to 44×44px */
.fav-btn {
    width: 44px;
    height: 44px;
    /* ... existing styles ... */
}
```

### 5.2 Filter Change Feel

**Current**: Cards dim to 50% opacity during HTMX swap.

**Target behavior**:
1. Show skeleton cards immediately (replace content, not dim)
2. New cards fade in with staggered animation
3. Result count updates simultaneously (OOB swap)
4. Map markers update after cards load

**HTMX approach**:

```html
<!-- In dashboard.html — add hx-indicator pointing to skeleton -->
<div id="listing-cards" aria-live="polite"
     hx-indicator="#loading-skeleton">
    {% include "partials/listing-cards.html" %}
</div>

<!-- Hidden skeleton shown during requests -->
<template id="loading-skeleton">
    {% include "partials/listing-skeleton.html" %}
</template>
```

**Card enter animation** (CSS):

```css
.listing-card {
    animation: cardFadeIn 0.3s ease forwards;
    opacity: 0;
}

.listing-card:nth-child(1) { animation-delay: 0ms; }
.listing-card:nth-child(2) { animation-delay: 50ms; }
.listing-card:nth-child(3) { animation-delay: 100ms; }
.listing-card:nth-child(4) { animation-delay: 150ms; }
.listing-card:nth-child(n+5) { animation-delay: 200ms; }

@keyframes cardFadeIn {
    from { opacity: 0; transform: translateY(8px); }
    to { opacity: 1; transform: translateY(0); }
}
```

### 5.3 Result Count OOB Update (P1-7)

When filters change, the result count in the filter bar should update too. Use HTMX out-of-band swaps:

**Template change** ([`dashboard.html`](../web/templates/dashboard.html)):

```html
<div class="result-count" id="result-count">
    <span class="result-count-number">{{ listing_count }}</span> listings
</div>
```

**Partial change** ([`listing-cards.html`](../web/templates/partials/listing-cards.html)):

```html
{% for listing in listings %}
  {% include "partials/listing-card.html" %}
{% endfor %}

{% if not listings %}
<div class="empty-state">
    <div class="empty-state-icon">🏠</div>
    <div class="empty-state-title">No listings found</div>
    <div class="empty-state-text">Try adjusting your filters to see more results.</div>
</div>
{% endif %}

<!-- OOB swap: update result count in filter bar -->
<div id="result-count" hx-swap-oob="innerHTML">
    <span class="result-count-number">{{ listing_count }}</span> listings
</div>
```

### 5.4 Dislike/Hide Listing (P2-1)

**Target behavior**:
1. Dislike button appears on card image hover (next to favorite)
2. Click → card fades out + slides up (300ms animation)
3. `POST /api/dislike/{listing_id}` removes from view
4. Map marker also removed
5. Result count decrements

**Template addition** (in [`listing-card.html`](../web/templates/partials/listing-card.html), after fav-btn):

```html
<button class="dislike-btn"
        hx-post="/api/dislike/{{ listing.id }}"
        hx-target="closest .listing-card"
        hx-swap="outerHTML swap:300ms"
        aria-label="Hide this listing"
        title="Not interested">
    👎
</button>
```

**CSS**:

```css
.dislike-btn {
    position: absolute;
    top: 6px;
    left: 6px;
    width: 32px;
    height: 32px;
    border: none;
    border-radius: 50%;
    background: rgba(0, 0, 0, 0.5);
    color: #fff;
    font-size: 14px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    opacity: 0;
    transition: opacity 0.2s, background 0.2s;
}

.listing-card:hover .dislike-btn {
    opacity: 1;
}

.dislike-btn:hover {
    background: rgba(220, 38, 38, 0.7);
}

/* Fade-out animation for disliked cards */
.listing-card.htmx-swapping {
    opacity: 0;
    transform: translateX(-20px);
    transition: opacity 0.3s ease, transform 0.3s ease;
}
```

---

## 6. Missing Design Elements Checklist

Elements defined in the design bible but not yet in the Phase 0 implementation:

| Element | Design Bible Section | Status | Phase |
|---------|---------------------|--------|-------|
| Price pill map markers | §4 Map → Price Pill Markers | ❌ Missing | P0-3 |
| Sunnyvale boundary overlay | §4 Map → implied by mockup | ❌ Missing | P1-1 |
| Marker clustering | §4 Map → Price Pill Markers | ❌ Missing | P1-12 |
| POI markers (work, school, etc.) | §4 Map → POI Markers | ❌ Missing | Phase 2 |
| Layer control toggle | §4 Map → Layer Control | ❌ Missing | Phase 2 |
| Styled map popups | §4 Map → Map Popups | ❌ Missing | P1-6 |
| Floating result count on map | §4 Map → Floating Result Count | ❌ Missing | P2 |
| Loading skeleton shimmer | §4 Loading States | ❌ Missing | P1-5 |
| Error state with retry | §4 Empty States | ❌ Missing | P1-11 |
| Focus visible states | §5 Accessibility | ❌ Missing | P1-9 |
| `aria-pressed` on favorites | §5 Accessibility | ❌ Missing | P1-3 |
| `prefers-reduced-motion` | §5 Accessibility | ❌ Missing | P2-6 |
| Card selected state | §3 Card Design | ❌ Missing | P1-4 |
| Reset filters button | §3 Filter Bar | ❌ Missing | P1-8 |
| Dislike/hide button | §4 Property Cards (implied) | ❌ Missing | P2-1 |
| Image `onerror` fallback | §4 Property Cards | ❌ Missing | P1-2 |
| Descriptive image alt text | §5 Accessibility | ❌ Missing | P1-10 |
| Card `<article>` semantics | §5 Accessibility | ❌ Missing | P1-10 |
| `aria-live` on result count | §5 Accessibility | ❌ Missing | P1-7 |
| 44×44px touch targets | §5 Accessibility | ❌ Missing | P1-3 |
| Dark theme tile layer | §4 Map → Tile Layers | ❌ Missing | P0-2 |

---

## 7. New Template Partials Needed

### 7.1 `web/templates/partials/listing-skeleton.html`

```html
{# Loading skeleton — shown during HTMX filter requests #}
{% for i in range(4) %}
<div class="skeleton-card" aria-hidden="true">
    <div class="skeleton-thumb"></div>
    <div class="skeleton-details">
        <div class="skeleton-line w60"></div>
        <div class="skeleton-line w80"></div>
        <div class="skeleton-line w40"></div>
        <div class="skeleton-line w50"></div>
    </div>
</div>
{% endfor %}
```

### 7.2 `web/templates/partials/error-state.html`

```html
{# Error state — shown when listing fetch fails #}
<div class="error-state" role="alert">
    <div class="error-state-icon">⚠️</div>
    <div class="error-state-title">Failed to load listings</div>
    <div class="error-state-text">We couldn't fetch the latest listings. Please try again.</div>
    <button class="error-state-btn"
            hx-get="/listings"
            hx-target="#listing-cards"
            hx-include="[name^='filter_']"
            aria-label="Retry loading listings">
        🔄 Retry
    </button>
</div>
```

---

## 8. Implementation Order (Recommended)

### Sprint 1: Visual Foundation (P0 — ~45 min)

1. **P0-1**: Fix left panel width (`flex-shrink: 0`, `width: 440px`)
2. **P0-2**: Switch to dark map tiles (Stadia or CartoDB Dark Matter)
3. **P0-3**: Price pill markers (replace default pins)

### Sprint 2: Map Polish (P1 map — ~2 hrs)

4. **P1-1**: Sunnyvale boundary overlay
5. **P1-6**: Styled map popups
6. **P1-4**: Card-map bidirectional sync
7. **P1-12**: Marker clustering

### Sprint 3: Card & Interaction Polish (P1 cards — ~1.5 hrs)

8. **P1-2**: Image fallback (`onerror`)
9. **P1-3**: Functional favorite toggle (HTMX + API route)
10. **P1-10**: Card semantics (`<article>`, `tabindex`, `aria-label`)
11. **P1-9**: Focus states (`:focus-visible`)

### Sprint 4: States & Filter Polish (P1 states — ~1 hr)

12. **P1-5**: Loading skeleton partial + CSS
13. **P1-11**: Error state partial
14. **P1-7**: Result count OOB update
15. **P1-8**: Reset filters button

### Sprint 5: Enhancement (P2 — ~1.5 hrs)

16. **P2-1**: Dislike button
17. **P2-2**: Active filter visual state
18. **P2-3**: URL-based filter state
19. **P2-4**: Card enter animation
20. **P2-5**: Responsive breakpoint (768-1024px)
21. **P2-6**: `prefers-reduced-motion`

**Total estimated time**: ~7 hours

---

## 9. Acceptance Criteria

### P0 Complete When:
- [ ] Left panel is visually ~440px wide (not compressed to ~20%)
- [ ] Map uses dark tiles matching the UI theme
- [ ] Map markers show price pills ($5.5K, $6K) instead of blue pins

### P1 Complete When:
- [ ] Sunnyvale boundary visible on map as blue dashed outline
- [ ] Broken images show 🏠/🏢 placeholder instead of alt text
- [ ] Favorite button toggles via HTMX and persists
- [ ] Clicking a card highlights the map marker and vice versa
- [ ] Skeleton cards appear during filter loading
- [ ] Map popups show price, address, specs, and source link
- [ ] Result count updates when filters change
- [ ] Reset button clears all filters
- [ ] All interactive elements have visible focus states
- [ ] Cards use `<article>` with proper ARIA attributes
- [ ] Error state shows when listing fetch fails
- [ ] Markers cluster when zoomed out

### P2 Complete When:
- [ ] Dislike button hides listings with animation
- [ ] Active filters have blue tint
- [ ] Filter state reflected in URL
- [ ] Cards animate in on filter change
- [ ] Layout adapts at 768-1024px breakpoint
- [ ] Animations respect `prefers-reduced-motion`

---

*This spec provides copy-paste-ready CSS and JS for the Code mode to implement directly. All values are derived from the design bible and existing mockups. No design decisions need to be made during implementation — just follow the spec.*
