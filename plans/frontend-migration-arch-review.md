# Architecture Review — Frontend Migration (FastAPI + HTMX + Jinja2)

> **Date**: 2026-03-29  
> **Author**: Architect Agent  
> **Status**: REVIEW — technical decisions for owner approval  
> **Reviewed Documents**:  
> - [`plans/frontend-migration.md`](frontend-migration.md) — original migration plan  
> - [`plans/frontend-migration-ux-review.md`](frontend-migration-ux-review.md) — UX Designer review  
> **Design Bible**: [`docs/design/design-bible.md`](../docs/design/design-bible.md)  
> **Source Template**: [`sunnynest-dashboard.html`](../docs/temp/mockups/sunnynest-dashboard.html) (1,324 lines, owner-selected)

---

## Executive Summary

The migration plan is **architecturally sound**. FastAPI + HTMX + Jinja2 is the right choice for this project — it solves the core Streamlit CSS problem while preserving 100% backend reuse. This review addresses 9 engineering concerns not covered in the original plan, proposes a concrete project structure, and incorporates the UX Designer's P0 recommendations into a revised phase plan.

**Key architectural decisions made in this review:**

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | Keep SQLAlchemy (no ORM change) | Zero migration effort; existing models work as-is |
| 2 | Scheduler runs in FastAPI lifespan | Same APScheduler, cleaner lifecycle than Streamlit |
| 3 | Client-side Leaflet.js (drop Folium) | Full API access for price pills, clustering, boundary |
| 4 | Single Uvicorn process (no Gunicorn) | Local single-user app; multi-worker adds complexity for no benefit |
| 5 | `sunnynest-dashboard.html` is the template | Owner-selected; 1,324-line dark-theme mockup with all states |
| 6 | Custom CSS (no framework) | Mockup already has production-quality CSS with design tokens |
| 7 | `web/` directory for all FastAPI code | Clean separation from existing `src/` backend |
| 8 | Responsive breakpoints in Phase 1 | Per UX review — core layout must work at all sizes from day one |
| 9 | SQLite `check_same_thread=False` sufficient | Already configured; no concurrent write pressure in single-user app |

---

## 1. Project Structure

### Proposed File Tree

```
zillow/
├── web/                              # ← NEW: All FastAPI frontend code
│   ├── __init__.py
│   ├── main.py                       # FastAPI app factory + lifespan
│   ├── config.py                     # FastAPI-specific settings (port, debug, etc.)
│   ├── dependencies.py               # Shared dependencies (get_db, get_config, etc.)
│   │
│   ├── routes/                       # Route modules (one per domain)
│   │   ├── __init__.py
│   │   ├── dashboard.py              # GET / — main dashboard page
│   │   ├── listings.py               # GET /listings — HTMX partial (filtered cards)
│   │   ├── actions.py                # POST /favorite/{id}, POST /dislike/{id}
│   │   ├── stream.py                 # GET /stream/listings — SSE endpoint
│   │   └── admin.py                  # GET /admin/* — all backoffice routes
│   │
│   ├── templates/                    # Jinja2 templates
│   │   ├── base.html                 # <html>, <head>, CSS/JS includes, dark theme
│   │   ├── dashboard.html            # Extends base — filter bar + split panel
│   │   ├── partials/                 # HTMX-swappable fragments
│   │   │   ├── listing-cards.html    # All cards container (swap target for filters)
│   │   │   ├── listing-card.html     # Single card (swap target for fav toggle)
│   │   │   ├── listing-skeleton.html # 3-4 skeleton shimmer cards
│   │   │   ├── result-summary.html   # "23 listings · sorted by newest"
│   │   │   ├── map-data.html         # JSON script block for Leaflet markers
│   │   │   ├── toast.html            # SSE new-listing toast notification
│   │   │   ├── empty-state.html      # No results + reset button
│   │   │   └── error-state.html      # Load failure + retry button
│   │   └── admin/                    # Backoffice templates
│   │       ├── base.html             # Admin layout with sidebar nav
│   │       ├── dashboard.html        # KPIs page
│   │       ├── analytics.html        # Listing analytics
│   │       ├── api-usage.html        # API call tracking
│   │       ├── notifications.html    # Notification history
│   │       └── settings.html         # Email/config settings
│   │
│   └── static/                       # Static assets (served by FastAPI)
│       ├── css/
│       │   ├── tokens.css            # Design tokens (CSS variables from design bible)
│       │   ├── reset.css             # Box-sizing, margin reset, font smoothing
│       │   ├── layout.css            # Split panel, filter bar, responsive breakpoints
│       │   ├── components/
│       │   │   ├── card.css          # Listing card (horizontal, hover, selected, skeleton)
│       │   │   ├── filter.css        # Filter selects, pills, active states
│       │   │   ├── map.css           # Map container, popups, price pills
│       │   │   ├── badge.css         # Status badges, source pills
│       │   │   ├── button.css        # Favorite, dislike, action buttons
│       │   │   ├── toast.css         # SSE notification toasts
│       │   │   └── states.css        # Empty, error, loading states
│       │   └── admin.css             # Backoffice-specific styles
│       ├── js/
│       │   ├── map.js                # Leaflet initialization, markers, clustering
│       │   ├── htmx-hooks.js         # aria-busy, focus management, map sync
│       │   └── theme.js              # Dark/light toggle (localStorage)
│       └── img/
│           └── (favicons, logos)
│
├── src/                              # ← UNCHANGED: Backend library
│   ├── database.py                   # SQLAlchemy queries (1,351 lines)
│   ├── models.py                     # ORM models (290 lines)
│   ├── orchestrator.py               # Scraper coordination (314 lines)
│   ├── scheduler.py                  # APScheduler (197 lines)
│   ├── notifier.py                   # Email notifications (503 lines)
│   ├── dedup.py                      # Cross-source deduplication
│   ├── geocoder.py                   # Address → lat/lng
│   ├── school_districts.py           # ZIP → school district
│   ├── utils.py                      # Shared utilities
│   └── scrapers/                     # Adapter pattern scrapers
│       ├── base.py
│       ├── zillow_scraper.py
│       └── craigslist_scraper.py
│
├── data/
│   ├── listings.db                   # SQLite database
│   └── sunnyvale-boundary.geojson    # City boundary for map overlay
│
├── config.yaml                       # App configuration (unchanged)
├── requirements.txt                  # Updated: -streamlit +fastapi +uvicorn
├── scripts/
│   ├── start-dashboard.sh            # Updated: uvicorn instead of streamlit
│   └── ...
├── app.py.backup-streamlit           # Archived Streamlit dashboard
└── backoffice.py.backup-streamlit    # Archived Streamlit backoffice
```

