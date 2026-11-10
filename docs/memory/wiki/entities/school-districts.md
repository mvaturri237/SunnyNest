# School Districts

> GeoJSON-based school assignment lookup using shapely point-in-polygon to show assigned elementary, middle, and high schools per listing address.

**Status:** Active
**Owner files:** `src/school_districts.py`
**Config:** `data/school-boundaries/*.geojson`
**Added:** 2026-03-31
**Last updated:** 2026-06-03

## Overview

The school districts module provides per-listing school assignment by performing point-in-polygon lookups against GeoJSON attendance zone boundary data. Each listing card shows the assigned elementary, middle, and high school (e.g., "🏫 Cherry Chase Elem · Columbia Middle · Fremont HS").

The module uses a lazy singleton pattern (`_SchoolBoundaryStore`) that loads GeoJSON files once on first call, caches shapely geometries, and provides sub-millisecond lookups. It gracefully degrades when shapely is not installed or boundary files are missing.

## Architecture

- **`_SchoolBoundaryStore` lazy singleton:** Thread-safe with double-checked locking, loads GeoJSON on first call
- **Guarded shapely import:** `_HAS_SHAPELY` flag — module works without shapely, existing `get_school_district()` unaffected
- **Graceful degradation:** Missing files → log warning, return None for all levels
- **GeoJSON coordinate order:** `Point(lng, lat)` matches GeoJSON convention
- **Separate files per school level:** `elementary.geojson`, `middle.geojson`, `high.geojson`
- **Enrichment pipeline position:** Step 3b in [Orchestrator](orchestrator.md) (after geocoding, before sqm conversion)
- **UI display:** `abbreviate_school` Jinja2 filter in `web/dependencies.py` for compact display

## Current State

- **Working:** 35/38 listings populated with school assignments
- **Coverage:** 13 elementary + 5 middle + 5 high school zones for Sunnyvale
- **🔴 KNOWN-WRONG ASSIGNMENTS (visible bug, 2026-06-04):** The approximate-rectangle polygons produce visibly incorrect school assignments — user screenshot showed a Mountain View listing tagged `Cherry Chase Elementary School` and a Sunnyvale listing tagged `Stevens Creek Elem` (Cupertino school). **UI surfaces disabled 2026-06-04** via [`SCHOOLS_UI_ENABLED=False`](../../../../web/dependencies.py:107) — chip on cards and green map pill both hidden, but the DB enrichment pipeline still writes (so new data can be validated against current dataset). Compounded by the OPEN P2 about [`geocode_address()`](../../../../src/geocoder.py:139) silent city-centroid fallback. Refresh planned in [`plans/school-boundaries-nces.md`](../../../../plans/school-boundaries-nces.md).
- **⚠️ Approximate boundaries:** Current polygons are simplified rectangles — being replaced via [`plans/school-boundaries-nces.md`](../../../../plans/school-boundaries-nces.md) (hybrid CUSD ArcGIS + manual PDF trace, 8–18 h).
- **3 new DB columns:** `school_elementary`, `school_middle`, `school_high` (keeps existing `school_district`)
- **Backfill script:** `scripts/backfill_schools.py` for populating existing listings
- **Map visualization (2026-06-03, extended later same day to 15 schools + 6 favorites):** The school list rendered on the dashboard map grew from 13 → **15** (added Montclaire in Los Altos / Laurelwood in Santa Clara). **6 are user favorites** marked with green `#16a34a` + ⭐ tooltip prefix. See [Map View](map-view.md) "School POI overlay" + "Favorite-school price-pill highlight" — district *polygons* still remain hidden; only the school *points* are surfaced. Coordinates live in `SCHOOLS` const in `web/static/js/map.js` (geocoded + manual fallbacks). This is **independent** of the per-listing assignment lookup logic in this module.
- **⚠️ Name-form discrepancy (2026-06-03):** [`update_listing_schools()`](../../../../src/school_districts.py:153) writes `school_elementary` with the full GeoJSON `school_name` value (e.g., `"Cherry Chase Elementary School"` — with `" School"` suffix). The UI canonical form (matching `map.js` SCHOOLS) drops the suffix: `"Cherry Chase Elementary"`. Bridged at read-time in [`web/dependencies.py:_normalize_school_name()`](../../../../web/dependencies.py:103) — strips `" School"` only from `" Elementary School"` / `" Middle School"` / `" High School"` suffixes (never interior). Used by [`is_favorite_school()`](../../../../web/dependencies.py:116) for the Option-C highlight. SCHOOL-P3-13 tracks future migration to ingest-time normalization (cleaner long-term, requires backfill).

## Configuration

| File | Content |
|------|---------|
| `data/school-boundaries/elementary.geojson` | 13 elementary school zone polygons |
| `data/school-boundaries/middle.geojson` | 5 middle school zone polygons |
| `data/school-boundaries/high.geojson` | 5 high school zone polygons |
| `data/school-boundaries/README.md` | Documentation for boundary data |

## Key Files

| File | Purpose |
|------|---------|
| `src/school_districts.py` | `_SchoolBoundaryStore`, `get_assigned_schools()`, `get_school_district()` |
| `data/school-boundaries/*.geojson` | Attendance zone boundary polygons |
| `scripts/backfill_schools.py` | Backfill script for existing listings |
| `web/dependencies.py` | `abbreviate_school` Jinja2 filter |
| `web/templates/partials/listing-card.html` | School display on cards |

## History

- [2026-06-04] **UI surfaces disabled via `SCHOOLS_UI_ENABLED=False`** — user reported visibly wrong assignments. DB pipeline preserved (250 → 250 rows). Refresh planned in [`plans/school-boundaries-nces.md`](../../../../plans/school-boundaries-nces.md).
- [2026-06-03] **Name-form discrepancy bridged at read-time** — DB stores `" Elementary School"` suffix (from GeoJSON); UI canonical strips it. [`_normalize_school_name()`](../../../../web/dependencies.py:103) handles the conversion. Surfaced during favorite-school highlight (Option C) scoping — naive set-membership would have matched 0 of 247 listings. Now matches 36. SCHOOL-P3-13 tracks ingest-time migration.
- [2026-06-03] School map count 13 → 15 (Montclaire, Laurelwood); 6 marked as favorites with green render. Independent of this module's assignment lookup.
- [2026-06-03] 13 elementary schools added as static POI markers on dashboard map (independent visualization — does not change assignment logic in this module). See [Map View](map-view.md) for details.
- [2026-03-31] Initial implementation — APPROVED (0 P1, 0 P2 after 1 fix cycle)
- [2026-03-31] P2 fix: guarded shapely import (unguarded import caused ImportError)
- [2026-03-31] Architecture plan created (`plans/school-assignment.md`)

## Related

- [Orchestrator](orchestrator.md) — calls `get_assigned_schools()` in pipeline step 3b
- [Database Schema](database-schema.md) — 3 school columns on `listings` table
- [Listing Card](listing-card.md) — displays school assignments
- [Geocoder](geocoder.md) — provides lat/lng for point-in-polygon lookups
- [Plan: School Assignment](../../../../plans/school-assignment.md) — architecture plan
