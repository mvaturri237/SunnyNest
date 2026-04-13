# Frontend Framework Migration — Evaluation & Plan

> **Date**: 2026-03-29  
> **Author**: Architect Agent  
> **Status**: PROPOSAL — awaiting owner decision  
> **Related**: [`plans/architecture.md`](../plans/architecture.md), [`docs/design/design-bible.md`](../docs/design/design-bible.md)

---

## 1. Problem Statement

Streamlit's DOM structure makes precise CSS layout control extremely difficult. The dashboard ([`app.py`](../app.py)) contains **530 lines of CSS hacks** (lines 63–531) fighting Streamlit's internal wrapper divs (`stLayoutWrapper`, `stVerticalBlockBorderWrapper`, `stElementContainer`). These wrappers:

- Are injected unpredictably and vary by Streamlit version
- Cannot be reliably targeted with CSS selectors
- Create empty space gaps that require multi-iteration debugging
- Make pixel-perfect layouts impossible without browser DevTools reverse-engineering

**Evidence of the problem:**
- 5 separate CSS fix iterations in a single day (2026-03-29) for layout spacing issues
- Lesson learned documented: "Always inspect the actual Streamlit DOM with browser DevTools before writing CSS selectors"
- `app.py` must NEVER use `st.sidebar` due to `stHeader` hiding — an architectural constraint imposed by CSS workarounds
- 73 `st.*` calls creating deep framework coupling

### What We Lose by Staying on Streamlit
| Issue | Impact |
|-------|--------|
| No HTML control | Every layout change requires CSS reverse-engineering |
| Wrapper div injection | Empty space gaps, unpredictable padding |
| Version fragility | DOM structure changes between Streamlit versions |
| No real-time updates | Full page reruns on every interaction |
| Session state complexity | Manual state management for filters, favorites, pagination |
| Map integration friction | `streamlit-folium` wrapper adds another abstraction layer |
| Mobile responsiveness | Nearly impossible — Streamlit controls the viewport |

---

## 2. Requirements for Replacement Framework

| # | Requirement | Priority | Notes |
|---|------------|----------|-------|
| R1 | Full CSS/HTML control — no injected wrappers | **Must** | Core reason for migration |
| R2 | Python backend compatibility | **Must** | Reuse `src/database.py`, `src/models.py`, `src/orchestrator.py`, etc. |
| R3 | Interactive map (Leaflet/Mapbox) | **Must** | Price pill markers, clustering, city boundary overlay |
| R4 | Real-time updates | **Should** | Show new listings as scraped (WebSocket or SSE) |
| R5 | Low migration effort (<40h) | **Should** | Solo developer, limited time budget |
| R6 | Solo developer manageable | **Must** | No complex build toolchains or framework ecosystems |
| R7 | Local deployment (localhost) | **Must** | No cloud dependency |
| R8 | Existing HTML mockups reusable | **Should** | 1,575-line dashboard mockup + 960-line backoffice mockup already exist |
| R9 | Dark theme support | **Must** | Current production uses dark theme |
| R10 | Favorite/dislike interactivity | **Must** | Toggle buttons that persist to SQLite |

---

## 3. Current Architecture Snapshot

```
┌─────────────────────────────────────────────────────┐
│                    Streamlit (app.py)                │
│  ┌──────────┐  ┌──────────┐  ┌───────────────────┐  │
│  │ Filter   │  │ Listing  │  │ Folium Map        │  │
│  │ Bar      │  │ Cards    │  │ (streamlit-folium) │  │
│  └──────────┘  └──────────┘  └───────────────────┘  │
│         73 st.* calls │ 530 lines CSS hacks         │
└────────────────────────┼────────────────────────────┘
                         │ Direct Python imports
┌────────────────────────┼────────────────────────────┐
│                   src/ (Backend)                     │
│  database.py (1350L) │ models.py (289L)             │
│  orchestrator.py (313L) │ scheduler.py (196L)       │
│  notifier.py (503L) │ utils.py (157L)               │
│  scrapers/ (zillow + craigslist)                     │
└─────────────────────────────────────────────────────┘
                         │
                    SQLite (data/listings.db)
```

**Key insight**: The backend (`src/`) has **zero Streamlit imports**. It's a clean Python library with SQLAlchemy models and pure functions. Any framework that can call Python functions can reuse it entirely.

---

## 4. Framework Comparison

### 4.1 Evaluation Matrix