### Key Structural Decisions

**Why `web/` and not modify `src/`?**

The `src/` directory is a clean Python library with zero framework imports. It contains database queries, ORM models, scrapers, and business logic. Mixing FastAPI route handlers into `src/` would violate this clean separation. The `web/` directory owns everything HTTP-related: routes, templates, static assets. It imports from `src/` but `src/` never imports from `web/`.

```
web/ ──imports──► src/ ──imports──► SQLite
 │                 │
 │                 ├── database.py (queries)
 │                 ├── models.py (ORM)
 │                 └── scheduler.py (APScheduler)
 │
 ├── routes/ (HTTP handlers)
 ├── templates/ (Jinja2 HTML)
 └── static/ (CSS/JS/images)
```

**Why separate route files instead of one big `main.py`?**

The current [`app.py`](../app.py) is 1,506 lines — a monolith. Splitting routes by domain prevents this:

| Route Module | Responsibility | Endpoints |
|-------------|---------------|-----------|
| [`dashboard.py`](../web/routes/dashboard.py) | Full page renders | `GET /` |
| [`listings.py`](../web/routes/listings.py) | HTMX partials for listing data | `GET /listings`, `GET /listings/{id}` |
| [`actions.py`](../web/routes/actions.py) | User actions (favorite, dislike) | `POST /favorite/{id}`, `POST /dislike/{id}` |
| [`stream.py`](../web/routes/stream.py) | SSE real-time updates | `GET /stream/listings` |
| [`admin.py`](../web/routes/admin.py) | Backoffice pages + actions | `GET /admin/*`, `POST /admin/settings` |

---

## 2. Backend Integration

### Strategy: Direct Python Imports (No API Layer)

The `src/` backend has **zero Streamlit imports** — confirmed by inspection of all 11 source files. Every function in [`src/database.py`](../src/database.py) returns SQLAlchemy ORM objects or plain Python types. FastAPI routes import directly:

```python
# web/routes/listings.py
from src.database import get_filtered_listings, toggle_favorite, toggle_dislike
from src.models import Listing

@router.get("/listings")
async def get_listings(request: Request, beds: int = None, ...):
    filters = _build_filters(beds=beds, ...)
    listings = get_filtered_listings(filters)
    return templates.TemplateResponse("partials/listing-cards.html", {
        "request": request,
        "listings": listings,
    })
```

**Why NOT an API layer (REST/JSON)?**

| Approach | Pros | Cons |
|----------|------|------|
| Direct imports ✅ | Zero overhead, type-safe, no serialization | Tighter coupling (acceptable for monolith) |
| REST API layer | Decoupled, could serve React later | Unnecessary indirection for single-user local app; doubles code |

An API layer would make sense if we planned to serve a React/mobile frontend later. For a local single-user tool with HTMX (server-rendered HTML), direct imports are the right call. The `src/` functions are already well-documented with type hints and docstrings.

### Integration Points

| `src/` Module | How FastAPI Uses It | Changes Needed |
|--------------|-------------------|----------------|
| [`database.py`](../src/database.py) | Direct import of query functions | **None** — `get_filtered_listings()`, `toggle_favorite()`, etc. work as-is |
| [`models.py`](../src/models.py) | ORM objects passed to Jinja2 templates | **None** — templates access `listing.price`, `listing.sources`, etc. |
| [`orchestrator.py`](../src/orchestrator.py) | Called by scheduler; manual sync button | **None** — `run_sync_blocking()` works from any caller |
| [`scheduler.py`](../src/scheduler.py) | Started in FastAPI lifespan event | **Minor** — move startup from `st.session_state` to `lifespan()` |
| [`notifier.py`](../src/notifier.py) | Called by scheduler (unchanged) | **None** |
| [`utils.py`](../src/utils.py) | `load_config()`, `setup_logging()` | **None** |
| [`dedup.py`](../src/dedup.py) | Called by orchestrator (unchanged) | **None** |

**Total backend changes: ~10 lines** (scheduler startup location only).

---

## 3. Database Layer

### Decision: Keep SQLAlchemy + Raw SQL Hybrid (No Change)

The current [`src/database.py`](../src/database.py) (1,351 lines) uses **SQLAlchemy ORM** for all queries — not raw SQL. It already has:

- ✅ Declarative models in [`src/models.py`](../src/models.py) (5 tables: `Listing`, `ListingSource`, `PriceHistory`, `ApiCallLog`, `NotificationLog`)
- ✅ Session management via context manager ([`get_session()`](../src/database.py:128))
- ✅ `check_same_thread=False` on SQLite engine ([line 53](../src/database.py:53))
- ✅ Eager loading with `selectinload` for relationships
- ✅ Idempotent migrations (`_ensure_days_on_market_column()`, `_migrate_to_listing_sources()`)

