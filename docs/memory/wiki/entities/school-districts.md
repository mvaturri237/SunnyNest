# School Districts

> GeoJSON-based school assignment lookup using shapely point-in-polygon to show assigned elementary, middle, and high schools per listing address.

**Status:** Active  
**Owner files:** `src/school_districts.py`  
**Config:** `data/school-boundaries/*.geojson`  
**Added:** 2026-03-31  
**Last updated:** 2026-03-31

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
- **⚠️ Approximate boundaries:** Current polygons are simplified rectangles — should be replaced with official NCES SABS data for production accuracy
- **3 new DB columns:** `school_elementary`, `school_middle`, `school_high` (keeps existing `school_district`)
- **Backfill script:** `scripts/backfill_schools.py` for populating existing listings

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

- [2026-03-31] Initial implementation — APPROVED (0 P1, 0 P2 after 1 fix cycle)
- [2026-03-31] P2 fix: guarded shapely import (unguarded import caused ImportError)
- [2026-03-31] Architecture plan created (`plans/school-assignment.md`)

## Related

- [Orchestrator](orchestrator.md) — calls `get_assigned_schools()` in pipeline step 3b
- [Database Schema](database-schema.md) — 3 school columns on `listings` table
- [Listing Card](listing-card.md) — displays school assignments
- [Geocoder](geocoder.md) — provides lat/lng for point-in-polygon lookups
- [Plan: School Assignment](../../../../plans/school-assignment.md) — architecture plan
