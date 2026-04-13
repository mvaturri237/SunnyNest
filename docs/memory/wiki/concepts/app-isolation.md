# App Isolation

> Dashboard (`app.py`) and Backoffice (`backoffice.py`) are separate Streamlit apps with independent UI — `app.py` must NEVER use `st.sidebar` because it hides `stHeader` via CSS.

**Applies to:** [Admin Dashboard](../entities/admin-dashboard.md), [Listing Card](../entities/listing-card.md), [Filter Bar](../entities/filter-bar.md)  
**Learned:** 2026-03-28  
**Source:** `docs/memory/shared/lessonsLearned.md` — App Isolation + `docs/memory/shared/systemPatterns.md` — App Isolation

## Pattern

The SunnyNest project has two separate Streamlit apps:
- **`app.py`** (dashboard, port 8501) — user-facing listing browser
- **`backoffice.py`** (admin, port 8502) — admin panel

Both share the same backend (`src/database.py`, `src/models.py`, `data/listings.db`) but have completely independent UI, CSS, and layout. The dashboard hides Streamlit's `stHeader` element via CSS to achieve a clean, full-width header-only layout. Since the sidebar toggle button lives inside `stHeader`, hiding it makes `st.sidebar` architecturally incompatible with the dashboard.

**Note:** After the frontend migration to FastAPI + HTMX, the dashboard runs at `localhost:8000` and the admin panel is at `/admin/` on the same server. The Streamlit apps (`app.py`, `backoffice.py`) are legacy but the isolation principle still applies to any Streamlit code.

## Rules

1. **`app.py` must NEVER use `st.sidebar`** — the sidebar toggle is inside the hidden `stHeader`
2. **Backoffice features must NOT modify `app.py`'s CSS or layout**
3. **Cross-app links go in the main content area, not the sidebar** — use `st.markdown()`, not `st.sidebar.markdown()`
4. **When adding sidebar content to `app.py`:** STOP. Use `st.expander()` in the main content area instead
5. **Before modifying `app.py`:** Always check the CSS section for `stHeader` hiding rules

## Examples

- **Regression incident (2026-03-28):** Adding an "Admin →" link to `app.py`'s sidebar required un-hiding `stHeader`, which broke the clean header layout and brought back the `»` sidebar toggle button. Fixed by removing ALL `st.sidebar` usage and moving content to main area.
- **Correct pattern:** "Admin →" link rendered via `st.markdown()` at the bottom of the page

## Related

- [Admin Dashboard](../entities/admin-dashboard.md) — the admin panel
- [Filter Bar](../entities/filter-bar.md) — filters in main content area (not sidebar)
