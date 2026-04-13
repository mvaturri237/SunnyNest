# School Assignment Lookup by Address

> **Feature**: Show the actual elementary, middle, and high schools each listing is assigned to — not just the district name.  
> **Status**: PROPOSAL  
> **Created**: 2026-03-31  
> **Author**: Architect  
> **Scope**: Sunnyvale, CA (ZIP codes 94085, 94086, 94087, 94089)

---

## Table of Contents

1. [Overview](#1-overview)
2. [Current State](#2-current-state)
3. [Data Acquisition](#3-data-acquisition)
4. [Database Schema Changes](#4-database-schema-changes)
5. [School Lookup Module](#5-school-lookup-module)
6. [Orchestrator Integration](#6-orchestrator-integration)
7. [UI Changes](#7-ui-changes)
8. [Backfill Script](#8-backfill-script)
9. [Dependencies](#9-dependencies)
10. [Testing Strategy](#10-testing-strategy)
11. [Implementation Phases](#11-implementation-phases)
12. [Open Questions](#12-open-questions)

---

## 1. Overview

### Problem

[`src/school_districts.py`](../src/school_districts.py) currently maps ZIP codes to district names (e.g., "Sunnyvale School District / Fremont Union High School District"). This tells parents *which district* but not *which specific school* their child would attend. School assignment is determined by **attendance zone boundaries** — geographic polygons — not ZIP codes.

### Solution

Use **NCES School Attendance Boundary Survey (SABS)** GeoJSON data to perform point-in-polygon lookups against each listing's existing `latitude`/`longitude` coordinates. This yields the specific elementary, middle, and high school assigned to each address.

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    Scrape Pipeline                           │
│                                                             │
│  Raw Listing → Normalize → Geocode → School Lookup → Upsert│
│                              │              │               │
│                         lat/lng         ┌───┴───┐           │
│                                         │Shapely│           │
│                                         │ PIP   │           │
│                                         └───┬───┘           │
│                                             │               │
│                              ┌──────────────┴────────────┐  │
│                              │  data/school-boundaries/  │  │
│                              │  ├─ elementary.geojson    │  │
│                              │  ├─ middle.geojson        │  │
│                              │  └─ high.geojson          │  │
│                              └───────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    SQLite Database                           │
│                                                             │
│  listings table:                                            │
│    school_district    TEXT  (existing — keep)                │
│    school_elementary  TEXT  (new)                            │
│    school_middle      TEXT  (new)                            │
│    school_high        TEXT  (new)                            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Listing Card UI                           │
│                                                             │
│  🏫 Sunnyvale Elementary · Sunnyvale Middle · Fremont HS   │
│  (replaces generic district name in location line)          │
└─────────────────────────────────────────────────────────────┘
```

### Sunnyvale School Districts Reference

| District | Level | ZIP Codes Served | Notes |
|----------|-------|-----------------|-------|
| **Sunnyvale School District (SSD)** | Elementary + Middle | 94085, 94086, 94089 | ~8 elementary, 2 middle schools |
| **Cupertino Union School District (CUSD)** | Elementary + Middle | 94087 | ~25 elementary, 5 middle schools (district-wide) |
| **Fremont Union High School District (FUHSD)** | High School | 94085, 94086, 94087, 94089 | 5 high schools serving all Sunnyvale |

---

## 2. Current State

### What exists today

| Component | File | Current Behavior |
|-----------|------|-----------------|
| Lookup module | [`src/school_districts.py`](../src/school_districts.py) | `_ZIP_TO_DISTRICT` dict → [`get_school_district(zip_code)`](../src/school_districts.py:25) returns district name string |
| Model | [`src/models.py`](../src/models.py:142) | Single `school_district` column (`Text`, nullable) |
| Orchestrator | [`src/orchestrator.py`](../src/orchestrator.py:128) | Calls `get_school_district(zip_code)` at enrichment step 3 (lines 128–133) |
| UI | [`web/templates/partials/listing-card.html`](../web/templates/partials/listing-card.html:157) | Displays `listing.school_district` in location line (lines 157–162) |
| Geocoding | [`src/geocoder.py`](../src/geocoder.py) | Already populates `latitude`/`longitude` on listings |

### What's missing

- No attendance zone boundary data
- No point-in-polygon geometry capability
- No per-school-level columns in the database
- No `shapely` dependency

---

## 3. Data Acquisition

### 3.1 Primary Source: NCES SABS Data

The **School Attendance Boundary Survey (SABS)** is a free federal dataset published by the National Center for Education Statistics (NCES). It contains attendance zone polygons for most US public schools.

| Property | Value |
|----------|-------|
| **Publisher** | NCES / U.S. Department of Education |
| **URL** | https://nces.ed.gov/programs/edge/Geographic/SchoolLocations |
| **Direct download** | https://nces.ed.gov/programs/edge/data/SABS_2223.zip (2022–23 vintage) |
| **Format** | Shapefile (`.shp` + sidecar files) inside ZIP |
| **Coverage** | ~70% of US school districts participated |
| **License** | Public domain (federal government data) |
| **Size** | ~2 GB national dataset (compressed) |
| **Vintage** | 2022–23 school year (most recent as of 2026) |
| **Update frequency** | Approximately every 2 years |

> **Note**: Check https://nces.ed.gov/programs/edge/Geographic/SchoolLocations for newer vintages. The 2024–25 survey may be available by the time this is implemented.

### 3.2 Alternative Source: California Department of Education

If SABS doesn't cover a specific Sunnyvale school (participation is voluntary):

| Property | Value |
|----------|-------|
| **Publisher** | California Department of Education (CDE) |
| **School directory** | https://www.cde.ca.gov/ds/si/ds/pubschls.asp |
| **District boundaries** | Available via CA GIS portal |
| **Format** | CSV (school list) + Shapefile (boundaries) |

### 3.3 Fallback: Manual Boundary Definition

For schools not covered by SABS or CDE data:

1. Visit each district's website for attendance zone maps:
   - SSD: https://www.sesd.org/ → "Schools" → attendance boundaries
   - CUSD: https://www.cusdk8.org/ → "Schools" → boundary maps
   - FUHSD: https://www.fuhsd.org/ → "Schools" → attendance areas
2. Trace boundaries manually into GeoJSON using https://geojson.io
3. Store in `data/school-boundaries/manual-overrides/` directory

### 3.4 Data Extraction Pipeline

Since the national SABS dataset is ~2 GB, we extract only Sunnyvale-area polygons:

#### Storage Layout

```
data/school-boundaries/
├── README.md                    # Data provenance, vintage, refresh instructions
├── elementary.geojson           # Extracted elementary school zones
├── middle.geojson               # Extracted middle school zones
├── high.geojson                 # Extracted high school zones
└── manual-overrides/            # Hand-drawn boundaries for missing schools
    └── .gitkeep
```

#### Extraction Script: `scripts/prepare_school_boundaries.py`

```python
"""Download SABS national shapefile, extract Sunnyvale-area attendance zones,
and save as GeoJSON files split by school level.

Usage:
    python scripts/prepare_school_boundaries.py

Requirements:
    pip install geopandas shapely requests
    (geopandas is a BUILD-TIME dependency only — not needed at runtime)
"""

# Pseudocode — actual implementation in Code mode:
#
# 1. Download SABS_2223.zip from NCES (or use cached local copy)
# 2. Extract shapefile from ZIP
# 3. Load with geopandas
# 4. Filter to Sunnyvale-area districts:
#    - LEA names containing "Sunnyvale", "Cupertino Union", "Fremont Union"
#    - OR bounding box filter: lat 37.33–37.42, lng -122.08 to -121.97
# 5. Split by school level (SABS has a "schLevel" field):
#    - "Elementary" → elementary.geojson
#    - "Middle" → middle.geojson
#    - "High" → high.geojson
# 6. Simplify polygons (tolerance=0.0001) to reduce file size
# 7. Save as GeoJSON with properties: school_name, nces_id, district_name
# 8. Write README.md with provenance metadata
```

#### Key SABS Shapefile Fields

| Field | Description | Example |
|-------|-------------|---------|
| `ncessch` | NCES school ID | `063441012345` |
| `schnam` | School name | `Sunnyvale Elementary` |
| `leaid` | District ID | `0634410` |
| `leanm` | District name | `Sunnyvale School District` |
| `stAbbrev` | State | `CA` |
| `schLevel` | School level | `Elementary`, `Middle`, `High` |
| `geometry` | Attendance zone polygon | MultiPolygon |

### 3.5 Data Freshness Strategy

| Concern | Strategy |
|---------|----------|
| **Vintage tracking** | Store vintage in `data/school-boundaries/README.md` header |
| **Refresh cadence** | Check NCES annually (August) for new SABS release |
| **Refresh process** | Re-run `scripts/prepare_school_boundaries.py` with new URL |
| **Boundary changes** | School districts occasionally redraw zones — re-extract when notified |
| **Git tracking** | GeoJSON files committed to repo (small after extraction — ~100 KB total) |

### 3.6 Expected Sunnyvale Schools

#### Sunnyvale School District (Elementary)
- Bishop Elementary
- Cherry Chase Elementary
- Cumberland Elementary
- Ellis Elementary
- Fairwood Elementary
- Lakewood Elementary
- San Miguel Elementary
- Vargas Elementary

#### Sunnyvale School District (Middle)
- Columbia Middle
- Sunnyvale Middle

#### Cupertino Union School District (Elementary — 94087 area)
- Eaton Elementary
- Garden Gate Elementary
- Nimitz Elementary
- Stocklmeir Elementary
- Stevens Creek Elementary (partial)

#### Cupertino Union School District (Middle — 94087 area)
- Cupertino Middle
- Hyde Middle
- Lawson Middle (partial)

#### Fremont Union High School District
- Cupertino High School
- Fremont High School
- Homestead High School
- Lynbrook High School
- Monta Vista High School

---

## 4. Database Schema Changes

### 4.1 New Columns on `Listing` Model

Add three new nullable `Text` columns to [`src/models.py`](../src/models.py:142), grouped with the existing `school_district` column:

```python
# --- Extra info ---
school_district: str | None = Column(Text, nullable=True)       # existing
school_elementary: str | None = Column(Text, nullable=True)      # NEW
school_middle: str | None = Column(Text, nullable=True)          # NEW
school_high: str | None = Column(Text, nullable=True)            # NEW
```

### 4.2 Migration Strategy

Follow the established pattern from [`_ensure_days_on_market_column()`](../src/database.py:71) — raw SQL `ALTER TABLE` with try/except for idempotency:

```python
def _ensure_school_columns() -> None:
    """Add school_elementary, school_middle, school_high columns if missing."""
    engine = get_engine()
    for col in ("school_elementary", "school_middle", "school_high"):
        try:
            with engine.connect() as conn:
                conn.execute(text(f"ALTER TABLE listings ADD COLUMN {col} TEXT"))
                conn.commit()
            logger.info("Added %s column to listings table.", col)
        except Exception:
            pass  # Column already exists
```

Register in [`init_db()`](../src/database.py:115):

```python
def init_db() -> None:
    engine = get_engine()
    Base.metadata.create_all(engine)
    _ensure_days_on_market_column()
    _migrate_to_listing_sources()
    _ensure_school_columns()          # ← NEW
    logger.info("Database tables initialised.")
```

### 4.3 Why Keep `school_district`?

- **Backward compatibility** — existing code and templates reference it
- **Complementary data** — district name is useful even when specific schools are shown
- **Fallback** — if boundary data doesn't cover a listing, district name from ZIP is still valuable
- **No migration risk** — adding columns is non-destructive; removing would require data migration

---

## 5. School Lookup Module

### 5.1 Module Design: [`src/school_districts.py`](../src/school_districts.py)

Extend the existing module with a new `get_assigned_schools()` function while keeping [`get_school_district()`](../src/school_districts.py:25) intact.

### 5.2 Architecture

```
src/school_districts.py
├── get_school_district(zip_code)          # EXISTING — unchanged
├── get_assigned_schools(lat, lng)         # NEW — point-in-polygon lookup
└── _SchoolBoundaryStore (lazy singleton)  # NEW — loads GeoJSON once
```

### 5.3 Lazy Singleton: `_SchoolBoundaryStore`

```python
class _SchoolBoundaryStore:
    """Loads school boundary GeoJSON files once and caches shapely geometries.
    
    Thread-safe lazy initialization. GeoJSON files are loaded on first call
    to get_assigned_schools(), not at module import time.
    """
    
    _instance: _SchoolBoundaryStore | None = None
    _lock: threading.Lock = threading.Lock()
    
    def __init__(self):
        self.boundaries: dict[str, list[SchoolZone]] = {
            "elementary": [],
            "middle": [],
            "high": [],
        }
        self._loaded = False
    
    @classmethod
    def get_instance(cls) -> _SchoolBoundaryStore:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance
    
    def _load(self) -> None:
        """Load GeoJSON files from data/school-boundaries/."""
        if self._loaded:
            return
        for level in ("elementary", "middle", "high"):
            path = Path("data/school-boundaries") / f"{level}.geojson"
            if path.exists():
                with open(path) as f:
                    geojson = json.load(f)
                for feature in geojson["features"]:
                    zone = SchoolZone(
                        name=feature["properties"]["school_name"],
                        nces_id=feature["properties"].get("nces_id"),
                        geometry=shape(feature["geometry"]),  # shapely
                    )
                    self.boundaries[level].append(zone)
                logger.info("Loaded %d %s school zones", 
                           len(self.boundaries[level]), level)
            else:
                logger.warning("School boundary file not found: %s", path)
        self._loaded = True
```

### 5.4 Data Class

```python
@dataclass
class SchoolZone:
    """A school attendance zone with its polygon geometry."""
    name: str
    nces_id: str | None
    geometry: BaseGeometry  # shapely Polygon or MultiPolygon
```

### 5.5 Lookup Function

```python
def get_assigned_schools(lat: float, lng: float) -> dict[str, str | None]:
    """Look up assigned schools for a geographic point.
    
    Args:
        lat: Latitude of the listing.
        lng: Longitude of the listing.
    
    Returns:
        Dict with keys "elementary", "middle", "high".
        Each value is the school name (str) or None if no boundary matched.
    
    Example:
        >>> get_assigned_schools(37.3688, -122.0363)
        {"elementary": "Cherry Chase Elementary", 
         "middle": "Columbia Middle", 
         "high": "Fremont High School"}
    """
    store = _SchoolBoundaryStore.get_instance()
    store._load()
    
    point = Point(lng, lat)  # Note: GeoJSON uses (lng, lat) order
    
    result: dict[str, str | None] = {
        "elementary": None,
        "middle": None,
        "high": None,
    }
    
    for level in ("elementary", "middle", "high"):
        for zone in store.boundaries[level]:
            if zone.geometry.contains(point):
                result[level] = zone.name
                break
    
    if all(v is None for v in result.values()):
        logger.debug(
            "No school boundaries matched for point (%s, %s)", lat, lng
        )
    
    return result
```

### 5.6 Edge Cases

| Edge Case | Handling |
|-----------|----------|
| **Listing outside all boundaries** | Return `{"elementary": None, "middle": None, "high": None}` — existing `school_district` from ZIP still shows |
| **Listing exactly on boundary edge** | `shapely.contains()` uses standard computational geometry — point on edge is typically `False`. Use `contains` (not `intersects`) for deterministic single-school assignment |
| **Multiple overlapping zones** | Take the first match. SABS zones should not overlap for the same level, but if they do, log a warning |
| **GeoJSON files missing** | Log warning, return all `None` — graceful degradation |
| **Invalid lat/lng** | Return all `None` — don't crash the pipeline |
| **Coordinate order** | GeoJSON uses `(longitude, latitude)` — `shapely.Point(lng, lat)` |

### 5.7 Performance Considerations

| Concern | Mitigation |
|---------|-----------|
| **GeoJSON load time** | Lazy singleton — loaded once, cached for process lifetime |
| **Memory footprint** | Sunnyvale-area only (~30 polygons) — negligible (~100 KB) |
| **Point-in-polygon speed** | Shapely uses GEOS C library — sub-millisecond per lookup |
| **Batch lookups** | For backfill, consider `shapely.STRtree` spatial index if >1000 listings |
| **Thread safety** | `threading.Lock` on singleton init; shapely geometries are read-only after load |

### 5.8 Optional: STRtree Optimization for Backfill

For the backfill script (processing all existing listings), use a spatial index:

```python
from shapely import STRtree

# Build spatial index once
tree = STRtree([zone.geometry for zone in zones])
# Query returns indices of candidate geometries
candidates = tree.query(point)
```

This reduces backfill from O(n × m) to O(n × log(m)) where n = listings, m = zones.

---

## 6. Orchestrator Integration

### 6.1 Changes to [`src/orchestrator.py`](../src/orchestrator.py)

Add a new enrichment step after the existing school district lookup (line 133):

```python
# 3. Enrich with school district (existing)
zip_code = normalized.get("zip_code", "")
if zip_code:
    district = get_school_district(zip_code)
    if district is not None:
        normalized["school_district"] = district

# 3b. Enrich with specific school assignments (NEW)
lat = normalized.get("latitude")
lng = normalized.get("longitude")
if lat is not None and lng is not None:
    schools = get_assigned_schools(lat, lng)
    if schools["elementary"]:
        normalized["school_elementary"] = schools["elementary"]
    if schools["middle"]:
        normalized["school_middle"] = schools["middle"]
    if schools["high"]:
        normalized["school_high"] = schools["high"]
```

### 6.2 Import Addition

Add to the imports at the top of [`src/orchestrator.py`](../src/orchestrator.py):

```python
from src.school_districts import get_school_district, get_assigned_schools
```

### 6.3 Pipeline Position

The school lookup must come **after** geocoding (step 2) since it depends on `latitude`/`longitude`:

```
Step 1:  Normalize raw listing
Step 1b: Filter invalid prices
Step 1c: Filter non-house types
Step 2:  Geocode address → lat/lng
Step 3:  ZIP → school district name (existing)
Step 3b: lat/lng → specific school names (NEW)
Step 4:  sqft → sqm conversion
Step 5:  Upsert to database
```

### 6.4 Failure Isolation

- If `get_assigned_schools()` raises an exception, catch and log it — don't block the listing from being saved
- The listing will still have `school_district` from the ZIP lookup
- Wrap in try/except matching the existing error handling pattern

---

## 7. UI Changes

### 7.1 Listing Card Update

Replace the current school district display in [`web/templates/partials/listing-card.html`](../web/templates/partials/listing-card.html:152) (lines 152–162):

**Current** (lines 157–162):
```html
{% if listing.school_district %}
    {% set _ = loc_parts.append(listing.school_district) %}
{% endif %}
```

**Proposed** — replace district string with compact school names:

```html
{# School assignments — show specific schools if available, fall back to district #}
{% set has_schools = listing.school_elementary or listing.school_middle or listing.school_high %}
{% if has_schools %}
    {% set school_parts = [] %}
    {% if listing.school_elementary %}
        {% set _ = school_parts.append('🏫 ' ~ listing.school_elementary) %}
    {% endif %}
    {% if listing.school_middle %}
        {% set _ = school_parts.append(listing.school_middle) %}
    {% endif %}
    {% if listing.school_high %}
        {% set _ = school_parts.append(listing.school_high) %}
    {% endif %}
    {% set _ = loc_parts.append(school_parts | join(' · ')) %}
{% elif listing.school_district %}
    {% set _ = loc_parts.append(listing.school_district) %}
{% endif %}
```

### 7.2 Display Design Decision

**Option A: Inline in location line** (recommended for Phase 1)
```
📍 Downtown Sunnyvale
🏫 Cherry Chase Elem · Columbia Middle · Fremont HS
```
- Compact — fits existing card layout
- Abbreviate "Elementary" → "Elem", "High School" → "HS" to save space
- Single 🏫 emoji prefix for the school line

**Option B: Tooltip/expandable** (future enhancement)
```
📍 Downtown Sunnyvale · 🏫 3 schools ▾
   ┌─────────────────────────────────┐
   │ Elementary: Cherry Chase Elem   │
   │ Middle:     Columbia Middle     │
   │ High:       Fremont HS         │
   └─────────────────────────────────┘
```
- Cleaner card but requires click/hover interaction
- Better for mobile where horizontal space is limited
- Consider for Phase 2

### 7.3 CSS Additions

```css
.card-schools {
    font-size: 12px;
    color: var(--text-muted);
    line-height: 1.4;
    margin-top: 2px;
}
```

### 7.4 Abbreviation Helper

To keep school names compact on cards, apply abbreviations in the template or via a Jinja2 filter:

| Full Name | Abbreviated |
|-----------|-------------|
| `... Elementary School` | `... Elem` |
| `... Elementary` | `... Elem` |
| `... Middle School` | `... Middle` |
| `... High School` | `... HS` |

Consider a Jinja2 custom filter `abbreviate_school` registered in [`web/dependencies.py`](../web/dependencies.py).

### 7.5 Design Bible Compliance

Per [`docs/design/design-bible.md`](../docs/design/design-bible.md):
- Font: Inter (already in use)
- Color: `var(--text-muted)` (#718096) for school names — secondary information
- Max 3 badges per card — schools go in location line, not badges
- Accessibility: school names are plain text, no color-only indicators

---

## 8. Backfill Script

### 8.1 Script: `scripts/backfill_schools.py`

Retroactively populate `school_elementary`, `school_middle`, `school_high` for all existing listings that have `latitude` and `longitude`.

```python
"""Backfill school assignments for existing listings.

Usage:
    python scripts/backfill_schools.py [--dry-run]

Idempotent — safe to re-run. Only updates listings where at least one
school column is NULL and lat/lng are available.
"""

# Pseudocode:
#
# 1. Initialize database (ensures columns exist)
# 2. Query all listings WHERE latitude IS NOT NULL 
#    AND longitude IS NOT NULL
#    AND (school_elementary IS NULL 
#         OR school_middle IS NULL 
#         OR school_high IS NULL)
# 3. For each listing:
#    a. Call get_assigned_schools(lat, lng)
#    b. Update non-None results
#    c. Commit in batches of 50
# 4. Print summary: X listings updated, Y skipped (no boundary match)
```

### 8.2 Idempotency

- Only processes listings with at least one NULL school column
- Never overwrites existing non-NULL values (unless `--force` flag)
- Safe to re-run after adding new boundary data

### 8.3 Dry Run Mode

`--dry-run` flag prints what would be updated without committing:

```
[DRY RUN] Listing #42 (123 Main St): Cherry Chase Elem / Columbia Middle / Fremont HS
[DRY RUN] Listing #43 (456 Oak Ave): No boundary match — skipping
...
Summary: 38 would be updated, 2 no match, 0 already populated
```

### 8.4 Performance

- Expected volume: ~50–200 existing listings (small dataset)
- STRtree spatial index not strictly necessary but good practice
- Batch commits every 50 listings to avoid long transactions
- Estimated runtime: <5 seconds for 200 listings

---

## 9. Dependencies

### 9.1 Runtime Dependencies

Add to [`requirements.txt`](../requirements.txt):

```
shapely>=2.0.0
```

**Why `shapely`?**
- Industry-standard Python library for computational geometry
- Uses GEOS C library under the hood — fast point-in-polygon
- No external service calls — fully offline lookups
- Already well-maintained, stable API

**Why NOT `geopandas`?**
- `geopandas` is heavy (pulls in `pandas`, `numpy`, `fiona`, `pyproj`)
- Only needed for the one-time data extraction script, not runtime
- Keep it as a dev/build dependency only

### 9.2 Build-Time Dependencies (not in requirements.txt)

For `scripts/prepare_school_boundaries.py` only:

```
geopandas>=0.14.0
fiona>=1.9.0
requests>=2.31.0
```

Install manually when running the extraction script:
```bash
pip install geopandas fiona requests
```

### 9.3 Standard Library Dependencies

- `json` — GeoJSON parsing
- `threading` — singleton lock
- `dataclasses` — `SchoolZone` data class
- `pathlib` — file path handling

---

## 10. Testing Strategy

### 10.1 Boundary Data Verification

| Test | Method |
|------|--------|
| **Visual inspection** | Load extracted GeoJSON into https://geojson.io and overlay on Google Maps — verify zones align with known school boundaries |
| **Known address spot-check** | Test 5–10 known Sunnyvale addresses against their actual school assignments (verify with district websites) |
| **Coverage check** | Ensure every Sunnyvale ZIP code has at least one school zone for each level |
| **No gaps** | Union of all elementary zones should cover the Sunnyvale city boundary |

### 10.2 Unit Tests for Point-in-Polygon

```python
# tests/test_school_districts.py

def test_known_address_cherry_chase():
    """Cherry Chase Elementary zone — known address."""
    result = get_assigned_schools(37.3688, -122.0363)
    assert result["elementary"] == "Cherry Chase Elementary"

def test_outside_sunnyvale():
    """Point in San Jose — should return all None."""
    result = get_assigned_schools(37.3382, -121.8863)
    assert result == {"elementary": None, "middle": None, "high": None}

def test_all_three_levels():
    """Every Sunnyvale point should match one school per level."""
    result = get_assigned_schools(37.3688, -122.0363)
    assert result["elementary"] is not None
    assert result["middle"] is not None
    assert result["high"] is not None

def test_boundary_edge():
    """Point exactly on a boundary edge — should not crash."""
    # Use a known boundary vertex coordinate
    result = get_assigned_schools(37.3700, -122.0400)
    # May return None for that level — that's acceptable
    assert isinstance(result, dict)

def test_invalid_coordinates():
    """Invalid lat/lng should return all None, not crash."""
    result = get_assigned_schools(0.0, 0.0)
    assert result == {"elementary": None, "middle": None, "high": None}

def test_missing_geojson_files(tmp_path, monkeypatch):
    """Missing boundary files should log warning, return all None."""
    monkeypatch.setattr(...)  # Point to empty tmp_path
    result = get_assigned_schools(37.3688, -122.0363)
    assert result == {"elementary": None, "middle": None, "high": None}
```

### 10.3 Integration Tests

| Test | Validates |
|------|-----------|
| **Orchestrator enrichment** | New listing with lat/lng gets school columns populated |
| **Orchestrator without lat/lng** | Listing without geocoding skips school lookup gracefully |
| **Backfill script** | Running backfill on test DB populates expected schools |
| **Backfill idempotency** | Running backfill twice produces same result |
| **UI rendering** | Listing card shows school names when populated |
| **UI fallback** | Listing card shows district name when school columns are NULL |

### 10.4 Spot-Check Addresses

Use these real Sunnyvale addresses to verify boundary data accuracy:

| Address | Expected Elementary | Expected Middle | Expected High |
|---------|-------------------|-----------------|---------------|
| 600 S Bernardo Ave, 94087 | Nimitz Elementary | Cupertino Middle | Homestead HS |
| 1120 Aster Ave, 94086 | Cherry Chase Elementary | Columbia Middle | Fremont HS |
| 820 E Duane Ave, 94085 | San Miguel Elementary | Columbia Middle | Fremont HS |
| 1200 Lakewood Dr, 94089 | Lakewood Elementary | Sunnyvale Middle | Fremont HS |

> **Important**: Verify these against district websites before using as test fixtures. Boundaries may have changed.

---

## 11. Implementation Phases

### Phase 1: Data Acquisition + Boundary Extraction
**Estimated effort**: 3–4 hours

| Task | Details |
|------|---------|
| Download SABS data | Fetch `SABS_2223.zip` from NCES |
| Write extraction script | `scripts/prepare_school_boundaries.py` |
| Extract Sunnyvale zones | Filter national dataset to 3 districts |
| Validate visually | Load into geojson.io, compare with district maps |
| Commit GeoJSON files | `data/school-boundaries/*.geojson` |
| Write README | Data provenance, vintage, refresh instructions |

**Deliverables**: `data/school-boundaries/elementary.geojson`, `middle.geojson`, `high.geojson`, `README.md`

### Phase 2: Schema + Lookup Module
**Estimated effort**: 2–3 hours

| Task | Details |
|------|---------|
| Add model columns | `school_elementary`, `school_middle`, `school_high` in [`src/models.py`](../src/models.py:142) |
| Add migration function | `_ensure_school_columns()` in [`src/database.py`](../src/database.py) |
| Register in `init_db()` | Call `_ensure_school_columns()` |
| Add `shapely` to requirements | [`requirements.txt`](../requirements.txt) |
| Implement `_SchoolBoundaryStore` | Lazy singleton in [`src/school_districts.py`](../src/school_districts.py) |
| Implement `get_assigned_schools()` | Point-in-polygon lookup function |
| Write unit tests | `tests/test_school_districts.py` |

**Deliverables**: Updated `src/school_districts.py`, `src/models.py`, `src/database.py`, `requirements.txt`, `tests/test_school_districts.py`

### Phase 3: Orchestrator Integration + Backfill
**Estimated effort**: 1–2 hours

| Task | Details |
|------|---------|
| Update orchestrator | Add step 3b in [`src/orchestrator.py`](../src/orchestrator.py:128) |
| Add import | `get_assigned_schools` import |
| Write backfill script | `scripts/backfill_schools.py` |
| Run backfill | Populate existing listings |
| Verify results | Spot-check 5 listings in DB |

**Deliverables**: Updated `src/orchestrator.py`, `scripts/backfill_schools.py`

### Phase 4: UI Display
**Estimated effort**: 1–2 hours

| Task | Details |
|------|---------|
| Update listing card | Show school names in [`listing-card.html`](../web/templates/partials/listing-card.html:152) |
| Add abbreviation filter | `abbreviate_school` Jinja2 filter in [`web/dependencies.py`](../web/dependencies.py) |
| Add CSS | `.card-schools` styles in [`web/static/css/style.css`](../web/static/css/style.css) |
| Test rendering | Verify cards display correctly with/without school data |

**Deliverables**: Updated `listing-card.html`, `style.css`, `web/dependencies.py`

### Total Estimated Effort: 7–11 hours

```
Phase 1 ████████░░░░░░░░░░░░  3-4h  Data acquisition
Phase 2 ██████░░░░░░░░░░░░░░  2-3h  Schema + module
Phase 3 ████░░░░░░░░░░░░░░░░  1-2h  Integration
Phase 4 ████░░░░░░░░░░░░░░░░  1-2h  UI
        ────────────────────
Total:                        7-11h
```

---

## 12. Open Questions

| # | Question | Recommendation | Impact |
|---|----------|---------------|--------|
| 1 | **SABS coverage**: Do all 3 Sunnyvale districts participate in SABS? | Check after downloading. If not, use manual boundary fallback (§3.3) | Phase 1 scope |
| 2 | **School name format**: Should we store full names ("Cherry Chase Elementary School") or abbreviated ("Cherry Chase Elem")? | Store full names in DB, abbreviate in UI via Jinja2 filter | Data integrity |
| 3 | **Map popup**: Should school names also appear in the map marker popup? | Yes, but defer to Phase 2 of UI work | UI scope |
| 4 | **Filter by school**: Should users be able to filter listings by assigned school? | Valuable feature but separate plan — defer | Future feature |
| 5 | **SABS vintage**: The 2022–23 data may be outdated. Should we check for 2024–25? | Check NCES website during Phase 1. Use latest available | Data accuracy |
| 6 | **Notification email**: Should new listing notifications include school assignments? | Yes — add to email template. Low effort, high value | Notification scope |

---

## Appendix A: File Change Summary

| File | Change Type | Description |
|------|------------|-------------|
| [`src/school_districts.py`](../src/school_districts.py) | **Modify** | Add `_SchoolBoundaryStore`, `SchoolZone`, `get_assigned_schools()` |
| [`src/models.py`](../src/models.py) | **Modify** | Add 3 columns: `school_elementary`, `school_middle`, `school_high` |
| [`src/database.py`](../src/database.py) | **Modify** | Add `_ensure_school_columns()`, register in `init_db()` |
| [`src/orchestrator.py`](../src/orchestrator.py) | **Modify** | Add step 3b: school assignment enrichment |
| [`web/templates/partials/listing-card.html`](../web/templates/partials/listing-card.html) | **Modify** | Show school names in location line |
| [`web/dependencies.py`](../web/dependencies.py) | **Modify** | Add `abbreviate_school` Jinja2 filter |
| [`web/static/css/style.css`](../web/static/css/style.css) | **Modify** | Add `.card-schools` styles |
| [`requirements.txt`](../requirements.txt) | **Modify** | Add `shapely>=2.0.0` |
| `data/school-boundaries/elementary.geojson` | **Create** | Elementary school attendance zones |
| `data/school-boundaries/middle.geojson` | **Create** | Middle school attendance zones |
| `data/school-boundaries/high.geojson` | **Create** | High school attendance zones |
| `data/school-boundaries/README.md` | **Create** | Data provenance and refresh instructions |
| `scripts/prepare_school_boundaries.py` | **Create** | SABS data extraction script |
| `scripts/backfill_schools.py` | **Create** | Backfill existing listings |
| `tests/test_school_districts.py` | **Create** | Unit tests for school lookup |

## Appendix B: Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| SABS doesn't cover Sunnyvale districts | Low | High | Manual boundary fallback (§3.3) |
| Boundary data is outdated | Medium | Medium | Document vintage, annual refresh check |
| `shapely` install issues on some platforms | Low | Medium | `shapely>=2.0` uses binary wheels — no C compiler needed |
| Performance regression in scrape pipeline | Very Low | Low | Sub-millisecond lookups, lazy loading |
| Incorrect school assignments | Medium | Medium | Spot-check validation (§10.4), user feedback mechanism |
