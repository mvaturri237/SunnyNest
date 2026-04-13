# School Attendance Zone Boundaries — Sunnyvale, CA

## Overview

This directory contains GeoJSON files defining approximate school attendance zone
boundaries for the Sunnyvale, CA area. These are used by
[`src/school_districts.py`](../../src/school_districts.py) to perform
point-in-polygon lookups and determine which specific schools are assigned to
each listing address.

## Files

| File | Level | Schools | District(s) |
|------|-------|---------|-------------|
| `elementary.geojson` | Elementary (K–5) | 13 zones | SSD + CUSD |
| `middle.geojson` | Middle (6–8) | 5 zones | SSD + CUSD |
| `high.geojson` | High (9–12) | 5 zones | FUHSD |

## Districts Covered

| Abbreviation | Full Name | Levels | ZIP Codes |
|-------------|-----------|--------|-----------|
| **SSD** | Sunnyvale School District | Elementary + Middle | 94085, 94086, 94089 |
| **CUSD** | Cupertino Union School District | Elementary + Middle | 94087 |
| **FUHSD** | Fremont Union High School District | High School | All Sunnyvale |

## Data Source

These boundaries are **approximate polygons** created manually based on:

- District website boundary maps
- Known ZIP code / neighborhood associations
- The Sunnyvale city boundary (`data/sunnyvale-boundary.geojson`)

They are simplified rectangular approximations of the actual attendance zones.
For production accuracy, replace with official NCES SABS data or district-provided
shapefiles.

### Official Sources

- **NCES SABS**: https://nces.ed.gov/programs/edge/Geographic/SchoolLocations
- **SSD boundaries**: https://www.sesd.org/ → Schools → Attendance Boundaries
- **CUSD boundaries**: https://www.cusdk8.org/ → Schools → Boundary Maps
- **FUHSD boundaries**: https://www.fuhsd.org/ → Schools → Attendance Areas

## Vintage

- **Created**: 2026-03-31
- **Based on**: 2025–26 school year attendance zones (approximate)
- **Refresh cadence**: Check district websites annually (August) for boundary changes

## GeoJSON Format

Each feature requires:

```json
{
  "type": "Feature",
  "properties": {
    "school_name": "Cherry Chase Elementary School",
    "district": "Sunnyvale School District"
  },
  "geometry": {
    "type": "Polygon",
    "coordinates": [[[lng, lat], [lng, lat], ...]]
  }
}
```

**Important**: GeoJSON uses `(longitude, latitude)` coordinate order.

## Updating Boundaries

1. Visit the district website for updated boundary maps
2. Use https://geojson.io to trace new polygons
3. Update the relevant `.geojson` file
4. Run `scripts/backfill_schools.py` to update existing listings
5. Update the vintage date in this README