| Criteria (weight) | Streamlit (current) | Flask + Jinja2 + JS | FastAPI + HTMX | NiceGUI | Dash (Plotly) | React + FastAPI | Gradio |
|---|---|---|---|---|---|---|---|
| **CSS/HTML control** (25%) | ❌ 1/5 | ✅ 5/5 | ✅ 5/5 | ⚠️ 3/5 | ⚠️ 2/5 | ✅ 5/5 | ❌ 1/5 |
| **Python backend reuse** (20%) | ✅ 5/5 | ✅ 5/5 | ✅ 5/5 | ✅ 5/5 | ✅ 5/5 | ✅ 4/5 | ✅ 5/5 |
| **Map integration** (15%) | ⚠️ 3/5 | ✅ 5/5 | ✅ 5/5 | ⚠️ 3/5 | ⚠️ 3/5 | ✅ 5/5 | ❌ 1/5 |
| **Real-time updates** (10%) | ❌ 1/5 | ⚠️ 3/5 | ✅ 4/5 | ✅ 4/5 | ⚠️ 2/5 | ✅ 5/5 | ❌ 1/5 |
| **Migration effort** (15%) | N/A | ⚠️ 3/5 | ✅ 4/5 | ✅ 4/5 | ⚠️ 3/5 | ❌ 2/5 | ⚠️ 3/5 |
| **Solo dev friendly** (10%) | ✅ 5/5 | ✅ 4/5 | ✅ 5/5 | ✅ 5/5 | ⚠️ 3/5 | ❌ 2/5 | ✅ 5/5 |
| **Local deployment** (5%) | ✅ 5/5 | ✅ 5/5 | ✅ 5/5 | ✅ 5/5 | ✅ 5/5 | ✅ 5/5 | ✅ 5/5 |
| **Weighted Score** | **2.55** | **4.45** | **4.70** | **3.90** | **3.10** | **3.85** | **2.30** |

### 4.2 Detailed Pros/Cons

#### Option 1: Flask + Jinja2 + Vanilla JS
**Score: 4.45/5**

| Pros | Cons |
|------|------|
| 100% HTML/CSS control — write exactly what you want | More boilerplate than HTMX (manual AJAX calls) |
| Mature, battle-tested, massive ecosystem | No built-in real-time — need Flask-SocketIO or SSE |
| Jinja2 templates can directly embed existing HTML mockups | Must write JS for interactive features (favorites, map) |
| Direct Python imports — `from src.database import ...` | Two languages (Python + JS) to maintain |
| Leaflet.js native — no wrapper library needed | Form handling is manual (no framework magic) |
| Existing mockups are already Flask-compatible HTML | Slightly more code than HTMX for same features |
| Huge community, easy to find solutions | — |

**Migration effort**: ~30–35 hours

#### Option 2: FastAPI + HTMX ⭐ RECOMMENDED
**Score: 4.70/5**

| Pros | Cons |
|------|------|
| 100% HTML/CSS control — you write the HTML | Smaller community than Flask (but growing fast) |
| HTMX replaces 90% of JS with HTML attributes | HTMX is a paradigm shift — learning curve for first project |
| FastAPI is async-native — perfect for SSE real-time updates | Less "magic" than Streamlit — must build UI from scratch |
| Automatic API docs (Swagger/OpenAPI) for free | Map interactions need small JS snippets (Leaflet events) |
| Direct Python imports — `from src.database import ...` | No built-in session management (use cookies or server-side) |
| Jinja2 templates — existing HTML mockups drop in directly | — |
| SSE (Server-Sent Events) built-in for real-time listing updates | — |
| Minimal JS — HTMX handles clicks, forms, partial page updates | — |
| Leaflet.js native — no wrapper library | — |
| Modern Python typing + Pydantic validation | — |
| WebSocket support if needed later | — |
| Backoffice can share the same FastAPI server (route separation) | — |

**Migration effort**: ~25–30 hours

#### Option 3: NiceGUI
**Score: 3.90/5**

| Pros | Cons |
|------|------|
| Pure Python — no HTML/JS/CSS needed | Still abstracts the DOM (Vue.js under the hood) |
| Built-in Leaflet map component | Less CSS control than raw HTML (better than Streamlit, worse than Flask) |
| WebSocket-based — real-time by default | Smaller community — fewer Stack Overflow answers |
| Easy migration from Streamlit (similar API style) | Custom layouts require learning NiceGUI's slot/container system |
| Tailwind CSS integration available | Map customization (price pills, clustering) may need workarounds |
| Direct Python imports work | Version 1.x — less mature than Flask/FastAPI |

