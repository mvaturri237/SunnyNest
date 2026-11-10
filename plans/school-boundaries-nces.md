# School Attendance-Boundary Refresh — Replace Approximate Rectangles with Official Data

> **Feature:** Replace the simplified-rectangle attendance polygons in [`data/school-boundaries/`](../data/school-boundaries/) with official attendance-zone data, validate, backfill, then re-enable the schools UI surfaces hidden by the 2026-06-04 [`SCHOOLS_UI_ENABLED`](../web/dependencies.py:107) flag.
>
> **Status:** PLANNED
> **Created:** 2026-06-04
> **Owner:** TBD (Code-mode implementer)
> **Estimated effort:** 8–18 hours (best/worst case — see §9)
> **Freshness tag:** 🟢 Fresh
>
> **Why now:** the immediate UI disable shipped on 2026-06-04 ([log entry](../docs/memory/wiki/log.md) — TBD by Orchestrator at sync time) hides visibly wrong school tags (e.g. Mountain View listings showing "Cherry Chase Elementary"). The DB enrichment pipeline still writes wrong data on purpose so the new boundaries can be validated against the existing dataset before cut-over. This plan is the path to re-enabling the chip + green map highlight with data parents can trust.

---

## Table of Contents

1. [Problem](#1-problem)
2. [Scope & non-goals](#2-scope--non-goals)
3. [Data source evaluation](#3-data-source-evaluation)
4. [Ingest pipeline design](#4-ingest-pipeline-design)
5. [Validation strategy (before cut-over)](#5-validation-strategy-before-cut-over)
6. [Migration / cut-over plan](#6-migration--cut-over-plan)
7. [Re-enable plan (Definition of Done)](#7-re-enable-plan-definition-of-done)
8. [Risks / open questions](#8-risks--open-questions)
9. [Effort estimate](#9-effort-estimate)
10. [Out of scope](#10-out-of-scope)
11. [Wiki Impact](#wiki-impact)

---

## 1. Problem

The school-to-listing assignment in [`src/school_districts.py`](../src/school_districts.py) is producing visibly wrong results. User screenshot evidence (2026-06-04):

- A **Mountain View** listing tagged `Cherry Chase Elementary School` (a *Sunnyvale* school).
- A **Sunnyvale** listing tagged `Stevens Creek Elem` (a *Cupertino* school).

### Two root-cause contributors

| # | Root cause | Where | Status |
|---|------------|-------|--------|
| 1 | **Approximate boundary polygons** — `data/school-boundaries/*.geojson` are simplified rectangles, not real attendance zones. Even with perfect input coords, the polygons themselves mis-classify ~30–40 % of points (based on the screenshot rate). | [`data/school-boundaries/elementary.geojson`](../data/school-boundaries/elementary.geojson) (and `middle.geojson`, `high.geojson`) — already flagged in [School Districts wiki entity](../docs/memory/wiki/entities/school-districts.md) "⚠️ Approximate boundaries" note | **THIS PLAN — fixes this.** |
| 2 | **Geocoder silent city-centroid fallback** — [`geocode_address()`](../src/geocoder.py:139) returns the Sunnyvale city centroid when Nominatim can't resolve a listing's street address. The centroid lands inside whatever polygon covers it, producing wrong-but-plausible school tags **even with perfect boundaries**. | [`src/geocoder.py:139`](../src/geocoder.py:139) → cascades through [`src/orchestrator.py:125`](../src/orchestrator.py:125). Documented as OPEN P2 in [Geocoder wiki entity](../docs/memory/wiki/entities/geocoder.md) "Known caveat" | **OUT OF SCOPE — separate task.** |

### Why this plan only addresses #1

The two are independent and ship-orderable separately. Boundary refresh is **necessary but not sufficient**: real polygons remove the systematic mis-tagging of points that ARE correctly geocoded, but listings with bad coords will still pin to the centroid and pick up whatever school covers that point. The ideal landing order is:

```
(a) Boundary refresh (this plan)
  → (b) Geocoder fallback fix (separate P2, see Geocoder entity)
    → (c) Re-enable UI
```

Re-enable can technically happen after (a) alone — see §7 step 3 for the recommendation that (b) be addressed first.

---

## 2. Scope & non-goals

**In scope (this plan):**

- Choose a replacement source for the 3 GeoJSON files
- Design the ingest pipeline (one-shot vs scripted)
- Validation strategy comparing OLD vs NEW assignments on the existing 250-listing dataset
- Backfill the existing DB rows with corrected assignments
- Definition of Done for re-enabling the UI flag

**Not in scope (explicitly listed in §10):**

- Geocoder silent-fallback fix
- Private / charter schools (SCHOOL-P3-4)
- Per-user favorite schools (SCHOOL-P3-9)
- Any UI changes beyond flipping [`SCHOOLS_UI_ENABLED`](../web/dependencies.py:107) — the chip CSS + JS already exist, dormant

**The 15 in-scope schools** (the set covered by the static `SCHOOLS` const in [`map.js`](../web/static/js/map.js:50)):

| District | Count | Schools |
|----------|-------|---------|
| Sunnyvale SD (SSD) | 8 | Bishop, Cherry Chase, Cumberland, Ellis, Fairwood Explorer, Lakewood, San Miguel, Vargas |
| Cupertino USD (CUSD) | 4 | Chester W. Nimitz, Louis E. Stocklmeir, West Valley, Montclaire |
| Santa Clara USD (SCUSD) | 3 | Braly, Ponderosa, Laurelwood |

Middle + high schools are also in scope (5 + 5 zones per the existing files), but the **elementary tier is where mis-tagging is most user-visible** because that's what the green favorite-school chip keys off.

---

## 3. Data source evaluation

### 3.1 Candidates compared

| Source | Coverage (Bay Area) | Freshness | Format | License | Maintenance burden | Notes |
|--------|---------------------|-----------|--------|---------|--------------------|-------|
| **A. NCES SABS 2021-22** (federal) | ⚠️ **Partial** — districts participate voluntarily. Bay Area is generally covered but CUSD / SCUSD boundary participation is unverified until download | 🔴 **Stale** — last public release is 2021-22 vintage (published 2024). NCES has confirmed no 2024-25 release is imminent. CUSD redrew elementary lines in mid-2024 → SABS data is **already wrong** for that district | Shapefile (in 2 GB ZIP) | Public domain (federal) | Low after one-shot extract; check annually for new vintage | The plan in [`plans/school-assignment.md`](school-assignment.md) §3.1 already speculated on this. Reality is worse than the original plan assumed. |
| **B. CA Dept of Education GIS portal** | ✅ **Full** — CDE publishes school **points** + **district** boundaries for the whole state. But **attendance zones below district level are NOT published** by CDE. | 🟢 Annual refresh | Shapefile / KML | Public domain (CA gov) | Low | Provides district polygons (useful nothing — already 1:1 with the 3 ZIPs we know). **Does NOT solve our problem** — we need *school-level* attendance zones, which CDE doesn't publish. |
| **C. District-direct downloads** | Mixed — **SSD** publishes a PDF map + InfoSnap school-finder web tool; **CUSD** has a public ArcGIS Online layer ("Cupertino Union Boundaries 2024-25") — **downloadable as GeoJSON**; **SCUSD** publishes only PDFs | 🟢 Current school year — each district refreshes when they redraw zones | CUSD: GeoJSON via ArcGIS REST. SSD + SCUSD: PDFs (manual tracing required) | Public information; check each district's footer (typically permissive for non-commercial use) | Medium — CUSD URL likely stable; SSD/SCUSD need re-tracing if they redraw | **Highest accuracy for what's downloadable. Mixed effort.** |
| **D. OpenStreetMap (OSM)** | ❌ **Sparse** — OSM has `amenity=school` (point data) extensively but `boundary=administrative` polygons with `admin_level=*` for school attendance zones are virtually absent in the South Bay. A handful of districts in the country have them; none of our 3 do. | N/A | GeoJSON via Overpass API | ODbL (share-alike) | N/A | **Verified by Overpass query during this evaluation:** zero attendance-zone relations for SSD/CUSD/SCUSD as of 2026-06. |
| **E. Commercial APIs** (GreatSchools, ATTOM, HomeFacts) | ✅ Full coverage typically | 🟢 Updated by vendor | JSON API | Paid — GreatSchools $99–199/mo for the boundary endpoint; ATTOM tier-pricing starts at $200/mo with annual commit | None (vendor handles updates) | **Cost-prohibitive for a personal-use app.** Also creates a runtime dependency where currently there is none. |
| **F. Hybrid manual tracing** (geojson.io from district PDFs / school-finder screenshots) | ✅ Whatever you trace | 🟡 Frozen at trace date | GeoJSON | Self-generated | High first time, low after (only re-trace when a district redraws) | ~30 min per polygon × ~25 polygons (15 elementary + 5 middle + 5 high) = **~12 h one-shot**. Tedious but deterministic. |

### 3.2 Coverage-gap audit per in-scope school

| School | District | Source A (SABS) | Source C (district-direct) | Recommended source for this school |
|--------|----------|-----------------|----------------------------|------------------------------------|
| Bishop, Cherry Chase, Cumberland, Ellis, Fairwood Explorer, Lakewood, San Miguel, Vargas | SSD | ⚠️ Likely in SABS but stale | PDF only — must trace | **C-PDF (trace)** — SSD redrew Cumberland zone in 2023 per district board minutes |
| Nimitz, Stocklmeir, West Valley, Montclaire | CUSD | ⚠️ In SABS but stale (CUSD redrew 2024) | ✅ **ArcGIS GeoJSON download** | **C-ArcGIS** — direct, current, GeoJSON-native |
| Braly, Ponderosa, Laurelwood | SCUSD | ⚠️ Likely in SABS but stale | PDF only — must trace | **C-PDF (trace)** |
| All 5 middle schools | SSD + CUSD | ⚠️ As above | Same mix | **C-ArcGIS for CUSD, C-PDF for SSD** |
| All 5 high schools | FUHSD | ⚠️ Likely in SABS, more stable (HS lines change rarely) | FUHSD publishes interactive map (not direct download) | **A-SABS with C-fallback** if SABS coverage is verified |

### 3.3 Recommendation

**Recommended: Source C (district-direct, hybrid) — with `Source A` (NCES SABS) used as a sanity-check baseline, NOT primary.**

Specifically:

1. **CUSD elementary + middle** → pull from the public CUSD ArcGIS REST endpoint as GeoJSON. **This is the only source that's both current AND machine-readable for the in-scope schools.** Likely URL pattern: `https://services.arcgis.com/<org-id>/arcgis/rest/services/Cupertino_Union_Boundaries_2024_25/FeatureServer/0/query?where=1%3D1&outFields=*&f=geojson`. Implementer must verify the exact URL during Phase 1 (the "Aging" risk — see §8 Q1).
2. **SSD + SCUSD elementary + middle + FUHSD high schools** → **manual trace** from each district's published PDF map into [geojson.io](https://geojson.io). ~30 min per polygon × ~17 polygons = ~8 h one-shot. Tedious but the only viable path because (a) PDFs are the canonical source and (b) NCES SABS is pre-2024-redraw and probably also missing some.

### 3.4 Why NOT each rejected option

| Rejected source | Reason |
|-----------------|--------|
| **A alone (NCES SABS)** | Stale by 2+ years; misses 2024 CUSD redraw — would ship known-wrong data. Acceptable only as a baseline cross-check. |
| **B (CDE)** | Wrong granularity — district polygons, not attendance zones. Doesn't address the problem. |
| **D (OSM)** | Empty for our districts. Verified. |
| **E (commercial)** | Cost. Also adds a runtime API dependency the architecture explicitly avoids per the [Adapter Pattern](../docs/memory/wiki/concepts/adapter-pattern.md) ethos. |
| **F (pure manual for everything)** | 12 h is fine, but if CUSD ArcGIS is downloadable we should use it — both cheaper to maintain AND more accurate. |

### 3.5 License / attribution

District-published boundaries are public information. The `data/school-boundaries/README.md` must:

- Cite each district's source URL + retrieval date.
- For traced PDFs, note "Hand-traced from PDF map dated YYYY-MM-DD."
- For CUSD ArcGIS, cite the FeatureServer URL.

No license incompatibilities for the personal-use app.

### 3.6 Refresh cadence

- **CUSD ArcGIS:** re-pull annually (August) via a refresh script — auto-detects schema drift, fails loud if endpoint moves.
- **SSD / SCUSD / FUHSD:** check district websites annually (August). Re-trace only if PDFs changed materially.
- **NCES SABS:** check annually for a new vintage. If a 2024-25 release lands and covers Bay Area, **consider** migrating to it as primary (revisit this plan).

---

## 4. Ingest pipeline design

### 4.1 Storage layout (unchanged from current)

```
data/school-boundaries/
├── elementary.geojson           # ← REPLACE (currently 13 rectangle zones)
├── middle.geojson               # ← REPLACE (currently 5 rectangle zones)
├── high.geojson                 # ← REPLACE (currently 5 rectangle zones)
├── README.md                    # ← UPDATE provenance section
└── sources/                     # ← NEW (raw downloads + traces, gitignored if large)
    ├── cusd-arcgis-snapshot-YYYY-MM-DD.geojson
    ├── ssd-traced-2026-06.geojson
    ├── scusd-traced-2026-06.geojson
    └── fuhsd-traced-2026-06.geojson
```

### 4.2 Schema compatibility (CRITICAL — keep the same properties)

The current [`_SchoolBoundaryStore._load_boundaries()`](../src/school_districts.py:133) reads two properties:

| Property | Type | Required | Source |
|----------|------|----------|--------|
| `school_name` | string | ✅ Yes — primary key | [`src/school_districts.py:153`](../src/school_districts.py:153) |
| `district` | string | Optional but populated by current data | [`src/school_districts.py:154`](../src/school_districts.py:154) |

**Recommendation: keep the same property names.** Avoid renaming so [`src/school_districts.py`](../src/school_districts.py) needs zero code changes. The new pipeline must output:

```json
{
  "type": "Feature",
  "properties": {
    "school_name": "Cherry Chase Elementary School",   // ← keep " School" suffix (matches current DB form)
    "district": "Sunnyvale School District",
    "source": "ssd-pdf-traced-2026-06-04",             // ← NEW optional provenance field
    "source_url": "https://www.sesd.org/...",          // ← NEW optional
    "traced_by": "manual" | "arcgis" | "sabs"          // ← NEW optional
  },
  "geometry": { "type": "Polygon" | "MultiPolygon", "coordinates": [...] }
}
```

The 3 new `source*` fields are **optional, ignored at read time, surfaced only for human audit**.

### 4.3 Pipeline shape: one-shot script + committed GeoJSON

**Decision: one-shot `scripts/refresh_school_boundaries.py` that the implementer runs manually, output committed to git.**

Rationale:

- **NOT scheduled.** Boundary changes are annual at most; a cron job is over-engineering and risks silent drift if the source endpoint moves.
- **NOT runtime-fetched.** Adds a network dependency to a hot path (every scraper run) for data that almost never changes.
- **Committed to git.** Files are small (~50 KB each after polygon simplification); diff review is the human cross-check on accuracy.

### 4.4 Script structure

```
scripts/refresh_school_boundaries.py
├── fetch_cusd_arcgis() → GeoJSON (HTTP GET, parse, filter to in-scope schools)
├── load_manual_traces() → reads sources/{ssd,scusd,fuhsd}-traced-*.geojson
├── normalize() → enforces schema in §4.2 (esp. " School" suffix on school_name)
├── validate() → calls helpers from §5
├── split_by_level() → writes elementary.geojson / middle.geojson / high.geojson
└── write_provenance() → updates README.md with retrieval date + counts
```

The script **fails loud** if:

- CUSD ArcGIS URL returns non-200 or schema-drifted JSON
- Any school in the in-scope list of 15 elementary names is missing from the merged output
- A polygon is self-intersecting (Shapely `polygon.is_valid == False`)
- Total area of all polygons in a level exceeds 2× Sunnyvale city area (overlap sanity check)

### 4.5 What does NOT change in [`src/school_districts.py`](../src/school_districts.py)

| Module piece | Reason it stays put |
|---|---|
| [`_SchoolBoundaryStore`](../src/school_districts.py:94) lazy singleton | Reads the same property names; no change |
| [`get_assigned_schools()`](../src/school_districts.py:197) | Same signature, same return shape |
| Shapely `Point(lng, lat).contains` logic | Polygon source-of-truth changed, algorithm unchanged |
| The DB columns `school_elementary` / `school_middle` / `school_high` | Same |
| The orchestrator step at [`src/orchestrator.py:125`](../src/orchestrator.py:125) | Same |

**Zero contract changes.** The whole refactor lives in `data/school-boundaries/*.geojson` + one new script.

---

## 5. Validation strategy (BEFORE cut-over)

This is the part that protects us from shipping a *different* kind of wrong.

### 5.1 Comparison script: `scripts/compare_school_assignments.py`

A read-only diff tool. Loads OLD boundary GeoJSON + NEW boundary GeoJSON, queries the DB for all listings with `latitude IS NOT NULL`, and prints:

```
=== School-assignment diff ===
Total listings examined: 247

UNCHANGED:               143  (57.9 %)
CHANGED (old → new):      82  (33.2 %)
  Cherry Chase Elem → Stocklmeir Elem:  18
  Cherry Chase Elem → Cumberland Elem:  11
  Stevens Creek    → Nimitz Elem:        7
  ...
GAINED (NULL → school):   12  (4.9 %)   ← listings the rectangles missed entirely
LOST   (school → NULL):   10  (4.0 %)   ← listings that fall outside the new polygons

ZIPs with no listings inside any new polygon: [list]

Suggested spot-check sample (10 changed listings, random):
  #123 Mountain View 94043 (37.4012, -122.0945): Cherry Chase → Stocklmeir
       Verify: https://www.cusdk8.org/Page/123 (CUSD school finder)
  #456 Sunnyvale 94087 (37.3411, -122.0518): Stevens Creek → Nimitz
       Verify: https://www.cusdk8.org/Page/123
  ...
```

### 5.2 Acceptance gates before cut-over

| Gate | Pass criterion | Tool |
|------|----------------|------|
| **G1. Polygon validity** | Every Shapely polygon `is_valid` AND non-empty | `scripts/refresh_school_boundaries.py` (built-in check) |
| **G2. Spatial coverage** | The union of elementary polygons covers ≥ 95 % of Sunnyvale city boundary (use [`data/sunnyvale-boundary.geojson`](../data/sunnyvale-boundary.geojson) as the reference). Allow ≤ 5 % gap for parks / industrial / airport. | `scripts/compare_school_assignments.py --coverage-report` |
| **G3. Overlap sanity** | ≤ 2 % of city area is covered by **multiple** elementary polygons | Same coverage report |
| **G4. Spot-check accuracy** | Implementer manually verifies 20 random listings against the relevant district's official school-finder web tool. **≥ 19 of 20 (95 %) must agree.** | Manual; outputs from §5.1 comparison script |
| **G5. No "everywhere" school** | No single school covers > 30 % of the city's residential area. Catches a bad polygon. | Coverage report |
| **G6. Round-trip** | After backfill, re-running the comparison script on DB should produce 0 CHANGED rows. | Comparison script |

**If any gate fails:** stop, fix source data, re-extract, re-validate. Do NOT proceed to backfill.

### 5.3 Spot-check oracles (where to verify the "right answer")

| District | Official school-finder | Notes |
|----------|------------------------|-------|
| SSD | `https://www.sesd.org/Page/<id>` (InfoSnap address lookup) | Authoritative; one address at a time |
| CUSD | `https://www.cusdk8.org/Page/<id>` (school locator) | Authoritative; one address at a time |
| SCUSD | `https://www.santaclarausd.org/Page/<id>` (boundary lookup) | Authoritative |
| FUHSD | `https://www.fuhsd.org/parents/school-locator` | Authoritative |

If a district's finder disagrees with our polygon for a tested listing, **the finder is canonical** — re-trace.

### 5.4 Edge cases to test explicitly

| Edge case | Expected behavior |
|-----------|-------------------|
| Listing exactly on a boundary vertex | `polygon.contains()` returns `False` for boundary points; listing gets `school_elementary = NULL`. Acceptable. |
| Listing outside all polygons (e.g. in Mountain View, San Jose) | All 3 school columns set to `NULL`. **Critically: do NOT fall back to nearest school.** Null is honest; nearest is misleading. |
| Listing with `latitude IS NULL` | Pipeline skips school lookup as today. No regression. |
| Same coordinate in 2 overlapping polygons (G3 should catch but might not in all cases) | First-match wins (current [`src/school_districts.py:232`](../src/school_districts.py:232) behavior). Log a warning. |

---

## 6. Migration / cut-over plan

### 6.1 Order of operations (UI flag stays OFF throughout)

```
1. Implement refresh_school_boundaries.py + run it → new GeoJSON files in working tree
2. Implement compare_school_assignments.py
3. Run compare against current DB → review diff, run §5 gates G1–G3, G5
4. Commit new GeoJSON + scripts in a single commit titled
   "boundaries: refresh from district-direct sources (UI flag still off)"
5. Run scripts/backfill_schools.py (already exists) with --force flag
   to overwrite existing school_* columns with new assignments
6. Run §5 gate G6 (round-trip) → expect 0 CHANGED rows
7. Run §5 gate G4 (manual spot-check of 20) → expect ≥ 95% agreement
   ↑ HUMAN STOP for review
8. Proceed to §7 (Re-enable plan) only if G4 passes
```

### 6.2 Backfill script changes

[`scripts/backfill_schools.py`](../scripts/backfill_schools.py) already exists for the original feature. It must be updated to support a `--force` flag that overwrites existing non-NULL `school_*` values. Current behavior only fills NULLs.

Add to the script:

```python
parser.add_argument(
    "--force",
    action="store_true",
    help="Overwrite existing non-NULL school_* columns (use after boundary refresh).",
)
```

When `--force` is set, the WHERE clause drops the `OR school_* IS NULL` filter and processes every listing with non-NULL `latitude` AND `longitude`.

### 6.3 Failure mode / rollback

If §5 gate G4 fails (< 95 % spot-check accuracy):

1. Do NOT commit the new GeoJSON to main (revert local changes).
2. Re-evaluate source for the failing schools — most likely the PDF trace is sloppy; re-do that polygon.
3. Re-run pipeline from step 1.

If G4 passes but **user reports a wrong tag post-backfill**:

1. The bad tag is almost certainly from root cause #2 (geocoder centroid). Confirm by checking the listing's `latitude`/`longitude` — if it matches Sunnyvale centroid (37.3688, -122.0363) to 4 decimals, root cause #2 fired.
2. If geocoder is innocent → re-trace the relevant polygon.

---

## 7. Re-enable plan (Definition of Done)

> **This is the Definition of Done for the whole project. Per Reviewer recommendation, the re-enable was NOT filed as a P3 — premature P3 sweeping could flip the flag before validation. Re-enable only happens as the FINAL acceptance gate.**

Ordered steps — must be executed top to bottom. Do not skip steps 1–3.

| # | Step | File / action |
|---|------|---------------|
| 1 | **Confirm §5 G4 passed** — 20-listing spot-check ≥ 95 % accurate vs district websites | Documented as part of the implementer's PR description |
| 2 | **Confirm no critical zero-coverage areas** — §5 G2 + G5 pass | Same |
| 3 | **(Strongly recommended) Confirm the geocoder silent-fallback P2 has been addressed** — see [Geocoder wiki entity](../docs/memory/wiki/entities/geocoder.md) "Known caveat". Without this, listings with unresolvable street addresses will still pin to Sunnyvale centroid and pick up whatever school covers (37.3688, -122.0363) — even with perfect boundaries. If the user explicitly decides to ship with #2 still open, document the residual mis-tag rate in the re-enable commit message. | Cross-task dependency |
| 4 | **Flip the feature flag** — [`web/dependencies.py:107`](../web/dependencies.py:107) `SCHOOLS_UI_ENABLED = False` → `True` | 1-line edit |
| 5 | **Bump CSS cache version** — `style.css ?v=16 → v=17` in [`web/templates/base.html:19`](../web/templates/base.html:19) so users see the resurrected `.school-pill-fav` chip + green pill | Per [CSS Cache Versioning](../docs/memory/wiki/concepts/css-cache-versioning.md) concept |
| 6 | **Remove the `/* DISABLED 2026-06-04 — UI hidden via SCHOOLS_UI_ENABLED flag … */` comment blocks** above `.school-pill-fav` and `.price-pill-marker.is-fav-school` in [`web/static/css/style.css`](../web/static/css/style.css) | Cosmetic only — the rules already work; this is markup hygiene |
| 7 | **Update wiki entity pages** — bump `Last updated:` and refresh `Current State` summaries in: [`listing-card.md`](../docs/memory/wiki/entities/listing-card.md), [`map-view.md`](../docs/memory/wiki/entities/map-view.md), [`school-districts.md`](../docs/memory/wiki/entities/school-districts.md) (replace the "⚠️ Approximate boundaries" warning with the new provenance). Also bump dates in the entity rows in [`docs/memory/wiki/index.md`](../docs/memory/wiki/index.md). | Markdown only |
| 8 | **Append "Re-enabled" log entry** to [`docs/memory/wiki/log.md`](../docs/memory/wiki/log.md) with: new source, validation results, file counts, screenshot diff | Markdown only |
| 9 | **Visual confirmation** — take a fresh screenshot of the dashboard. Diff against the user's original 2026-06-04 screenshot. Confirm: (a) Mountain View listings no longer say "Cherry Chase Elementary"; (b) green ★ chip + green map pill render correctly for favorite-school matches. | Manual; commit screenshot to `docs/memory/wiki/archive/school-boundaries-re-enable-YYYY-MM-DD.png` |

Re-enable is **complete** only when all 9 steps land in a single PR / commit chain and the user verbally accepts the screenshot diff.

---

## 8. Risks / open questions

| # | Risk / question | Likelihood | Impact | Mitigation |
|---|-----------------|------------|--------|------------|
| **Q1** | **CUSD ArcGIS URL is unverified at plan time.** The implementer needs to confirm the FeatureServer endpoint exists, is public, and contains 2024-25 boundaries. If it doesn't, CUSD collapses into the "trace PDF" bucket — adds ~3 h. | Medium | Medium | Phase 1 task: probe the URL before committing to the design. If missing, escalate. |
| **Q2** | **NCES SABS may cover NONE of the 3 districts.** If true, source A drops out entirely as a cross-check baseline — implementer leans 100 % on district-direct + manual. | Medium | Low | Plan already treats SABS as advisory, not load-bearing. |
| **Q3** | **Cupertino redrew elementary lines in 2024.** Public minutes confirm this. The new boundaries are what we want — make sure the CUSD ArcGIS pull is the **current** 2024-25 layer, not an archived 2023-24 one. | Medium | High | When fetching CUSD, log the layer's `lastEditDate` (ArcGIS metadata) and assert it's > 2024-01-01. |
| **Q4** | **The 4 schools with manual coordinate fallbacks in `map.js`** (Cumberland, Vargas, Braly, Ponderosa — all flagged `// manual` per [`map.js:54-67`](../web/static/js/map.js:54)) may need similar manual treatment for their attendance polygons. Their POI **points** were hard cases for Nominatim; their **polygons** might be poorly documented or recently redrawn too. | High | Medium | Treat all 4 as priority spot-check candidates in §5.3. |
| **Q5** | **Geocoder P2 not fixed before re-enable.** Per §7 step 3, ideally we ship (b) before (c). If the user chooses to ship the boundary refresh alone, residual mis-tag rate from centroid-pinned listings will be visible but at a much lower rate than today. Plan accommodates either order. | High (depends on user choice) | Low–Medium | §7 step 3 makes the trade-off explicit. |

---

## 9. Effort estimate

### Phases

| Phase | Activities | Best | Worst | Notes |
|-------|------------|------|-------|-------|
| **P1. Source eval + URL probe** | Verify CUSD ArcGIS endpoint, download SABS as cross-check baseline, confirm SSD/SCUSD/FUHSD PDFs available | 1 h | 2 h | If CUSD ArcGIS missing → P2 grows |
| **P2. Ingest pipeline** | Write `refresh_school_boundaries.py`, manually trace ~17 polygons from PDFs in geojson.io, fetch CUSD ArcGIS, normalize, write 3 GeoJSON files + provenance README | 4 h | 10 h | Tracing dominates — 30 min × 17 polygons = ~8.5 h worst case |
| **P3. Validation** | Write `compare_school_assignments.py`, run §5 gates G1–G3, G5, manual spot-check 20 listings (G4) | 1.5 h | 2.5 h | Spot-check itself is ~30 min; coding the comparison is ~1–2 h |
| **P4. Backfill** | Update `backfill_schools.py` for `--force`, run on production DB, run G6 round-trip | 0.5 h | 1 h | Already-built script needs ~10 LOC change |
| **P5. Re-enable** | §7 steps 4–9: flag flip, cache bump, CSS cleanup, wiki sync, screenshot | 1 h | 2.5 h | Wiki updates take most of this |
| **Total** | | **8 h** | **18 h** | |

### Reality check

This is **bigger than the original [`plans/school-assignment.md`](school-assignment.md)** (7–11 h) because (a) the manual tracing burden wasn't priced realistically in the original plan, and (b) validation + cut-over discipline is now non-negotiable given we've already shipped wrong data once.

**If the user wants to prioritize fast over correct:** drop manual tracing for SSD + SCUSD, use whatever SABS gives us for those 11 schools, fix CUSD only via ArcGIS → ~5 h. **Not recommended** — likely lands at ~70 % accuracy, repeats today's problem in a slightly different shape.

### Comparison to other queue items

| Plan | Effort | User-visible value |
|------|--------|---------------------|
| **This plan** | 8–18 h | Re-enables a feature the user explicitly wanted, hidden today |
| [`plans/cloud-scheduler.md`](cloud-scheduler.md) | ~2 h | Fixes laptop-asleep-on-weekends gap |
| Geocoder P2 (no plan yet) | ~3–5 h (estimated) | Fixes residual mis-tag risk for both boundary refresh AND map pins |

Recommended sequencing: **cloud-scheduler → geocoder P2 → this plan**. The first two are quick + unblock the third's residual-quality risk.

---

## 10. Out of scope

Explicitly **NOT** included in this plan:

| Excluded item | Tracker |
|---------------|---------|
| Geocoder silent city-centroid fallback fix | OPEN P2 in [Geocoder wiki entity](../docs/memory/wiki/entities/geocoder.md) "Known caveat" |
| Private / charter schools | SCHOOL-P3-4 in [`docs/memory/p3-backlog.md`](../docs/memory/p3-backlog.md) |
| Per-user favorite schools (config-driven) | SCHOOL-P3-9 |
| Ingest-time school-name normalization (drop `" School"` suffix) | SCHOOL-P3-13 |
| Adding `district` styling / colored chips | SCHOOL-P3-2 |
| Any UI / template / CSS changes beyond the flag flip in §7 | All dormant CSS + JS already exists; nothing to redesign |
| A cron / launchd schedule for boundary refresh | Annual manual run is sufficient (see §3.6) |
| Migration of the entire pipeline to a different geometry library (`geopandas`, `H3`, etc.) | Shapely point-in-polygon is fine for 25 polygons |

---

## Wiki Impact

- **New entities:** None.
- **Updated entities:** [`school-districts.md`](../docs/memory/wiki/entities/school-districts.md) (remove ⚠️ approximate-boundary warning, add provenance section, bump `Last updated`); [`geocoder.md`](../docs/memory/wiki/entities/geocoder.md) (cross-link to this plan in "Known caveat" section); [`map-view.md`](../docs/memory/wiki/entities/map-view.md) (refresh favorite-school highlight summary once re-enabled); [`listing-card.md`](../docs/memory/wiki/entities/listing-card.md) (refresh `.school-pill-fav` summary once re-enabled).
- **New concepts:** None. (The "manual-trace + ArcGIS + validation gates" approach is a one-off pattern; if it ever reaches a second domain, promote then.)
- **Plan table:** add a row for this plan in [`docs/memory/wiki/index.md`](../docs/memory/wiki/index.md) `## Plans` section, status `PLANNED (2026-06-04)`.

---

## Appendix A: file change summary

| File | Change | Notes |
|------|--------|-------|
| `data/school-boundaries/elementary.geojson` | **Replace** | New polygons from §3.3 |
| `data/school-boundaries/middle.geojson` | **Replace** | Same |
| `data/school-boundaries/high.geojson` | **Replace** | Same |
| `data/school-boundaries/README.md` | **Modify** | Update provenance section |
| `data/school-boundaries/sources/` | **Create** | Raw downloads + traced GeoJSON |
| `scripts/refresh_school_boundaries.py` | **Create** | One-shot ingest pipeline (§4.4) |
| `scripts/compare_school_assignments.py` | **Create** | OLD vs NEW diff tool (§5.1) |
| [`scripts/backfill_schools.py`](../scripts/backfill_schools.py) | **Modify** | Add `--force` flag (§6.2) |
| [`web/dependencies.py`](../web/dependencies.py) | **Modify** | Flag flip (§7 step 4) — **only after validation gates pass** |
| [`web/templates/base.html`](../web/templates/base.html) | **Modify** | CSS cache bump (§7 step 5) |
| [`web/static/css/style.css`](../web/static/css/style.css) | **Modify** | Remove DISABLED comment blocks (§7 step 6) |
| `docs/memory/wiki/entities/{school-districts,geocoder,map-view,listing-card}.md` | **Modify** | Wiki Impact section above |
| [`docs/memory/wiki/index.md`](../docs/memory/wiki/index.md) | **Modify** | Plans table + entity Last Updated dates |
| [`docs/memory/wiki/log.md`](../docs/memory/wiki/log.md) | **Modify** | "Re-enabled" log entry |

**Source-code changes in [`src/school_districts.py`](../src/school_districts.py): zero.** That's the whole point of §4.2 — schema compatibility lets the data swap be a pure data refresh.

---

*End of plan. Implementer: read §3 + §5 + §7 first — those are the load-bearing decisions.*
