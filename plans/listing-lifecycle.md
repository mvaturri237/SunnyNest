# Listing Lifecycle Analytics & Days-on-Market Filter

> Architecture plan for `deactivated_at` timestamp, "Max Days Listed" dashboard filter, and Listing Lifecycle analytics section on the admin analytics page.

**Status:** PLANNED  
**Created:** 2026-04-06  
**Author:** Architect  
**Phases:** 2 (Backend → Frontend)

---

## Table of Contents

1. [Overview](#overview)
2. [Current State](#current-state)
3. [Phase 1 — Backend](#phase-1--backend-schema--queries--filter-logic)
4. [Phase 2 — Frontend](#phase-2--frontend-filter-ui--analytics-section)
5. [Affected Files](#affected-files)
6. [Data Flow Diagrams](#data-flow-diagrams)
7. [Implementation Notes](#implementation-notes)
8. [Wiki Impact](#wiki-impact)

---

## Overview

Three interconnected features that give SunnyNest lifecycle visibility into listings:

| # | Feature | Purpose |
|---|---------|---------|
| 1 | `deactivated_at` timestamp | Exact removal detection — when a listing was marked inactive |
| 2 | "Max Days Listed" filter | Dashboard filter to show only listings on market ≤ N days |
| 3 | Listing Lifecycle analytics | Admin analytics section with lifespan KPIs and breakdowns |

---

## Current State

### Relevant Schema (from [`src/models.py`](../src/models.py))

| Column | Type | Purpose | Populated By |
|--------|------|---------|-------------|
| `first_seen` | DateTime | When scraper first discovered listing | Scraper upsert |
| `last_seen` | DateTime | When scraper last confirmed listing | Scraper upsert |
| `listed_date` | Date, nullable | Date listing was posted on source | Scraper (from source data) |
| `days_on_market` | Integer, nullable | Days since `listed_date` or `first_seen` | Scraper (recalculated each run) |
| `is_active` | Boolean | Whether listing is still available | [`mark_inactive()`](../src/database.py:742) |

### Key Observations

- **81 listings** total: 51 active, 30 inactive
- **65 listings** have non-null `days_on_market` (avg=90, range 0–1051)
- [`mark_inactive()`](../src/database.py:742) sets `is_active=False` but records **no timestamp** — we lose the exact moment a listing was removed
- Inactive listing lifespan can currently only be approximated via `last_seen - first_seen` (avg 1.8 days for current data)
- The `days_on_market` column is already populated by scrapers and ready for filtering

---

## Phase 1 — Backend (Schema + Queries + Filter Logic)

### 1.1 — `deactivated_at` Column

#### Model Change — [`src/models.py`](../src/models.py:159)

Add `deactivated_at` after the `days_on_market` column in the `Listing` class (line ~161):

```python
# --- Analytics ---
days_on_market: int | None = Column(Integer, nullable=True)
deactivated_at: datetime | None = Column(DateTime, nullable=True)
```

#### Migration — [`src/database.py`](../src/database.py:132)

Add `_ensure_deactivated_at_column()` following the exact pattern of [`_ensure_days_on_market_column()`](../src/database.py:71):

```python
def _ensure_deactivated_at_column() -> None:
    """Add the ``deactivated_at`` column to the listings table if missing."""
    engine = get_engine()
    try:
        with engine.connect() as conn:
            conn.execute(
                text("ALTER TABLE listings ADD COLUMN deactivated_at DATETIME")
            )
            conn.commit()
        logger.info("Added deactivated_at column to listings table.")
    except Exception:
        pass  # Column already exists
```

Call it from [`init_db()`](../src/database.py:132) after the existing migration calls:

```python
def init_db() -> None:
    Base.metadata.create_all(engine)
    _ensure_days_on_market_column()
    _migrate_to_listing_sources()
    _ensure_school_columns()
    _ensure_deactivated_at_column()  # ← NEW
    logger.info("Database tables initialised.")
```

#### Backfill Consideration

For the 30 existing inactive listings, `deactivated_at` will be `NULL`. The lifecycle analytics queries (§1.3) must fall back to `last_seen` when `deactivated_at` is not available:

```sql
COALESCE(deactivated_at, last_seen) - first_seen
```

No separate backfill migration is needed — the `COALESCE` handles it gracefully.

#### Update `mark_inactive()` — [`src/database.py`](../src/database.py:742)

Modify the `.update()` call at line 761 to also set `deactivated_at`:

```python
# Current (line 761-763):
.update(
    {Listing.is_active: False},
    synchronize_session="fetch",
)

# New:
.update(
    {
        Listing.is_active: False,
        Listing.deactivated_at: datetime.now(timezone.utc),
    },
    synchronize_session="fetch",
)
```

**Important:** Only set `deactivated_at` when transitioning from active → inactive. The existing filter `Listing.is_active == True` in the query already ensures this — we only update listings that are currently active.

#### Upsert Exclusion

Add `deactivated_at` to the upsert exclusion tuples in [`upsert_listing()`](../src/database.py) so that scraper updates don't overwrite the deactivation timestamp. This follows the [Upsert Exclusion Pattern](../docs/memory/wiki/concepts/upsert-exclusion-pattern.md).

### 1.2 — "Max Days Listed" Filter Logic

#### Parse Filter — [`web/routes/__init__.py`](../web/routes/__init__.py:6)

Add `filter_max_days` parameter to [`parse_filters()`](../web/routes/__init__.py:6):

```python
def parse_filters(
    *,
    filter_price: str | None = None,
    filter_price_min: str | None = None,
    filter_price_max: str | None = None,
    filter_beds: str | None = None,
    filter_baths: str | None = None,
    filter_source: str | None = None,
    filter_sqft_min: str | None = None,
    filter_sqft_max: str | None = None,
    filter_pet: str | None = None,
    filter_ac: str | None = None,
    filter_furnished: str | None = None,
    filter_favorites: str | None = None,
    filter_max_days: str | None = None,  # ← NEW
) -> dict:
```

Add parsing logic after the favorites block (line ~101):

```python
# Parse max days on market
if filter_max_days and filter_max_days != "any":
    try:
        filters["max_days_listed"] = int(filter_max_days)
    except (ValueError, TypeError):
        pass
```

#### Apply Filter — [`src/database.py`](../src/database.py:175)

Add `max_days_listed` support to [`_apply_listing_filters()`](../src/database.py:175), after the `exclude_disliked` block (line ~278):

```python
# --- Days on market ---
if "max_days_listed" in filters:
    query = query.filter(
        Listing.days_on_market.isnot(None),
        Listing.days_on_market <= filters["max_days_listed"],
    )
```

**Design decision:** Filter on `days_on_market` column (not computed from dates) because:
- It's already populated by scrapers with accurate source data
- It's an indexed-friendly integer comparison
- 65 of 81 listings already have values
- Listings with `NULL` `days_on_market` are excluded (they lack data to filter on)

Update the docstring of `_apply_listing_filters()` to include `max_days_listed` in the supported filter keys list.

#### Wire Through Routes

**[`web/routes/listings.py`](../web/routes/listings.py:20)** — Add `filter_max_days` query parameter:

```python
@router.get("/listings")
async def filtered_listings(
    request: Request,
    # ... existing params ...
    filter_max_days: Optional[str] = Query(None, description="Max days on market, e.g. '30'"),
):
    filters = parse_filters(
        # ... existing params ...
        filter_max_days=filter_max_days,
    )
```

**[`web/routes/dashboard.py`](../web/routes/dashboard.py:23)** — Add default to `_DROPDOWN_DEFAULTS`:

```python
_DROPDOWN_DEFAULTS = {
    # ... existing defaults ...
    "filter_max_days": "",  # ← NEW (empty = "Any")
}
```

And pass it to `parse_filters()`:

```python
filters = parse_filters(
    # ... existing params ...
    filter_max_days=_DROPDOWN_DEFAULTS["filter_max_days"],
)
```

### 1.3 — Lifecycle Analytics Query Functions

Add three new functions to [`src/database.py`](../src/database.py):

#### `get_lifecycle_stats()`

Returns aggregate lifespan statistics for inactive listings.

```python
def get_lifecycle_stats() -> dict:
    """Return lifecycle statistics for inactive listings.

    Uses deactivated_at - first_seen when available,
    falls back to last_seen - first_seen for legacy data.

    Returns:
        Dict with keys: avg_lifespan_days, median_lifespan_days,
        min_lifespan_days, max_lifespan_days, total_removed.
    """
```

**SQL approach** (SQLite `julianday()` for date arithmetic):

```sql
SELECT
    COUNT(*) as total_removed,
    AVG(julianday(COALESCE(deactivated_at, last_seen)) - julianday(first_seen)) as avg_days,
    MIN(julianday(COALESCE(deactivated_at, last_seen)) - julianday(first_seen)) as min_days,
    MAX(julianday(COALESCE(deactivated_at, last_seen)) - julianday(first_seen)) as max_days
FROM listings
WHERE is_active = 0
```

For **median**, SQLite lacks a built-in `MEDIAN()`. Two options:
- **Option A (recommended):** Fetch all lifespan values and compute median in Python (`statistics.median()`)
- **Option B:** Use a SQLite window function with `PERCENTILE_CONT` (requires extension)

Recommend **Option A** for simplicity — the inactive listing count (currently 30) is small enough for in-memory computation.

#### `get_lifecycle_by_bedrooms()`

```python
def get_lifecycle_by_bedrooms() -> list[dict]:
    """Return average lifespan breakdown by bedroom count.

    Returns:
        List of dicts: [{"bedrooms": 3, "avg_days": 12.5, "count": 8}, ...]
    """
```

**SQL:**

```sql
SELECT
    bedrooms,
    COUNT(*) as count,
    AVG(julianday(COALESCE(deactivated_at, last_seen)) - julianday(first_seen)) as avg_days
FROM listings
WHERE is_active = 0
GROUP BY bedrooms
ORDER BY bedrooms
```

#### `get_lifecycle_by_price_range()`

```python
def get_lifecycle_by_price_range() -> list[dict]:
    """Return average lifespan breakdown by price bucket.

    Price buckets: <$3K, $3K–$4K, $4K–$5K, $5K–$6K, $6K–$7K, $7K–$8K, $8K+

    Returns:
        List of dicts: [{"range": "$3K–$4K", "avg_days": 15.2, "count": 5}, ...]
    """
```

**SQL approach:** Use `CASE WHEN` for bucketing:

```sql
SELECT
    CASE
        WHEN price < 3000 THEN '<$3K'
        WHEN price < 4000 THEN '$3K–$4K'
        WHEN price < 5000 THEN '$4K–$5K'
        WHEN price < 6000 THEN '$5K–$6K'
        WHEN price < 7000 THEN '$6K–$7K'
        WHEN price < 8000 THEN '$7K–$8K'
        ELSE '$8K+'
    END as price_range,
    COUNT(*) as count,
    AVG(julianday(COALESCE(deactivated_at, last_seen)) - julianday(first_seen)) as avg_days
FROM listings
WHERE is_active = 0
GROUP BY price_range
ORDER BY MIN(price)
```

#### Wire Into Admin Route — [`web/routes/admin.py`](../web/routes/admin.py:273)

Update the [`admin_analytics()`](../web/routes/admin.py:273) route to call the new functions and pass data to the template:

```python
from src.database import (
    # ... existing imports ...
    get_lifecycle_stats,
    get_lifecycle_by_bedrooms,
    get_lifecycle_by_price_range,
)

@router.get("/analytics")
async def admin_analytics(request: Request):
    # ... existing code ...

    # Lifecycle analytics (NEW)
    lifecycle_stats = get_lifecycle_stats()
    lifecycle_by_bedrooms = get_lifecycle_by_bedrooms()
    lifecycle_by_price = get_lifecycle_by_price_range()

    return templates.TemplateResponse(
        request,
        "admin/analytics.html",
        context={
            # ... existing context ...
            "lifecycle_stats": lifecycle_stats,
            "lifecycle_by_bedrooms": lifecycle_by_bedrooms,
            "lifecycle_by_price": lifecycle_by_price,
        },
    )
```

---

## Phase 2 — Frontend (Filter UI + Analytics Section)

### 2.1 — "Days Listed" Filter UI

#### Placement Recommendation

Add the "Days Listed" filter as a **new dropdown** in the filter bar, positioned **between Source and More**:

```
[💰 Price] [🛏️ Beds & Baths] [📡 Source] [📅 Days Listed] [⚙️ More]  |  [Sort ▾]  Admin →
```

**Rationale:**
- It's a distinct, single-purpose filter (like Price, unlike the catch-all "More")
- Placing it before "More" keeps "More" as the last dropdown for miscellaneous filters
- It's a common search criterion that deserves first-class visibility
- The 📅 emoji provides clear visual identification

#### Hidden Input — [`web/templates/dashboard.html`](../web/templates/dashboard.html:13)

Add after the existing hidden inputs (line ~33):

```html
<input type="hidden" name="filter_max_days" id="filter_max_days"
       value="{{ active_filters.filter_max_days }}">
```

#### Dropdown HTML — [`web/templates/dashboard.html`](../web/templates/dashboard.html:228)

Insert after the Source dropdown closing `</div>` (line ~228), before the More dropdown:

```html
<!-- ===== Days Listed Dropdown ===== -->
<div class="filter-dropdown" data-filter="days">
    <button type="button"
            class="filter-pill{% if active_filters.filter_max_days %} active{% endif %}"
            aria-expanded="false"
            aria-haspopup="dialog"
            aria-label="Days on market filter"
            id="pill-days">
        <span class="filter-pill-text" data-default="📅 Days Listed">
            {%- if active_filters.filter_max_days -%}
                ≤{{ active_filters.filter_max_days }}d
            {%- else -%}
                📅 Days Listed
            {%- endif -%}
        </span>
        <svg class="filter-pill-arrow" width="10" height="6" viewBox="0 0 10 6" aria-hidden="true">
            <path d="M0 0l5 6 5-6z" fill="currentColor"/>
        </svg>
    </button>
    <div class="filter-panel" role="dialog" aria-label="Days on market filter" id="panel-days">
        <div class="filter-panel-header">Max Days on Market</div>
        <div class="filter-radio-group" role="radiogroup" aria-label="Days listed presets">
            <label class="filter-radio">
                <input type="radio" name="days-preset" value=""
                       {{ 'checked' if not active_filters.filter_max_days }}>
                <span class="filter-radio-label">Any</span>
            </label>
            <label class="filter-radio">
                <input type="radio" name="days-preset" value="7"
                       {{ 'checked' if active_filters.filter_max_days == '7' }}>
                <span class="filter-radio-label">≤ 7 days</span>
            </label>
            <label class="filter-radio">
                <input type="radio" name="days-preset" value="14"
                       {{ 'checked' if active_filters.filter_max_days == '14' }}>
                <span class="filter-radio-label">≤ 14 days</span>
            </label>
            <label class="filter-radio">
                <input type="radio" name="days-preset" value="30"
                       {{ 'checked' if active_filters.filter_max_days == '30' }}>
                <span class="filter-radio-label">≤ 30 days</span>
            </label>
            <label class="filter-radio">
                <input type="radio" name="days-preset" value="60"
                       {{ 'checked' if active_filters.filter_max_days == '60' }}>
                <span class="filter-radio-label">≤ 60 days</span>
            </label>
        </div>

        <div class="filter-panel-divider"></div>

        <div class="filter-panel-header">Custom</div>
        <div class="filter-panel-row">
            <div class="filter-input-group">
                <label for="days-custom-input" class="sr-only">Custom max days</label>
                <input type="text" id="days-custom-input" class="filter-input"
                       inputmode="numeric" placeholder="e.g. 45"
                       value="{{ active_filters.filter_max_days if active_filters.filter_max_days not in ('', '7', '14', '30', '60') else '' }}">
            </div>
            <span class="filter-input-suffix">days</span>
        </div>

        <button type="button" class="filter-apply-btn"
                hx-get="/listings" hx-target="#listing-cards"
                hx-include="[name^='filter_']"
                hx-trigger="apply"
                data-panel="days">
            Apply
        </button>
    </div>
</div>
```

#### JavaScript — [`web/static/js/filters.js`](../web/static/js/filters.js)

Add snapshot/revert and apply logic for the `days` filter. Follow the existing pattern:

**Snapshot** (in [`snapshotValues()`](../web/static/js/filters.js:107)):

```javascript
case "days":
    snap.max_days = document.getElementById("filter_max_days").value;
    break;
```

**Revert** (in [`revertValues()`](../web/static/js/filters.js:131)):

```javascript
case "days":
    document.getElementById("filter_max_days").value = snap.max_days;
    // Also revert radio + custom input
    const radios = document.querySelectorAll('input[name="days-preset"]');
    radios.forEach(r => r.checked = (r.value === snap.max_days));
    document.getElementById("days-custom-input").value =
        ["", "7", "14", "30", "60"].includes(snap.max_days) ? "" : snap.max_days;
    break;
```

**Apply** (in [`applyFilter()`](../web/static/js/filters.js:333)):

```javascript
case "days": {
    // Custom input takes precedence over radio presets
    const customVal = document.getElementById("days-custom-input").value.trim();
    let val = "";
    if (customVal && !isNaN(customVal)) {
        val = customVal;
    } else {
        const checked = document.querySelector('input[name="days-preset"]:checked');
        val = checked ? checked.value : "";
    }
    document.getElementById("filter_max_days").value = val;
    break;
}
```

**Radio ↔ Custom input interaction:**
- When a radio preset is selected → clear the custom input
- When the custom input receives a value → deselect all radio presets
- Add event listeners for both in the initialization block

**Reset all filters** (in the reset handler, line ~569):
```javascript
document.getElementById("filter_max_days").value = "";
```

#### Pill Text Update

Update the pill text dynamically after apply, following the pattern used by Price:
- If a value is set: show `≤{N}d` (e.g., "≤30d")
- If "Any": show default text "📅 Days Listed"
- Add `.active` class to pill when filter is active

#### CSS — [`web/static/css/style.css`](../web/static/css/style.css)

Minimal CSS additions needed:
- `.filter-input-suffix` — styled inline text after the custom input ("days" label)
- `.filter-radio` / `.filter-radio-label` — if not already styled (check if radio styles exist from Beds & Baths)

**Remember:** Bump `?v=N` in [`web/templates/base.html`](../web/templates/base.html) per [CSS Cache Versioning](../docs/memory/wiki/concepts/css-cache-versioning.md).

### 2.2 — Listing Lifecycle Analytics Section

#### Template — [`web/templates/admin/analytics.html`](../web/templates/admin/analytics.html:167)

Add a new section **after** the Inventory Timeline section (line ~167), before `{% endblock %}`:

```html
<!-- Listing Lifecycle -->
<div class="section">
    <h2 class="section-title">📊 Listing Lifecycle</h2>
    <p class="section-subtitle">How long do listings stay on the market before being removed?</p>
</div>

<!-- Lifecycle KPI Cards -->
<div class="kpi-grid kpi-grid-3">
    <div class="kpi-card kpi-blue">
        <div class="kpi-label">Avg Lifespan</div>
        <div class="kpi-value">{{ "%.1f"|format(lifecycle_stats.avg_lifespan_days) }}d</div>
    </div>
    <div class="kpi-card kpi-purple">
        <div class="kpi-label">Median Lifespan</div>
        <div class="kpi-value">{{ "%.1f"|format(lifecycle_stats.median_lifespan_days) }}d</div>
    </div>
    <div class="kpi-card kpi-teal">
        <div class="kpi-label">Total Removed</div>
        <div class="kpi-value">{{ lifecycle_stats.total_removed }}</div>
    </div>
</div>

<!-- Two-column: Lifespan by Bedrooms + Lifespan by Price Range -->
<div class="two-col">
    <!-- Lifespan by Bedrooms -->
    <div class="section">
        <h2 class="section-title">Lifespan by Bedrooms</h2>
        {% if lifecycle_by_bedrooms %}
        <div class="chart-bars">
            {% set max_life_br = lifecycle_by_bedrooms|map(attribute='avg_days')|max %}
            {% for item in lifecycle_by_bedrooms %}
            <div class="bar-row">
                <span class="bar-label">{{ item.bedrooms }} BR ({{ item.count }})</span>
                <div class="bar-track">
                    <div class="bar-fill bar-fill-blue"
                         style="width: {{ (item.avg_days / max_life_br * 100)|round }}%"></div>
                </div>
                <span class="bar-value">{{ "%.1f"|format(item.avg_days) }}d</span>
            </div>
            {% endfor %}
        </div>
        {% else %}
        <div class="empty-state"><p>No lifecycle data available.</p></div>
        {% endif %}
    </div>

    <!-- Lifespan by Price Range -->
    <div class="section">
        <h2 class="section-title">Lifespan by Price Range</h2>
        {% if lifecycle_by_price %}
        <div class="chart-bars">
            {% set max_life_pr = lifecycle_by_price|map(attribute='avg_days')|max %}
            {% for item in lifecycle_by_price %}
            <div class="bar-row">
                <span class="bar-label">{{ item.range }} ({{ item.count }})</span>
                <div class="bar-track">
                    <div class="bar-fill bar-fill-purple"
                         style="width: {{ (item.avg_days / max_life_pr * 100)|round }}%"></div>
                </div>
                <span class="bar-value">{{ "%.1f"|format(item.avg_days) }}d</span>
            </div>
            {% endfor %}
        </div>
        {% else %}
        <div class="empty-state"><p>No lifecycle data available.</p></div>
        {% endif %}
    </div>
</div>
```

**Design notes:**
- Reuses existing CSS classes: `kpi-grid`, `kpi-card`, `chart-bars`, `bar-row`, `two-col`
- Uses `bar-fill-blue` for bedrooms, `bar-fill-purple` for price range (consistent with existing analytics)
- Bar labels include count in parentheses for context: "3 BR (8)"
- Values shown as days with 1 decimal: "12.5d"
- Empty states handled with existing `.empty-state` pattern

---

## Affected Files

### Phase 1 — Backend

| File | Change | Lines |
|------|--------|-------|
| [`src/models.py`](../src/models.py:160) | Add `deactivated_at` column | ~161 |
| [`src/database.py`](../src/database.py:71) | Add `_ensure_deactivated_at_column()` migration | After line ~88 |
| [`src/database.py`](../src/database.py:132) | Call migration from `init_db()` | ~143 |
| [`src/database.py`](../src/database.py:742) | Update `mark_inactive()` to set `deactivated_at` | ~761 |
| [`src/database.py`](../src/database.py:175) | Add `max_days_listed` to `_apply_listing_filters()` | After ~278 |
| [`src/database.py`](../src/database.py) | Add `get_lifecycle_stats()` | New function |
| [`src/database.py`](../src/database.py) | Add `get_lifecycle_by_bedrooms()` | New function |
| [`src/database.py`](../src/database.py) | Add `get_lifecycle_by_price_range()` | New function |
| [`src/database.py`](../src/database.py) | Add `deactivated_at` to upsert exclusion tuples | In `upsert_listing()` |
| [`web/routes/__init__.py`](../web/routes/__init__.py:6) | Add `filter_max_days` to `parse_filters()` | ~6, ~101 |
| [`web/routes/listings.py`](../web/routes/listings.py:20) | Add `filter_max_days` query param | ~20, ~38 |
| [`web/routes/dashboard.py`](../web/routes/dashboard.py:23) | Add `filter_max_days` to defaults | ~23, ~42 |
| [`web/routes/admin.py`](../web/routes/admin.py:24) | Import + call lifecycle functions | ~24, ~273 |

### Phase 2 — Frontend

| File | Change |
|------|--------|
| [`web/templates/dashboard.html`](../web/templates/dashboard.html:13) | Add hidden input + Days Listed dropdown |
| [`web/static/js/filters.js`](../web/static/js/filters.js) | Snapshot/revert/apply for `days` filter |
| [`web/static/css/style.css`](../web/static/css/style.css) | `.filter-input-suffix`, radio styles if needed |
| [`web/templates/base.html`](../web/templates/base.html) | Bump CSS `?v=N` |
| [`web/templates/admin/analytics.html`](../web/templates/admin/analytics.html:167) | Add Listing Lifecycle section |

---

## Data Flow Diagrams

### Days-on-Market Filter Flow

```
User selects "≤30 days"
        │
        ▼
[dashboard.html]  radio/custom input
        │
        ▼
[filters.js]  applyFilter("days")
  → sets hidden input filter_max_days = "30"
  → dispatches CustomEvent("apply")
        │
        ▼
[HTMX]  GET /listings?filter_max_days=30&...
        │
        ▼
[listings.py]  filtered_listings()
  → parse_filters(filter_max_days="30")
  → filters = {..., "max_days_listed": 30}
        │
        ▼
[database.py]  get_filtered_listings(filters)
  → _apply_listing_filters(query, filters)
  → query.filter(Listing.days_on_market <= 30)
        │
        ▼
[listing-cards.html]  HTMX swap
```

### Lifecycle Analytics Flow

```
Admin visits /admin/analytics
        │
        ▼
[admin.py]  admin_analytics()
  → get_lifecycle_stats()
  → get_lifecycle_by_bedrooms()
  → get_lifecycle_by_price_range()
        │
        ▼
[database.py]  SQL queries on inactive listings
  → julianday(COALESCE(deactivated_at, last_seen)) - julianday(first_seen)
        │
        ▼
[analytics.html]  Render KPI cards + bar charts
```

### Deactivation Timestamp Flow

```
Scraper run completes
        │
        ▼
[orchestrator.py]  mark_inactive(source, active_ids)
        │
        ▼
[database.py]  mark_inactive()
  → UPDATE listings SET
      is_active = False,
      deactivated_at = NOW()    ← NEW
    WHERE source = ? AND is_active = True
      AND external_id NOT IN (?)
```

---

## Implementation Notes

### Edge Cases

1. **Listings with NULL `days_on_market`:** The filter excludes them (`Listing.days_on_market.isnot(None)`). This is correct — if we don't know how long it's been listed, we can't filter on it.

2. **Re-activation:** If a listing reappears after being marked inactive, `deactivated_at` should be cleared. This would happen in `upsert_listing()` when `is_active` is set back to `True`. Add: `if listing was inactive and is now active, set deactivated_at = None`.

3. **Lifecycle stats with 0 inactive listings:** Return sensible defaults (all zeros) to avoid division-by-zero in templates.

4. **Price buckets with 0 listings:** Skip empty buckets in the bar chart (same pattern as existing price distribution).

### Performance

- All lifecycle queries operate on inactive listings only (currently 30 rows) — no performance concern
- `days_on_market` filter is a simple integer comparison on an existing column — fast
- No new indexes needed at current data volumes

### Testing Checklist

- [ ] `deactivated_at` column added idempotently (run `init_db()` twice)
- [ ] `mark_inactive()` sets `deactivated_at` for newly inactive listings
- [ ] `mark_inactive()` does NOT overwrite `deactivated_at` for already-inactive listings
- [ ] `parse_filters(filter_max_days="30")` produces `{"max_days_listed": 30}`
- [ ] `parse_filters(filter_max_days="any")` produces no `max_days_listed` key
- [ ] `_apply_listing_filters()` correctly filters by `days_on_market <= N`
- [ ] Lifecycle stats handle 0 inactive listings gracefully
- [ ] Lifecycle stats use `COALESCE(deactivated_at, last_seen)` for legacy data
- [ ] Filter UI radio presets work correctly
- [ ] Filter UI custom input overrides radio presets
- [ ] Snapshot/revert works for Days Listed filter
- [ ] Reset all filters clears Days Listed

---

## Wiki Impact

- **Updated entities:**
  - [`database-schema.md`](../docs/memory/wiki/entities/database-schema.md) — new `deactivated_at` column, 3 new query functions
  - [`filter-bar.md`](../docs/memory/wiki/entities/filter-bar.md) — new "Days Listed" dropdown
  - [`admin-dashboard.md`](../docs/memory/wiki/entities/admin-dashboard.md) — new Listing Lifecycle analytics section
- **New concepts:** None (uses existing patterns)
- **New entities:** None