**Should we add a full ORM migration tool (Alembic)?**

| Option | Effort | Benefit |
|--------|--------|---------|
| Keep current approach (manual `ALTER TABLE` + `INSERT OR IGNORE`) | 0h | Works fine for 5 tables, solo developer |
| Add Alembic | 3-4h setup | Overkill — we have 5 tables and schema changes are rare |

**Recommendation: No.** The current manual migration approach is sufficient. Alembic adds complexity (migration files, `alembic.ini`, `env.py`) that isn't justified for a 5-table SQLite database with infrequent schema changes.

### SQLite Concurrency Concern

FastAPI is async, but SQLAlchemy's synchronous session is used throughout `src/database.py`. This is fine because:

1. **Single-user app** — no concurrent write pressure
2. **`check_same_thread=False`** already configured on the engine
3. **SQLite WAL mode** could be enabled for better read concurrency if needed (one-line change)
4. **No async SQLAlchemy needed** — the overhead of migrating to `async_session` isn't justified

If performance becomes an issue (unlikely for 23 listings), the fix is:
```python
# Add to get_engine() — enables concurrent reads
engine.execute("PRAGMA journal_mode=WAL")
```

### FastAPI + Synchronous SQLAlchemy

FastAPI routes calling synchronous `src/database` functions will block the event loop. For a single-user local app this is imperceptible. If needed, wrap in `run_in_executor`:

```python
# Only if blocking becomes noticeable (unlikely)
import asyncio
listings = await asyncio.to_thread(get_filtered_listings, filters)
```

**Recommendation**: Start synchronous. Add `asyncio.to_thread()` only if profiling shows blocking.

---

## 4. Scheduler Integration

### Decision: APScheduler in FastAPI Lifespan (Same Thread Model)

The current [`ScrapeScheduler`](../src/scheduler.py) uses `BackgroundScheduler(daemon=True)` — it runs in a background thread, not the main thread. This works identically in FastAPI:

```python
# web/main.py
from contextlib import asynccontextmanager
from src.scheduler import ScrapeScheduler
from src.utils import load_config

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start scheduler on app startup, stop on shutdown."""
    config = load_config()
    interval = config.get("schedule", {}).get("interval_hours", 6)
    
    scheduler = ScrapeScheduler(interval_hours=interval)
    scheduler.start()
    app.state.scheduler = scheduler  # Accessible in routes for manual sync
    
    yield  # App runs here
    
    scheduler.stop()

app = FastAPI(lifespan=lifespan)
```

**Why this is better than Streamlit's approach:**

| Aspect | Streamlit (current) | FastAPI (proposed) |
|--------|--------------------|--------------------|
| Lifecycle | `st.session_state` — restarts on page refresh | `lifespan` — starts once, stops on shutdown |
| Multiple tabs | Each tab creates a new scheduler instance | Single scheduler for the entire app |
| Graceful shutdown | No cleanup — daemon thread dies with process | `scheduler.stop()` called explicitly |
| Manual sync | `scheduler.run_now()` via button callback | Same — `request.app.state.scheduler.run_now()` |

**No separate process needed.** APScheduler's `BackgroundScheduler` is designed to run in-process. A separate process (e.g., Celery worker) would add deployment complexity for zero benefit in a single-user app.

### Manual Sync Button

The dashboard's "Sync Now" button triggers an immediate scrape. In FastAPI:

```python
# web/routes/dashboard.py
@router.post("/sync")
async def trigger_sync(request: Request):
    scheduler = request.app.state.scheduler
    scheduler.run_now()  # Runs in background thread
    return templates.TemplateResponse("partials/sync-status.html", {
        "request": request,
        "message": "Scrape started in background...",
    })
```

The HTMX button:
```html
<button hx-post="/sync" hx-target="#sync-status" hx-swap="innerHTML">
  🔄 Sync Now
</button>
```

---

## 5. Map Implementation

### Decision: Client-Side Leaflet.js (Drop Folium Entirely)

The current stack uses Folium (Python) → generates HTML → `streamlit-folium` renders it. This is a triple abstraction layer. With FastAPI, we go direct:

```
Current:  Python → Folium → HTML → streamlit-folium → iframe → Leaflet.js
Proposed: Python → JSON data → Leaflet.js (direct)
```

### Architecture

The map is initialized once on page load and updated via JavaScript when filters change. The server provides listing data as JSON; the client renders markers.

**Server side** — FastAPI provides marker data as a JSON script block in the HTML:

```python
# web/routes/dashboard.py
@router.get("/")
async def dashboard(request: Request):
    listings = get_filtered_listings({"is_active": True, "exclude_disliked": True})
    markers = [
        {
            "id": l.id,
            "lat": l.latitude,
            "lng": l.longitude,
            "price": l.price,
            "label": _format_price_label(l.price),
            "address": l.address,
            "beds": l.bedrooms,
            "baths": l.bathrooms,
        }
        for l in listings if l.latitude and l.longitude
    ]
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "listings": listings,
        "markers_json": json.dumps(markers),
        "boundary_geojson": _load_sunnyvale_boundary(),
    })
```

**Client side** — [`map.js`](../web/static/js/map.js) handles all map logic:

```javascript
// web/static/js/map.js — Key responsibilities:
// 1. Initialize Leaflet map with tile layer
// 2. Load GeoJSON city boundary
// 3. Create price pill markers (DivIcon)
// 4. Marker clustering (Leaflet.markercluster)
// 5. Bidirectional card ↔ marker sync
// 6. Update markers when HTMX swaps listing cards
```

