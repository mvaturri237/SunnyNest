# Frontend Migration — Consolidated Plan (For Approval)

> **Date**: 2026-03-29  
> **Status**: AWAITING OWNER APPROVAL  
> **Sources**: [Original Plan](frontend-migration.md) | [UX Review](frontend-migration-ux-review.md) | [Architecture Review](frontend-migration-arch-review.md)

---

## Decision: Streamlit → FastAPI + HTMX + Jinja2

### Why Migrate?
Streamlit injects unpredictable wrapper divs (`stLayoutWrapper`, `stVerticalBlockBorderWrapper`) that make pixel-perfect CSS layout impossible. After 3 failed attempts to fix a simple empty-space gap, the conclusion is clear: **Streamlit is not designed for custom layouts**.

### Why FastAPI + HTMX?
- **100% HTML/CSS control** — no framework-injected wrappers
- **Python backend stays unchanged** — `src/` has zero Streamlit imports
- **Existing HTML mockups become templates** — minimal conversion effort
- **HTMX handles interactivity** — 14KB library, no build step, no React/npm
- **Single server** — dashboard + backoffice on one process (eliminates separate launchd plist)

---

## Project Structure

```
zillow/
├── web/                          # NEW: All FastAPI code
│   ├── main.py                   # App factory + scheduler lifespan
│   ├── routes/
│   │   ├── dashboard.py          # GET / (main page)
│   │   ├── listings.py           # GET /listings (HTMX partial)
│   │   ├── actions.py            # POST /favorite/{id}, /dislike/{id}
│   │   ├── stream.py             # GET /stream/listings (SSE)
│   │   └── admin.py              # GET /admin/* (backoffice)
│   ├── templates/
│   │   ├── base.html             # Shared layout (dark theme)
│   │   ├── dashboard.html        # Filter bar + split panel
│   │   ├── partials/             # HTMX-swappable fragments
│   │   │   ├── listing-cards.html
│   │   │   ├── listing-card.html
│   │   │   ├── listing-skeleton.html
│   │   │   └── toast.html
│   │   └── admin/                # Backoffice pages
│   └── static/
│       ├── css/                  # Design tokens + components
│       └── js/
│           ├── map.js            # Leaflet (replaces Folium)
│           └── htmx-hooks.js     # Accessibility + map sync
├── src/                          # UNCHANGED: Backend library
└── data/                         # UNCHANGED: SQLite + GeoJSON
```

---

## Key Technical Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | **Keep SQLAlchemy** (no ORM change) | Zero migration effort |
| 2 | **Client-side Leaflet.js** (drop Folium) | Full map API access, no server-side rendering |
| 3 | **Custom CSS** (no Tailwind/Bootstrap) | Mockups already have production-quality CSS |
| 4 | **Single Uvicorn process** | Local single-user app, no need for Gunicorn |
| 5 | **APScheduler in FastAPI lifespan** | Same scheduler, cleaner lifecycle |
| 6 | **Dark theme only** (initially) | Matches current production |

---

## Phase Plan

### Phase 0: Foundation (4–5h)
- Install FastAPI + dependencies
- Create `web/` directory structure
- Extract CSS from mockup into component files
- Convert mockup HTML → Jinja2 templates
- Wire up `src/database.py` for real data
- Add accessibility foundation (`aria-live`, focus management)
- **Deliverable**: Homepage loads at `localhost:8000` with real listings

### Phase 1: Dashboard Core (10–12h)
- HTMX-powered filter bar (price, beds, baths, source, sort)
- Listing cards with favorites/dislikes (HTMX inline swap)
- Leaflet.js map with price pill markers + city boundary
- **Bidirectional map ↔ card sync** (click marker → highlight card, click card → highlight marker)
- **Responsive breakpoints** (>1024px split, 768-1024px narrow, <768px stacked)
- Loading skeletons, empty state, error state
- Route tests (TestClient)
- **Deliverable**: Full dashboard feature parity

### Phase 2: Backoffice (6–8h)
- Convert backoffice mockup → Jinja2 templates
- 5 admin pages: Dashboard, Analytics, API Usage, Notifications, Settings
- Admin link in dashboard footer
- **Deliverable**: Backoffice feature parity at `/admin/`

### Phase 3: Polish (4–6h)
- SSE for real-time new listing notifications (toast pattern)
- Card animations (fade-in on filter, fade-out on dislike)
- Keyboard navigation (arrow keys in card feed)
- URL-based filter state (shareable links)
- **Deliverable**: Features exceeding current Streamlit capabilities

### Phase 4: Cutover (3–4h)
- Update launchd plist → Uvicorn
- Remove Streamlit dependencies
- Archive `app.py` and `backoffice.py`
- Full smoke test
- **Deliverable**: Streamlit fully replaced

**Total estimated: 27–35h** (AI-assisted, likely 4-6 sessions)

---

## Dependency Changes

| Remove (6) | Add (5) |
|------------|---------|
| `streamlit` | `fastapi` |
| `streamlit-folium` | `uvicorn[standard]` |
| `folium` | `jinja2` |
| `plotly` | `python-multipart` |
| `pandas` | `sse-starlette` |
| `playwright` | |

**Keep unchanged**: `sqlalchemy`, `httpx`, `beautifulsoup4`, `apscheduler`, `pyyaml`, `geopy`, `lxml`

---

## Rollback Strategy

The migration is inherently safe:
- **Database untouched** — same SQLite file, same queries
- **Backend untouched** — `src/` has zero changes
- **Streamlit backups preserved** — `app.py.backup-streamlit`

During development, both run in parallel:
| App | Port | Purpose |
|-----|------|---------|
| Streamlit (current) | 8501 | Daily use |
| FastAPI (new) | 8000 | Development |

Rollback takes 5 minutes: restore backup files + reinstall Streamlit.

---

## Questions for Your Approval

Please confirm these before we start:

- [ ] **1. Proceed with FastAPI + HTMX?** (Yes/No)
- [ ] **2. Dev port 8000** while Streamlit stays on 8501? (Yes/No)
- [ ] **3. Keep Streamlit running** during Phases 0–3 for daily use? (Yes/No)
- [ ] **4. Dark theme only** to start? (Yes/No)
- [ ] **5. Keep OpenStreetMap tiles** or switch to Stadia dark? (OSM/Stadia)
- [ ] **6. Start migration now** or after other planned features? (Now/Later)

---

*Full details in: [Architecture Review](frontend-migration-arch-review.md) | [UX Review](frontend-migration-ux-review.md)*