**Migration effort**: ~20–25 hours

#### Option 4: Dash (Plotly)
**Score: 3.10/5**

| Pros | Cons |
|------|------|
| Python-native — callbacks in Python | React-based components — same wrapper div problem as Streamlit |
| Excellent charting (Plotly native) | CSS control is limited — Dash injects its own wrapper divs |
| Good for data dashboards | Map component (dash-leaflet) is a wrapper — same abstraction issue |
| Pattern-matching callbacks for dynamic UIs | Callback hell — complex state management for interactive UIs |
| Enterprise-grade (Plotly maintains it) | Heavier than needed — designed for data science dashboards |
| — | Two apps would need two Dash servers (like Streamlit) |

**Migration effort**: ~30–35 hours

#### Option 5: React/Next.js + FastAPI
**Score: 3.85/5**

| Pros | Cons |
|------|------|
| Ultimate CSS/HTML control | Two separate codebases (Python API + React frontend) |
| React-Leaflet is excellent for maps | Must learn React, JSX, npm, webpack/vite ecosystem |
| Real-time via WebSocket trivial | Massive toolchain complexity for a solo developer |
| Huge ecosystem, any UI pattern possible | API serialization layer needed (can't just import Python) |
| Best long-term scalability | 2x the code to maintain |
| — | Overkill for a local single-user tool |
| — | Existing HTML mockups need conversion to JSX |

**Migration effort**: ~50–60 hours

#### Option 6: Gradio
**Score: 2.30/5**

| Pros | Cons |
|------|------|
| Pure Python, very easy to learn | Designed for ML demos, not dashboards |
| Quick prototyping | Very limited layout control (worse than Streamlit for custom UIs) |
| Built-in sharing (not needed here) | No map component — would need iframe hack |
| — | No real-time updates |
| — | Card-based listing UI would be extremely hacky |
| — | Wrong tool for this job |

**Migration effort**: ~35–40 hours (fighting the framework)

---

## 5. Recommendation: FastAPI + HTMX + Jinja2

### Why FastAPI + HTMX Wins

1. **Solves the core problem**: 100% HTML/CSS control. The 530 lines of CSS hacks in [`app.py`](../app.py) become ~50 lines of clean, standard CSS. No wrapper divs, no `data-testid` selectors, no version-dependent DOM structures.

2. **Existing mockups are the templates**: The [`user-dashboard.html`](../docs/temp/mockups/user-dashboard.html) (1,575 lines) and [`backoffice.html`](../docs/temp/mockups/backoffice.html) mockups are already valid HTML with design tokens. They become Jinja2 templates with minimal changes (add `{{ }}` template tags).

3. **HTMX eliminates JavaScript**: Instead of writing `fetch()` calls and DOM manipulation, HTMX uses HTML attributes:
   ```html
   <!-- Toggle favorite — no JS needed -->
   <button hx-post="/api/favorite/{{ listing.id }}" 
           hx-swap="outerHTML"
           hx-target="this">
     ♡
   </button>
   ```

4. **Backend reuse is 100%**: FastAPI routes directly import from `src/database`, `src/models`, etc.:
   ```python
   from src.database import get_filtered_listings, toggle_favorite
   
   @app.get("/")
   async def dashboard(request: Request):
       listings = get_filtered_listings(filters)
       return templates.TemplateResponse("dashboard.html", {"listings": listings})
   ```

5. **Real-time updates via SSE**: FastAPI has native SSE support — new listings appear without page refresh:
   ```python
   @app.get("/stream/listings")
   async def listing_stream():
       async def event_generator():
           while True:
               new = check_for_new_listings()
               if new:
                   yield f"data: {json.dumps(new)}\n\n"
               await asyncio.sleep(30)
       return StreamingResponse(event_generator(), media_type="text/event-stream")
   ```

6. **Unified server**: Dashboard and backoffice can run on the same FastAPI server with route prefixes (`/` for dashboard, `/admin/` for backoffice), eliminating the need for two separate processes and two launchd services.

7. **Leaflet.js native**: No wrapper library. Direct Leaflet with full API access for price pill markers, clustering, boundary overlays — exactly matching the design bible's map specifications.

### Why Not Flask?

Flask would also work well (score 4.45), but FastAPI edges it out because:
- **Async-native**: SSE and WebSocket support without extensions
- **Auto-generated API docs**: Free Swagger UI at `/docs` — useful for debugging
- **Pydantic models**: Type-safe request/response validation
- **Modern Python**: Type hints, async/await, dataclasses
- Flask would require `Flask-SocketIO` for real-time, adding complexity

### Why Not NiceGUI?

NiceGUI (score 3.90) is tempting because it's pure Python, but:
- It still abstracts the DOM (Vue.js components under the hood)
- Custom map markers (price pills) would require workarounds
- Smaller community means fewer solutions when stuck
- We'd be trading one abstraction layer (Streamlit) for another (NiceGUI)
- The existing HTML mockups can't be reused — they'd need to be rebuilt in NiceGUI's API

---

## 6. Migration Plan

### Phase 0: Foundation (4–5 hours)
**Goal**: FastAPI server running with one working page

- [ ] Install FastAPI, Uvicorn, Jinja2, python-multipart, HTMX (CDN)
- [ ] Create project structure:
  ```
  web/
  ├── main.py              # FastAPI app entry point
  ├── routes/
  │   ├── dashboard.py     # Dashboard routes
  │   └── admin.py         # Backoffice routes
  ├── templates/
  │   ├── base.html         # Shared layout (head, nav, footer)
  │   ├── dashboard.html    # Main dashboard (from mockup)
  │   └── admin/
  │       └── dashboard.html
  ├── static/
  │   ├── css/
  │   │   └── style.css     # Design bible tokens → CSS variables
  │   ├── js/
  │   │   └── map.js        # Leaflet map initialization
  │   └── img/
  └── partials/
      ├── listing-card.html  # Single card (HTMX swappable)
      ├── filter-bar.html    # Filter controls
      └── map-popup.html     # Map marker popup
  ```
- [ ] Convert [`user-dashboard.html`](../docs/temp/mockups/user-dashboard.html) mockup → Jinja2 base template
- [ ] Wire up `src/database.py` imports in FastAPI routes
- [ ] Verify: homepage loads with static content from database

### Phase 1: Dashboard Core (8–10 hours)
**Goal**: Feature parity with current Streamlit dashboard (minus real-time)

- [ ] **Filter bar**: HTMX-powered dropdowns that reload listing cards without full page refresh
  ```html
  <select hx-get="/listings" hx-target="#listing-cards" hx-include="[name='filter']">
  ```
- [ ] **Listing cards**: Jinja2 partial template, rendered server-side, swapped via HTMX
- [ ] **Map**: Leaflet.js with price pill markers (DivIcon), city boundary GeoJSON overlay, marker clustering
- [ ] **Favorites/dislikes**: HTMX `hx-post` buttons that toggle and swap the button HTML
- [ ] **Sort**: HTMX-powered sort dropdown
- [ ] **Image lazy loading**: Native `loading="lazy"` attribute (no framework needed)
- [ ] **Dark theme**: CSS variables from design bible, `prefers-color-scheme` media query

### Phase 2: Backoffice (6–8 hours)
**Goal**: Backoffice feature parity

- [ ] Convert [`backoffice.html`](../docs/temp/mockups/backoffice.html) mockup → Jinja2 templates
- [ ] Dashboard KPIs page (listing stats, source counts)
- [ ] Listing Analytics page (price distribution, inventory timeline)
- [ ] API Usage page (call counts, daily breakdown)
- [ ] Notifications page (history, stats)
- [ ] Settings page (email toggle, recipient — writes to `config.yaml`)
- [ ] Route prefix: `/admin/` with all backoffice routes

### Phase 3: Real-time & Polish (4–6 hours)
**Goal**: Features that exceed current Streamlit capabilities

- [ ] **SSE for new listings**: Browser subscribes to `/stream/listings`, new cards appear automatically
- [ ] **Map-card interaction**: Click a map marker → highlight the corresponding card (and vice versa)
- [ ] **URL-based filters**: Filter state in URL query params (shareable, bookmarkable)
- [ ] **Keyboard shortcuts**: Arrow keys for card navigation (native JS, no framework)
- [ ] **Mobile responsive**: CSS media queries (impossible in Streamlit)
- [ ] **Loading states**: HTMX `hx-indicator` for spinner during filter changes

### Phase 4: Cutover & Cleanup (3–4 hours)
**Goal**: Replace Streamlit entirely

- [ ] Update [`scripts/start-dashboard.sh`](../scripts/start-dashboard.sh) to run `uvicorn web.main:app`
- [ ] Update [`com.sunnynest.dashboard.plist`](../com.sunnynest.dashboard.plist) for FastAPI
- [ ] Remove [`com.sunnynest.backoffice.plist`](../com.sunnynest.backoffice.plist) (backoffice is now same server)
- [ ] Update [`requirements.txt`](../requirements.txt): remove `streamlit`, `streamlit-folium`; add `fastapi`, `uvicorn`, `jinja2`, `python-multipart`
- [ ] Archive `app.py` and `backoffice.py` as `*.backup-streamlit`
- [ ] Update [`plans/architecture.md`](../plans/architecture.md) with new tech stack
- [ ] Update [`docs/design/design-bible.md`](../docs/design/design-bible.md) — remove Streamlit-specific sections
- [ ] Update [`AGENTS.md`](../AGENTS.md) — remove Streamlit app isolation rules
- [ ] Run full smoke test: filters, favorites, map, backoffice, scheduler

---

## 7. Effort Summary

| Phase | Hours | Deliverable |
|-------|-------|-------------|
| Phase 0: Foundation | 4–5h | FastAPI server + base template |
| Phase 1: Dashboard | 8–10h | Full dashboard feature parity |
| Phase 2: Backoffice | 6–8h | Full backoffice feature parity |
| Phase 3: Real-time & Polish | 4–6h | SSE, mobile, map interaction |
| Phase 4: Cutover | 3–4h | Streamlit removed, services updated |
| **Total** | **25–33h** | **Complete migration** |

### Comparison: Migration Effort by Framework

| Framework | Estimated Hours | Notes |
|-----------|----------------|-------|
| FastAPI + HTMX ⭐ | 25–33h | Mockups reusable, minimal JS |
| NiceGUI | 20–25h | Fastest, but trades one abstraction for another |
| Flask + Jinja2 + JS | 30–35h | More JS boilerplate than HTMX |
| Dash | 30–35h | Same wrapper div problems |
| Gradio | 35–40h | Wrong tool, fighting the framework |
| React + FastAPI | 50–60h | Overkill, two codebases |

---

## 8. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| HTMX learning curve | Medium | Low | HTMX is ~14KB, simple API; 1–2h tutorial sufficient |
| Leaflet map complexity | Medium | Medium | Existing Folium code generates Leaflet — can extract marker logic |
| Scheduler integration | Low | High | APScheduler runs in-process with FastAPI (same as Streamlit) |
| Session state for favorites | Low | Low | Use browser cookies or server-side session (no Streamlit magic needed) |
| SQLite concurrent access | Medium | Medium | FastAPI is async but SQLite is single-writer; use `check_same_thread=False` + connection pooling |
| Backoffice config.yaml writes | Low | Low | Same `src/utils.py` functions, just called from FastAPI route instead of Streamlit |
| launchd service update | Low | Low | Change one line in plist (streamlit → uvicorn) |
| Regression in existing features | Medium | High | Keep Streamlit backups; run both in parallel during Phase 1–3 |

### Risk Mitigation Strategy
- **Parallel running**: Keep Streamlit on port 8501 while developing FastAPI on port 8000. Switch over only after full smoke test.
- **Incremental migration**: Each phase is independently testable. Can stop after Phase 1 if needed.
- **Backup files**: `app.py.backup-streamlit` and `backoffice.py.backup-streamlit` for instant rollback.

---

## 9. What Changes in the Backend

**Almost nothing.** The backend (`src/`) has zero Streamlit imports. The migration is purely a frontend concern.

| Backend Module | Changes Needed |
|----------------|---------------|
| [`src/database.py`](../src/database.py) | None — functions already return ORM objects |
| [`src/models.py`](../src/models.py) | None |
| [`src/orchestrator.py`](../src/orchestrator.py) | None |
| [`src/scheduler.py`](../src/scheduler.py) | Minor — start scheduler in FastAPI `lifespan` instead of `st.session_state` |
| [`src/notifier.py`](../src/notifier.py) | None |
| [`src/utils.py`](../src/utils.py) | None |
| [`config.yaml`](../config.yaml) | None |
| [`data/listings.db`](../data/listings.db) | None |

The only backend change is moving the scheduler startup from Streamlit's session state to FastAPI's lifespan event:

```python
# Before (Streamlit)
if "scheduler" not in st.session_state:
    scheduler = ScrapeScheduler(interval_hours=6)
    scheduler.start()
    st.session_state["scheduler"] = scheduler

# After (FastAPI)
@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = ScrapeScheduler(interval_hours=6)
    scheduler.start()
    yield
    scheduler.stop()
```

---

## 10. Backoffice Decision

### Should the backoffice migrate too?

**Yes — and it becomes simpler.**

| Aspect | Current (Streamlit) | After Migration (FastAPI) |
|--------|-------------------|--------------------------|
| Server | Separate process on port 8502 | Same server, `/admin/` route prefix |
| launchd | Separate plist file | Eliminated — one server handles both |
| Shared code | Import from `src/` | Same — import from `src/` |
| UI framework | Streamlit (960 lines) | Jinja2 templates (from existing mockup) |
| CSS control | Limited (same Streamlit problems) | Full control |

The backoffice mockup ([`backoffice.html`](../docs/temp/mockups/backoffice.html)) is already a complete HTML file. Converting it to Jinja2 templates is straightforward.

---

## 11. Architecture After Migration

```
┌─────────────────────────────────────────────────────────┐
│              FastAPI + Uvicorn (port 8501)               │
│                                                         │
│  ┌─────────────────────┐  ┌──────────────────────────┐  │
│  │  Dashboard Routes   │  │  Admin Routes (/admin/)  │  │
│  │  GET /              │  │  GET /admin/             │  │
│  │  GET /listings      │  │  GET /admin/analytics    │  │
│  │  POST /favorite/:id │  │  GET /admin/api-usage    │  │
│  │  GET /stream/new    │  │  POST /admin/settings    │  │
│  └─────────┬───────────┘  └────────────┬─────────────┘  │
│            │                           │                │
│  ┌─────────┴───────────────────────────┴─────────────┐  │
│  │              Jinja2 Templates                     │  │
│  │  base.html │ dashboard.html │ admin/*.html        │  │
│  │  partials/listing-card.html (HTMX swappable)     │  │
│  └───────────────────────────────────────────────────┘  │
│                                                         │
│  ┌───────────────────────────────────────────────────┐  │
│  │              Static Assets                        │  │
│  │  style.css (design tokens) │ map.js (Leaflet)    │  │
│  │  htmx.min.js (14KB CDN)                          │  │
│  └───────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────┘
                         │ Direct Python imports
┌────────────────────────┼────────────────────────────────┐
│                   src/ (Backend — UNCHANGED)             │
│  database.py │ models.py │ orchestrator.py              │
│  scheduler.py │ notifier.py │ utils.py                  │
│  scrapers/ (zillow + craigslist)                         │
└────────────────────────┬────────────────────────────────┘
                         │
                    SQLite (data/listings.db)
```

---

## 12. Decision Checklist

Before proceeding, the owner should confirm:

- [ ] **Framework choice**: FastAPI + HTMX (recommended) or alternative?
- [ ] **Migration scope**: Dashboard only, or dashboard + backoffice?
- [ ] **Port**: Keep 8501 or change to 8000 (FastAPI default)?
- [ ] **Parallel period**: Run both Streamlit and FastAPI during development?
- [ ] **Theme**: Start with dark theme (current) or switch to light theme (mockup)?
- [ ] **Priority**: Start migration now or after other planned features (POI markers, etc.)?

---

## Appendix A: Technology Quick Reference

| Technology | What It Does | Size/Overhead |
|-----------|-------------|---------------|
| [FastAPI](https://fastapi.tiangolo.com/) | Python web framework (async, type-safe) | ~1MB pip install |
| [Uvicorn](https://www.uvicorn.org/) | ASGI server (runs FastAPI) | ~500KB |
| [Jinja2](https://jinja.palletsprojects.com/) | HTML template engine (already a Streamlit dependency) | Already installed |
| [HTMX](https://htmx.org/) | HTML-over-the-wire (replaces most JS) | 14KB CDN, zero build step |
| [Leaflet.js](https://leafletjs.com/) | Interactive maps (replaces Folium wrapper) | 42KB CDN |
| [Leaflet.markercluster](https://github.com/Leaflet/Leaflet.markercluster) | Marker clustering plugin | 12KB CDN |

### New `requirements.txt` additions
```
fastapi>=0.109.0
uvicorn[standard]>=0.27.0
python-multipart>=0.0.6
```

### Removed from `requirements.txt`
```
streamlit>=1.30.0
streamlit-folium>=0.18.0
```

> **Note**: `folium` can optionally be kept for server-side map HTML generation, or replaced entirely with client-side Leaflet.js. Recommendation: use Leaflet.js directly for full control over markers and interactions.