### Price Pill Markers

Currently generated by Folium's `DivIcon` in [`app.py`](../app.py). In Leaflet.js directly:

```javascript
function createPricePill(listing) {
    return L.marker([listing.lat, listing.lng], {
        icon: L.divIcon({
            className: 'price-pill',
            html: `<span>$${listing.label}</span>`,
            iconSize: [60, 24],
            iconAnchor: [30, 12],
        })
    });
}
```

CSS for price pills (from design bible):
```css
.price-pill {
    background: #3b82f6;
    color: white;
    font-size: 11px;
    font-weight: 700;
    border-radius: 12px;
    padding: 2px 8px;
    box-shadow: 0 2px 8px rgba(59, 130, 246, 0.3);
    white-space: nowrap;
}
.price-pill.selected {
    background: #1d4ed8;
    transform: scale(1.1);
    z-index: 1000;
}
```

### GeoJSON Boundary

The [`sunnyvale-boundary.geojson`](../data/sunnyvale-boundary.geojson) file is loaded server-side and embedded in the template as a `<script>` tag, or served as a static file and fetched by Leaflet:

```javascript
// Option A: Embedded in template (faster, no extra request)
const boundary = JSON.parse(document.getElementById('boundary-data').textContent);
L.geoJSON(boundary, { style: { color: '#3b82f6', weight: 2, fillOpacity: 0.05 } }).addTo(map);
```

### Marker Clustering

Use [Leaflet.markercluster](https://github.com/Leaflet/Leaflet.markercluster) (12KB CDN):

```javascript
const clusterGroup = L.markerClusterGroup({
    maxClusterRadius: 40,
    spiderfyOnMaxZoom: true,
    showCoverageOnHover: false,
});
markers.forEach(m => clusterGroup.addLayer(createPricePill(m)));
map.addLayer(clusterGroup);
```

### Map-Card Bidirectional Sync (Phase 1 — per UX review)

```javascript
// Card click → highlight marker
document.addEventListener('click', (e) => {
    const card = e.target.closest('[data-listing-id]');
    if (card) highlightMarker(card.dataset.listingId);
});

// Marker click → scroll to card
marker.on('click', () => {
    const card = document.querySelector(`[data-listing-id="${listing.id}"]`);
    card?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    card?.classList.add('selected');
});
```

### Map Update on Filter Change

When HTMX swaps the listing cards, the map markers must also update. Use HTMX's `afterSwap` event:

```javascript
document.body.addEventListener('htmx:afterSwap', (e) => {
    if (e.detail.target.id === 'listing-cards') {
        // The server includes updated marker JSON in a <script> tag within the partial
        const markerData = JSON.parse(
            document.getElementById('marker-data').textContent
        );
        updateMapMarkers(markerData);
    }
});
```

**Alternative approach**: The HTMX partial response for `/listings` includes a hidden `<script id="marker-data" type="application/json">` block with the marker JSON. This avoids a separate API call for map data.

---

## 6. HTMX Endpoint Patterns

### Complete Endpoint Map

| User Action | HTTP Method | Endpoint | HTMX Target | Response | Swap Strategy |
|------------|-------------|----------|-------------|----------|---------------|
| Page load | `GET` | `/` | — | Full `dashboard.html` | Full page |
| Change filter | `GET` | `/listings?beds=3&min_price=5000&...` | `#listing-cards` | `listing-cards.html` partial + marker JSON | `innerHTML` |
| Sort change | `GET` | `/listings?sort=price_asc&...` | `#listing-cards` | `listing-cards.html` partial | `innerHTML` |
| Toggle favorite | `POST` | `/favorite/{id}` | `#fav-btn-{id}` | Updated button HTML | `outerHTML` |
| Dislike listing | `POST` | `/dislike/{id}` | `#card-{id}` | Empty (card removed) | `outerHTML` with delete swap |
| Reset filters | `GET` | `/listings` (no params) | `#listing-cards` | `listing-cards.html` partial | `innerHTML` |
| Manual sync | `POST` | `/sync` | `#sync-status` | Status message | `innerHTML` |
| SSE new listings | `GET` | `/stream/listings` | `#sse-toast` | `toast.html` partial | SSE swap |
| Admin pages | `GET` | `/admin/`, `/admin/analytics`, etc. | — | Full admin page | Full page |
| Save settings | `POST` | `/admin/settings` | `#settings-form` | Updated form with success message | `outerHTML` |

### Filter Endpoint Detail

The `/listings` endpoint accepts all filter parameters as query strings and returns an HTML fragment:

```python
# web/routes/listings.py
@router.get("/listings")
async def filtered_listings(
    request: Request,
    beds_min: int | None = None,
    beds_max: int | None = None,
    price_min: int | None = None,
    price_max: int | None = None,
    sort: str = "newest",
    source: str | None = None,
):
    filters = {}
    if beds_min: filters["min_bedrooms"] = beds_min
    if beds_max: filters["max_bedrooms"] = beds_max
    if price_min: filters["min_price"] = price_min
    if price_max: filters["max_price"] = price_max
    if source: filters["source"] = source
    filters["is_active"] = True
    filters["exclude_disliked"] = True

    listings = get_filtered_listings(filters)
    
    # Sort
    if sort == "price_asc":
        listings.sort(key=lambda l: l.price)
    elif sort == "price_desc":
        listings.sort(key=lambda l: l.price, reverse=True)
    # default: newest (already sorted by last_seen desc from DB)

    # Prepare marker data for map update
    markers = [...]  # Same as dashboard route

    return templates.TemplateResponse("partials/listing-cards.html", {
        "request": request,
        "listings": listings,
        "markers_json": json.dumps(markers),
        "count": len(listings),
    })
```

### HTMX Filter Bar HTML

```html
<!-- Filter bar — each select triggers HTMX GET -->
<div class="filter-bar">
    <div class="brand">🏠 <span class="brand-name">SunnyNest</span></div>
    
    <select name="beds_min" class="filter-select"
            hx-get="/listings" 
            hx-target="#listing-cards" 
            hx-include=".filter-select"
            hx-push-url="true"
            hx-indicator="#loading-indicator">
        <option value="">Beds</option>
        <option value="3">3+ beds</option>
        <option value="4">4+ beds</option>
    </select>
    
    <!-- Similar for price, sort, source -->
    
    <button class="reset-btn" 
            hx-get="/listings" 
            hx-target="#listing-cards"
            hx-push-url="true"
            aria-label="Reset filters">
        ↺
    </button>
</div>
```

### Favorite Toggle Pattern

```html
<!-- In listing-card.html partial -->
<button id="fav-btn-{{ listing.id }}"
        class="fav-btn {{ 'active' if listing.is_favorite }}"
        hx-post="/favorite/{{ listing.id }}"
        hx-swap="outerHTML"
        aria-pressed="{{ 'true' if listing.is_favorite else 'false' }}"
        aria-label="{{ 'Remove from favorites' if listing.is_favorite else 'Add to favorites' }}">
    {{ '♥' if listing.is_favorite else '♡' }}
</button>
```

Server returns the updated button HTML with toggled state.

### Dislike Pattern (Card Removal with Animation)

```html
<article id="card-{{ listing.id }}" 
         class="listing-card"
         data-listing-id="{{ listing.id }}">
    <!-- card content -->
    <button class="dislike-btn"
            hx-post="/dislike/{{ listing.id }}"
            hx-target="#card-{{ listing.id }}"
            hx-swap="outerHTML swap:300ms"
            hx-on::before-request="this.closest('.listing-card').classList.add('fade-out')"
            aria-label="Hide this listing">
        ✕
    </button>
</article>
```

The server returns empty string; HTMX removes the card after the CSS fade-out animation (300ms).

---

## 7. Deployment

### Decision: Single Uvicorn Process (No Gunicorn)

| Option | Workers | Use Case | Verdict |
|--------|---------|----------|---------|
| `uvicorn web.main:app` | 1 | Local single-user | ✅ **Recommended** |
| `gunicorn -w 4 -k uvicorn.workers.UvicornWorker` | 4 | Production multi-user | ❌ Overkill |

**Rationale**: This is a localhost-only, single-user application. Multiple workers would:
- Create multiple scheduler instances (duplicate scrapes)
- Require inter-process coordination for SQLite writes
- Add deployment complexity for zero benefit

### Updated launchd Configuration

The [`com.sunnynest.dashboard.plist`](../com.sunnynest.dashboard.plist) changes from Streamlit to Uvicorn:

```xml
<!-- Before (Streamlit) -->
<string>/opt/homebrew/opt/python@3.14/bin/python3.14</string>
<string>-m</string>
<string>streamlit</string>
<string>run</string>
<string>app.py</string>
<string>--server.headless</string>
<string>true</string>
<string>--server.port</string>
<string>8501</string>
<string>--server.address</string>
<string>localhost</string>

<!-- After (Uvicorn) -->
<string>/opt/homebrew/opt/python@3.14/bin/python3.14</string>
<string>-m</string>
<string>uvicorn</string>
<string>web.main:app</string>
<string>--host</string>
<string>localhost</string>
<string>--port</string>
<string>8501</string>
```

### Port Decision

**Keep port 8501.** Changing ports would break:
- Browser bookmarks
- Email notification links (`dashboard_url` in [`config.yaml`](../config.yaml))
- Any muscle memory

### Backoffice Consolidation

The [`com.sunnynest.backoffice.plist`](../com.sunnynest.backoffice.plist) is **eliminated**. The backoffice runs on the same FastAPI server at `/admin/`. This removes:
- One launchd service
- One process to monitor
- Port 8502 allocation

### Updated Start Script

```bash
#!/usr/bin/env bash
# scripts/start-dashboard.sh — Updated for FastAPI
set -euo pipefail

PROJECT_DIR="/Users/mvaturri/Documents/zillow"
VENV_DIR="${PROJECT_DIR}/.venv"

cd "${PROJECT_DIR}"
source "${VENV_DIR}/bin/activate"

exec uvicorn web.main:app \
    --host localhost \
    --port 8501 \
    --log-level info
```

### Updated Requirements

```
# Remove:
# streamlit>=1.30.0
# streamlit-folium>=0.18.0
# folium>=0.15.0

# Add:
fastapi>=0.109.0
uvicorn[standard]>=0.27.0
jinja2>=3.1.0
python-multipart>=0.0.6
sse-starlette>=1.8.0    # For SSE support

# Keep:
sqlalchemy>=2.0.0
httpx>=0.25.0
beautifulsoup4>=4.12.0
apscheduler>=3.10.0
pyyaml>=6.0.0
geopy>=2.4.0
lxml>=4.9.0

# Remove (no longer needed):
# plotly>=5.18.0         # Charts were Streamlit-only; backoffice uses SVG charts from mockup
# pandas>=2.1.0          # Only used by Streamlit charts
# playwright>=1.40.0     # Not used (Zillow uses API, not browser scraping)
```

---

## 8. Testing Strategy

### Layered Testing Approach

| Layer | Tool | What It Tests | Priority |
|-------|------|--------------|----------|
| **Unit** | `pytest` | `src/` functions (already testable) | P1 — existing |
| **Route** | `pytest` + `httpx.AsyncClient` (TestClient) | FastAPI endpoints return correct HTML/status | P1 — new |
| **Template** | `pytest` + Jinja2 render | Templates render without errors with sample data | P2 — new |
| **Integration** | `pytest` + TestClient | Full request → DB → template → response cycle | P1 — new |
| **E2E** | Playwright | Browser-based: filters work, map loads, favorites toggle | P2 — Phase 3 |
| **Visual** | Manual + screenshots | Compare FastAPI output to mockup | P1 — during dev |

### FastAPI TestClient Example

```python
# tests/test_routes.py
from fastapi.testclient import TestClient
from web.main import app

client = TestClient(app)

def test_dashboard_loads():
    response = client.get("/")
    assert response.status_code == 200
    assert "SunnyNest" in response.text
    assert "listing-cards" in response.text

def test_listings_partial():
    response = client.get("/listings?beds_min=3")
    assert response.status_code == 200
    assert "listing-card" in response.text  # Contains card HTML

def test_favorite_toggle():
    response = client.post("/favorite/1")
    assert response.status_code == 200
    assert "fav-btn" in response.text

def test_admin_dashboard():
    response = client.get("/admin/")
    assert response.status_code == 200
```

### What NOT to Test

- **Leaflet.js map rendering** — client-side JS; test via Playwright E2E only
- **CSS layout** — visual; verify manually against mockup
- **HTMX swap behavior** — framework responsibility; test endpoints return correct HTML

### Recommended Test Structure

```
tests/
├── conftest.py              # Fixtures: test DB, sample listings
├── test_database.py         # Existing src/database.py tests
├── test_routes/
│   ├── test_dashboard.py    # GET / tests
│   ├── test_listings.py     # GET /listings filter tests
│   ├── test_actions.py      # POST /favorite, /dislike tests
│   └── test_admin.py        # GET /admin/* tests
└── test_templates/
    └── test_partials.py     # Template rendering tests
```

---

## 9. Migration Risk & Rollback Strategy

### Risk Matrix (Updated)

| Risk | Likelihood | Impact | Mitigation | Owner |
|------|-----------|--------|------------|-------|
| **HTMX learning curve** | Medium | Low | 14KB library, simple API; 1-2h tutorial | Developer |
| **Leaflet map complexity** | Medium | Medium | Extract marker logic from existing Folium code in `app.py` | Developer |
| **SQLite blocking in async** | Low | Low | Single-user; add `asyncio.to_thread()` if needed | Developer |
| **Scheduler double-start** | Low | High | Lifespan ensures single instance; add guard in `ScrapeScheduler.start()` | Developer |
| **Template extraction errors** | Medium | Medium | Test each partial independently; compare output to mockup | Developer |
| **CSS regression** | Medium | Medium | Mockup CSS is the source of truth; diff against it | Developer |
| **Broken favorites/dislikes** | Low | High | TestClient integration tests for all action endpoints | Developer |
| **launchd service failure** | Low | Medium | Test plist changes on dev machine before committing | Developer |
| **Data loss during migration** | None | Critical | Database is untouched; `src/` is untouched | N/A |

### Rollback Strategy

**The migration is inherently safe** because:

1. **Database is untouched** — same SQLite file, same ORM models, same queries
2. **Backend is untouched** — `src/` has zero changes (except 10 lines in scheduler startup)
3. **Streamlit backups exist** — `app.py.backup-streamlit` and `backoffice.py.backup-streamlit`

**Rollback procedure** (5 minutes):

```bash
# 1. Stop FastAPI
launchctl unload ~/Library/LaunchAgents/com.sunnynest.dashboard.plist

# 2. Restore Streamlit files
cp app.py.backup-streamlit app.py
cp backoffice.py.backup-streamlit backoffice.py

# 3. Restore Streamlit plist
# (keep a backup of the FastAPI plist)
cp com.sunnynest.dashboard.plist.streamlit-backup com.sunnynest.dashboard.plist

# 4. Reinstall Streamlit deps
pip install streamlit streamlit-folium folium

# 5. Restart
launchctl load ~/Library/LaunchAgents/com.sunnynest.dashboard.plist
```

### Parallel Running Strategy

During development (Phases 0–3), run both:

| App | Port | Purpose |
|-----|------|---------|
| Streamlit (current) | 8501 | Production — daily use |
| FastAPI (new) | 8000 | Development — testing |

Switch ports only after Phase 3 smoke test passes. This means zero downtime during migration.

---

## 10. Revised Phase Plan (Incorporating UX Feedback)

### Phase 0: Foundation (4–5 hours)

**Goal**: FastAPI server running with one working page

- [ ] Install dependencies: `fastapi`, `uvicorn`, `jinja2`, `python-multipart`, `sse-starlette`
- [ ] Create `web/` directory structure (as defined in §1)
- [ ] Create `web/main.py` with FastAPI app factory + lifespan (scheduler startup)
- [ ] Extract CSS from [`sunnynest-dashboard.html`](../docs/temp/mockups/sunnynest-dashboard.html) into `web/static/css/` files:
  - `tokens.css` — design tokens (lines 14–47 of mockup)
  - `reset.css` — reset + base styles (lines 49–98)
  - `layout.css` — filter bar + split panel (lines 100–208)
  - `components/card.css` — listing card styles (lines 242–500+)
  - `components/states.css` — empty, error, loading states
- [ ] Convert mockup HTML → `base.html` + `dashboard.html` Jinja2 templates
- [ ] Wire up `src/database.py` imports in dashboard route
- [ ] Verify: homepage loads at `localhost:8000` with static content from database
- [ ] **Accessibility foundation** (P0 from UX review):
  - `aria-live="polite"` on listing cards container and result count
  - `aria-busy` toggle during HTMX requests (global JS event listener)
  - Skip link: "Skip to listings" before map
  - Semantic card markup (`article`, `tabindex="0"`, `aria-label`)

### Phase 1: Dashboard Core (10–12 hours)

**Goal**: Feature parity with current Streamlit dashboard + UX improvements

- [ ] **Filter bar**: HTMX-powered selects with `hx-get="/listings"`, `hx-include`, `hx-push-url="true"`
- [ ] **Listing cards**: Jinja2 partial template (`listing-card.html`), rendered server-side, swapped via HTMX
- [ ] **Favorites/dislikes**: HTMX `hx-post` buttons with `aria-pressed`, 44×44px touch targets
- [ ] **Sort**: HTMX-powered sort dropdown
- [ ] **Image lazy loading**: Native `loading="lazy"` attribute
- [ ] **Loading skeletons**: `listing-skeleton.html` partial with shimmer animation (not spinner)
- [ ] **Map**: Leaflet.js with:
  - Price pill markers (DivIcon)
  - City boundary GeoJSON overlay
  - Marker clustering (Leaflet.markercluster)
  - **Bidirectional card ↔ marker sync** (moved from Phase 3 per UX review)
- [ ] **Responsive breakpoints** (moved from Phase 3 per UX review):
  - `> 1024px`: Full split-panel (42% listings + flexible map)
  - `768–1024px`: Narrower panel (360px)
  - `< 768px`: Stacked layout (listings top, map bottom)
- [ ] **Focus management**: Restore focus to first card after HTMX content swap
- [ ] **Dark theme**: CSS variables from design bible, dark as default
- [ ] **Result count**: `aria-live` region showing "X listings found"
- [ ] **Empty state**: No results message + reset filters button
- [ ] **Error state**: Load failure message + retry button
- [ ] **Route tests**: TestClient tests for all endpoints

### Phase 2: Backoffice (6–8 hours)

**Goal**: Backoffice feature parity on same server

- [ ] Convert [`backoffice.html`](../docs/temp/mockups/backoffice.html) mockup → Jinja2 templates under `templates/admin/`
- [ ] Dashboard KPIs page (`GET /admin/`)
- [ ] Listing Analytics page (`GET /admin/analytics`)
- [ ] API Usage page (`GET /admin/api-usage`)
- [ ] Notifications page (`GET /admin/notifications`)
- [ ] Settings page (`GET /admin/settings`, `POST /admin/settings`)
- [ ] Admin link in dashboard footer: `<a href="/admin/">Admin →</a>`
- [ ] Route tests for all admin endpoints

### Phase 3: Real-time & Polish (4–6 hours)

**Goal**: Features that exceed current Streamlit capabilities

- [ ] **SSE for new listings**: `/stream/listings` endpoint with toast notification pattern
  - Toast: "🏠 3 new listings found [View ↑]" — batch, don't auto-insert
  - `aria-live="polite"` on toast container
  - Auto-dismiss after 10 seconds
- [ ] **URL-based filter state**: Already implemented via `hx-push-url="true"` in Phase 1; add server-side parsing of URL params on page load
- [ ] **Card animations**: Staggered fade-in on filter change, fade-out on dislike
- [ ] **Theme toggle**: Dark/light switch with `localStorage` persistence
- [ ] **Keyboard navigation**: Arrow keys within card feed (Tab navigation already in Phase 1)
- [ ] **Map tile theme matching**: Stadia dark tiles for dark theme, Stadia Outdoors for light

### Phase 4: Cutover & Cleanup (3–4 hours)

**Goal**: Replace Streamlit entirely

- [ ] Update [`scripts/start-dashboard.sh`](../scripts/start-dashboard.sh) → `uvicorn web.main:app`
- [ ] Update [`com.sunnynest.dashboard.plist`](../com.sunnynest.dashboard.plist) → Uvicorn args
- [ ] Remove [`com.sunnynest.backoffice.plist`](../com.sunnynest.backoffice.plist) (backoffice is same server)
- [ ] Update [`requirements.txt`](../requirements.txt): remove `streamlit`, `streamlit-folium`, `folium`, `plotly`, `pandas`, `playwright`; add `fastapi`, `uvicorn`, `jinja2`, `python-multipart`, `sse-starlette`
- [ ] Archive `app.py` → `app.py.backup-streamlit`
- [ ] Archive `backoffice.py` → `backoffice.py.backup-streamlit`
- [ ] Update [`config.yaml`](../config.yaml): `dashboard_url` stays `http://localhost:8501`
- [ ] Update [`plans/architecture.md`](architecture.md): new tech stack diagram
- [ ] Update [`docs/design/design-bible.md`](../docs/design/design-bible.md): remove Streamlit-specific sections
- [ ] Update [`AGENTS.md`](../AGENTS.md): remove Streamlit app isolation rules (§4), update tech stack
- [ ] Run full smoke test: filters, favorites, map, backoffice, scheduler, email notifications
- [ ] Uninstall Streamlit: `pip uninstall streamlit streamlit-folium folium`

---

## 11. Architecture After Migration

```
┌──────────────────────────────────────────────────────────────┐
│               FastAPI + Uvicorn (port 8501)                   │
│                                                              │
│  ┌────────────────────────┐  ┌─────────────────────────────┐ │
│  │   Dashboard Routes     │  │   Admin Routes (/admin/)    │ │
│  │   GET /                │  │   GET /admin/               │ │
│  │   GET /listings        │  │   GET /admin/analytics      │ │
│  │   POST /favorite/{id}  │  │   GET /admin/api-usage      │ │
│  │   POST /dislike/{id}   │  │   GET /admin/notifications  │ │
│  │   POST /sync           │  │   GET /admin/settings       │ │
│  │   GET /stream/listings │  │   POST /admin/settings      │ │
│  └──────────┬─────────────┘  └──────────────┬──────────────┘ │
│             │                               │                │
│  ┌──────────┴───────────────────────────────┴──────────────┐ │
│  │              Jinja2 Templates (web/templates/)          │ │
│  │  base.html │ dashboard.html │ admin/*.html              │ │
│  │  partials/ (HTMX-swappable fragments)                   │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │              Static Assets (web/static/)                │ │
│  │  css/ (tokens + components) │ js/ (map + htmx-hooks)   │ │
│  │  HTMX 14KB (CDN) │ Leaflet 42KB (CDN)                  │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │              APScheduler (lifespan-managed)             │ │
│  │  Scrape job: every 6h │ Notification job: 8am/8pm      │ │
│  └─────────────────────────────────────────────────────────┘ │
└──────────────────────────┬───────────────────────────────────┘
                           │ Direct Python imports
┌──────────────────────────┼───────────────────────────────────┐
│                    src/ (Backend — UNCHANGED)                 │
│  database.py (1,351L) │ models.py (290L)                     │
│  orchestrator.py (314L) │ scheduler.py (197L)                │
│  notifier.py (503L) │ dedup.py │ utils.py                    │
│  scrapers/ (zillow + craigslist adapters)                     │
└──────────────────────────┬───────────────────────────────────┘
                           │
                      SQLite (data/listings.db)
```

---

## 12. Open Questions for Owner

Before implementation begins:

- [x] **Template choice**: Use `sunnynest-dashboard.html` (owner confirmed)
- [ ] **Port during development**: Use 8000 for FastAPI dev while Streamlit stays on 8501?
- [ ] **Parallel period**: Keep Streamlit running during Phases 0–3 for daily use?
- [ ] **Theme**: Start with dark theme only (matches current production)?
- [ ] **Map tiles**: Switch to Stadia dark tiles immediately, or keep OpenStreetMap?
- [ ] **Priority**: Start migration now or after other planned features (POI markers)?

---

## Appendix A: Mockup → Template Extraction Guide

The [`sunnynest-dashboard.html`](../docs/temp/mockups/sunnynest-dashboard.html) (1,324 lines) breaks down as:

| Lines | Content | Becomes |
|-------|---------|---------|
| 1–9 | `<head>`, meta, fonts | `base.html` |
| 10–47 | CSS design tokens | `static/css/tokens.css` |
| 49–98 | CSS reset + base | `static/css/reset.css` |
| 100–208 | CSS filter bar + split panel | `static/css/layout.css` |
| 210–500+ | CSS card, badges, map, states | `static/css/components/*.css` |
| 800+ | HTML filter bar | `dashboard.html` (filter section) |
| 850+ | HTML listing cards | `partials/listing-card.html` |
| 1000+ | HTML map placeholder | `dashboard.html` (map section) |
| 1100+ | HTML empty/error states | `partials/empty-state.html`, `partials/error-state.html` |
| 1200+ | HTML skeleton loading | `partials/listing-skeleton.html` |

The CSS extraction is mechanical — copy sections into separate files and `@import` them in `base.html`. The HTML extraction requires adding Jinja2 template tags (`{{ }}`, `{% %}`) and HTMX attributes (`hx-get`, `hx-target`, etc.).

---

## Appendix B: Dependency Changes Summary

| Package | Current | After Migration | Reason |
|---------|---------|----------------|--------|
| `streamlit` | ✅ Required | ❌ Remove | Replaced by FastAPI |
| `streamlit-folium` | ✅ Required | ❌ Remove | Replaced by Leaflet.js |
| `folium` | ✅ Required | ❌ Remove | Replaced by Leaflet.js |
| `plotly` | ✅ Required | ❌ Remove | Backoffice uses SVG charts from mockup |
| `pandas` | ✅ Required | ❌ Remove | Only used by Streamlit/Plotly charts |
| `playwright` | ✅ Listed | ❌ Remove | Never used (Zillow uses API) |
| `fastapi` | — | ✅ Add | Web framework |
| `uvicorn[standard]` | — | ✅ Add | ASGI server |
| `jinja2` | ✅ (transitive) | ✅ Add explicit | Template engine |
| `python-multipart` | — | ✅ Add | Form data parsing |
| `sse-starlette` | — | ✅ Add | Server-Sent Events |
| `sqlalchemy` | ✅ Keep | ✅ Keep | ORM (unchanged) |
| `httpx` | ✅ Keep | ✅ Keep | HTTP client for scrapers |
| `beautifulsoup4` | ✅ Keep | ✅ Keep | HTML parsing for Craigslist |
| `apscheduler` | ✅ Keep | ✅ Keep | Background scheduler |
| `pyyaml` | ✅ Keep | ✅ Keep | Config file parsing |
| `geopy` | ✅ Keep | ✅ Keep | Geocoding |
| `lxml` | ✅ Keep | ✅ Keep | Fast HTML parser |

**Net change**: Remove 6 packages, add 4 packages. Lighter dependency footprint.

---

*This review is documentation only — no production code. All technical decisions are proposals awaiting owner approval before implementation begins.*
