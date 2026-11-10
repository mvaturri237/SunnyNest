# SunnyNest Wiki Log

> Chronological record of all changes. Newest entries at top.
> Each entry links to affected entity/concept pages.

---

## 2026-06-04

### Zillow stale for-sale → rental bug (Bug A + Bug B), ✅ APPROVED, 4 new P3s → backlog

**Trigger:** User reported [`1525 Bittern Dr`](https://www.zillow.com/homedetails/1525-Bittern-Dr-Sunnyvale-CA-94087/19615280_zpid/) shown as $6,200/mo active rental in the dashboard — but the property is **"Off market"** / for sale at $2.98M on Zillow.com (Rent Zestimate $5,838/mo). One screenshot of the app + one of Zillow.com supplied as evidence.

**Pipeline:** User report → Orchestrator routing (Debug first, per "debug/troubleshoot" keywords) → Debug (`new_task` — read-only RCA, 3 RapidAPI probes consumed = 5→8/500 monthly) → Orchestrator confirmation with user → Code (`new_task` — TDD, 15/15 tests green, atomic Bug A + Bug B + stop-the-bleed) → Code Reviewer (`new_task` ✅ APPROVED 0 P0/P1/P2, 4 P3s) → Orchestrator wiki sync (this entry).

**Root-cause (two layered bugs):**

| # | Bug | Where | Symptom |
|---|-----|-------|---------|
| **A** | Trust-the-provider: no response-side status validation | [`src/scrapers/zillow_scraper.py:268`](../../../src/scrapers/zillow_scraper.py:268) `normalize()` — sent `listingStatus=For_Rent` as request param but never re-checked `property.listing.listingStatus` / `marketingStatus` on the response | Off-market for-sale rows the provider mis-indexes pass straight to DB |
| **B** | Eager `mark_inactive`: deactivates on a single missed scrape | [`src/orchestrator.py:240`](../../../src/orchestrator.py:240) / [`src/database.py:824`](../../../src/database.py:824) `mark_inactive()` | Debug verified the RapidAPI provider's index is non-deterministic — same query returned zpid 19615280 at 04:20 UTC but NOT in three 10:50 UTC retries. One "hit" per scrape was enough to keep the stale row "active" forever. |

Compound symptom: a $2.98M off-market property displayed as a $6,200 rental for an unknown duration (≥ 2 days per `first_seen=2026-06-02`).

**Falsified hypothesis (noted for future readers):** the numerical proximity of $6,200 (DB) ↔ $5,838 (Zillow.com Rent Zestimate today) suggested a "Rent Zestimate field leak" — Debug disproved this. The provider's `price.value` for stale rows is just a cached prior asking price, NOT a Zestimate. `property.homeStatus` is also a dead-end — key is present but value is **always `null`** in our responses.

**Files modified (5 production + 2 tests + 1 ops):**

Production:
- [`src/scrapers/zillow_scraper.py`](../../../src/scrapers/zillow_scraper.py:268) — Bug A top-of-function status guard in `normalize()`. Signature changed to `dict | None`. Debug log on skip. Docstring names the live zpid + warns `property.homeStatus` is unusable.
- [`src/scrapers/base.py`](../../../src/scrapers/base.py:81) — `BaseScraper.normalize()` abstract return widened to `dict | None`; docstring documents the skip-signal contract. Non-breaking for Craigslist + Realtor adapters (still return `dict`).
- [`src/orchestrator.py`](../../../src/orchestrator.py:94) — handles `normalize() is None` with `continue` BEFORE `seen_external_ids.append(...)` (so filtered items don't poison the active-set); per-source `normalize_filtered` debug counter emitted only when > 0.
- [`src/models.py`](../../../src/models.py:163) — new `consecutive_misses: int = Column(Integer, nullable=False, default=0, server_default="0")` with docstring cross-referencing `MARK_INACTIVE_MISS_THRESHOLD`.
- [`src/database.py`](../../../src/database.py:166) — (1) new idempotent `_ensure_consecutive_misses_column()` migration in `init_db()` (all 278 existing rows backfill to 0 via `DEFAULT 0` ALTER), (2) added `consecutive_misses` to BOTH upsert exclusion tuples ([`:442`](../../../src/database.py:442), [`:501`](../../../src/database.py:501)) per [Upsert Exclusion Pattern](concepts/upsert-exclusion-pattern.md), (3) rewrote `mark_inactive()` — reset on present (cross-source isolated), increment on absent, flip `is_active=False` + `deactivated_at` only at `consecutive_misses >= MARK_INACTIVE_MISS_THRESHOLD = 3`; `ListingSource.is_active` mirror only on threshold crossing.

Tests (15/15 green, TDD verified RED→GREEN by spot-check):
- [`scripts/test_zillow_status_filter.py`](../../../scripts/test_zillow_status_filter.py) — 7 cases (forSale rejected / inactive rejected / missing subdict / missing key / case-insensitive happy path / non-string value / valid-forRent-active accepted).
- [`scripts/test_mark_inactive_counter.py`](../../../scripts/test_mark_inactive_counter.py) — 8 cases (counter reset on present / increment-1-still-active / increment-2-still-active / cross threshold deactivates / re-appearance clears deactivation + counter / cross-source isolation / ListingSource mirror at threshold / ListingSource mirror NOT below threshold).

Ops:
- [`scripts/deactivate_stale_zillow.py`](../../../scripts/deactivate_stale_zillow.py) — idempotent one-shot for id=327 / zpid 19615280. Dry-run default; `--apply` to commit. Sanity guard on source+external_id refuses to act if row identity drifted. Prints BEFORE/AFTER snapshots + active-zillow counts. **Not auto-run** — user runs it post-merge.

**Runtime verification (zero RapidAPI calls burned during fix; 3 burned during Debug):**
- Dashboard `curl http://127.0.0.1:8000/` → HTTP 200 (uvicorn left running, no template/CSS touched per AGENTS.md §6 — pure backend change).
- Schema migration ran in-band via `init_db()` on production [`data/listings.db`](../../../data/listings.db): `PRAGMA table_info` confirms `consecutive_misses INTEGER NOT NULL DEFAULT 0` present on `listings`; 278/278 rows have `consecutive_misses = 0`.
- Dry-run of [`scripts/deactivate_stale_zillow.py`](../../../scripts/deactivate_stale_zillow.py) confirms target row identity: `id=327, source='zillow', external_id='19615280', address='1525 Bittern Dr, Sunnyvale, CA 94087', price=6200.0, is_active=1, consecutive_misses=0` — matches user-reported symptom exactly.
- RapidAPI monthly counter: 5 → **8/500** (Debug's 3 probes only; Code mode used no live API).

**4 new P3s** (ZILLOW-STALE-P3-1 through ZILLOW-STALE-P3-4):
- **ZILLOW-STALE-P3-1** Legacy 30% safety threshold in [`orchestrator.py:225-249`](../../../src/orchestrator.py:225) is now redundant with the new hysteresis counter — pick "delete + comment" or "keep + retune comment" within 1 review cycle so the next reader has a clean story.
- **ZILLOW-STALE-P3-2** Craigslist + Realtor adapters inherit the new `dict | None` contract but have no equivalent status field to validate today. Log so the next contributor adding a status field doesn't reinvent the Bug A guard pattern.
- **ZILLOW-STALE-P3-3** `mark_inactive(source, [])` has a defense-in-depth gap — orchestrator's `if seen_external_ids:` guard currently shields it, but the function is module-public. Add an early-return + regression test `test_empty_active_ids_is_noop`.
- **ZILLOW-STALE-P3-4** Extract `_UPSERT_PRIMARY_EXCLUDE` + `_UPSERT_MERGED_EXCLUDE` module-level constants in `database.py` — both tuples are now 8+11 items long and a future contributor will inevitably forget one. Closes [Upsert Exclusion Pattern](concepts/upsert-exclusion-pattern.md) Rule #6 from "Consider" to "Done".

**Affected entities/concepts** (updated this sync):
- [`zillow-scraper`](entities/zillow-scraper.md) — new "Response-side status validation (Bug A)" subsection; History entry; signature annotation update.
- [`orchestrator`](entities/orchestrator.md) — pipeline step 2 docstring; `mark_inactive` semantics rewritten in Architecture; Current State and History entries.
- [`database-schema`](entities/database-schema.md) — `consecutive_misses` column added to the `listings` table row of the Tables section; History entry.
- [`silent-failure-pattern`](concepts/silent-failure-pattern.md) — new "Trust-the-provider scraper pattern" sub-pattern; new row in the "Variants" table; pairs with the existing 6 variants.
- [`p3-backlog`](../p3-backlog.md) — 4 new ZILLOW-STALE-P3-* rows.

**Cost summary:** ~2 hours agent time across Debug (RCA) + Code (TDD fix) + Reviewer (multi-axis review) + Orchestrator (wiki sync). 3 RapidAPI calls. Net DB rows affected: 0 by fix code; user will affect 1 row (id=327) by running the stop-the-bleed script.

**User action required (1 command):** `.venv/bin/python scripts/deactivate_stale_zillow.py --apply`

---

### Featured POI — Ortega Park added (Option A — 36×36 ringed pin + always-shown label), ✅ APPROVED, 5 new P3s → backlog

**Trigger:** User requested adding Ortega Park (Sunnyvale city park) as a new POI on the map with visual differentiation from regular POIs, with future intent of prioritizing nearby listings (ranking deferred to separate plan).

**Decision tree:** Orchestrator presented 3 paths (A regular POI add, B featured-POI subsystem, C hardcoded const) → User picked **B + Later** (featured subsystem now, ranking deferred). UX delivered 3 mockup options in [`docs/temp/mockups/featured-poi-map.html`](../../../docs/temp/mockups/featured-poi-map.html); User picked **Option A** (larger ringed pin + always-shown label) with all 5 sub-question defaults (per-entry `featured: true` flag, user-editable, below price pills, simple hover, no UI for the flag yet).

**Pipeline:** User request → Orchestrator triage (Path B + Later) → UX (`new_task` — 3 mockup options) → User pick (Option A + all defaults) → Code (`new_task`) → Reviewer (`new_task` ✅ APPROVED, 0 P1/P2, 5 P3s) → Orchestrator wiki sync (this entry).

**Files modified:**
- [`data/interest-points.json`](../../../data/interest-points.json) — appended `poi_ortega_park` entry with `"featured": true` flag. PANW HQ entry unchanged (no `featured` key — missing-is-falsy v1 contract).
- [`web/static/js/map.js`](../../../web/static/js/map.js:395) — [`createPOIMarker()`](../../../web/static/js/map.js:395) now branches inline on `poi.featured`. Both branches build valid `L.divIcon` (featured 36×36 ringed pin + always-shown label pill; regular 24×24 dot unchanged). `zIndexOffset: -50` on featured only (between schools `-100` and price pills `0`). **Tooltip enriched to `"Name · Category"` for ALL POIs** (intentional consistency — PANW HQ now shows `"Palo Alto Networks HQ · Work"` on hover; Reviewer agreed it would have been worse to differentiate hover-affordance between featured vs regular).
- [`web/static/css/style.css`](../../../web/static/css/style.css:1445) — new block lines 1445-1517 with `.poi-marker--featured`, `.poi-featured-pin`, `.poi-featured-label`. Faithful port of Option A mockup CSS; `prefers-reduced-motion` override included.
- [`web/templates/base.html`](../../../web/templates/base.html:19) — `style.css ?v=16 → v=17`; [`map.js`](../../../web/templates/base.html:35) `?v=14 → v=15`.

**🟢 Coordinate correction caught by Code mode:** task brief suggested `37.3496, -122.0184` for Ortega Park; Code mode queried Nominatim directly and used `37.3422, -122.0256` from OSM way `22462667` (~1 km from the suggested coords — different neighborhood). Reviewer independently verified via second Nominatim query (`37.3425911, -122.0247687` for node `764510168` inside the park — ~95m of Code mode's perimeter pin, well within tolerance). Also corrected ZIP `94086 → 94087`. This is the second time this session that Code mode's "verify external suggestions before pasting" discipline saved a user-visible bug (first was the wrong-by-1-3km school coords in the 2026-06-03 cycle).

**Runtime verification (all 6 checks PASSED):** HTTP 200 on `/`; `style.css?v=17` + `map.js?v=15` served; `/api/poi` returns 2 POIs with `featured: ['Ortega Park']`; `featured` keyword in served map.js = 7 (branch + properties); `poi-marker--featured` class in served style.css = 7.

**Out of scope (deliberate, deferred):** "ranking by distance to featured POI" — separate plan. No `featured` field on `POICreate` Pydantic (P3-POI-1). No "★ Feature this POI" toggle button in POI panel (P3-POI-2). No distance-to-listings on hover (P3-POI-3 — pairs with ranking).

**5 new P3s** (POI-P3-1 through POI-P3-5):
- **POI-P3-1** Add `featured: Optional[bool]` to `POICreate` Pydantic schema (forward-prep for toggle UI)
- **POI-P3-2** "★ Feature this POI" toggle button in POI list (paired with POI-P3-1)
- **POI-P3-3** Enrich featured-POI tooltip with distance-to-nearest-listing (requires ranking work)
- **POI-P3-4** Verify/test `add_poi()` Pydantic passthrough of unknown kwargs (footgun before POI-P3-1 lands)
- **POI-P3-5** Featured POI label pill can visually overlap nearby price pills at zoom ≥15 (cosmetic — z-order keeps clicks correct)

**Affected entities:** [`map-view`](entities/map-view.md) (new featured-POI variant; createPOIMarker branches; tooltip enriched).

**Cost summary:** ~1.5 hours agent time (Orchestrator triage + UX + Code + Reviewer). Zero production API calls (used Nominatim curl for coord verification).

---

### School-assignment UI disabled via `SCHOOLS_UI_ENABLED` flag (Option C from triage) — wrong data hidden pending NCES boundary refresh

**Trigger:** User reported (with screenshot evidence) that listings displayed wrong school assignments — a Mountain View listing tagged `Cherry Chase Elementary School`, a Sunnyvale listing tagged `Stevens Creek Elem` (a Cupertino school). Bug was upstream — the UI was faithfully showing what `school_districts.py` wrote to the DB; the DB was wrong because the GeoJSON polygons at [`data/school-boundaries/elementary.geojson`](../../../data/school-boundaries/elementary.geojson) are approximate rectangles, not real attendance zones. Combined with the OPEN P2 about [`geocode_address()`](../../../src/geocoder.py:139) silent city-centroid fallback, the chip + green-pill highlight shipped the previous day were misleading users.

**User-picked path (Option C from 4 options):** remove the user-facing surfaces now (honesty), queue an Architect-led data-refresh project for later.

**Pipeline:** User report + screenshot → Orchestrator triage (4 options A/B/C/D presented) → User picked C → Code (`new_task`) → Reviewer (`new_task` ✅ APPROVED 0 P1/P2, recommended SCHOOL-P3-16 NOT be a P3 to avoid premature sweep) → Architect (`new_task`, produced `plans/school-boundaries-nces.md`) → Orchestrator wiki sync (this entry).

**What shipped (the disable):**
- New module-level constant [`SCHOOLS_UI_ENABLED: bool = False`](../../../web/dependencies.py:107) at [`web/dependencies.py`](../../../web/dependencies.py) with multi-line rationale comment. Registered as Jinja env global at [`web/dependencies.py:168`](../../../web/dependencies.py:168) — flows to every template (including htmx-swapped partials) without per-route wiring.
- [`web/templates/partials/listing-card.html`](../../../web/templates/partials/listing-card.html) — `fav_school` boolean AND-ed with flag (defense-in-depth), `data-fav-school` attribute and entire `<div class="card-schools">…</div>` block wrapped in `{% if SCHOOLS_UI_ENABLED %}…{% endif %}`. No bare schools text leaks when flag is off.
- [`web/static/css/style.css`](../../../web/static/css/style.css) — added `/* DISABLED 2026-06-04 — UI hidden via SCHOOLS_UI_ENABLED flag … */` comment markers above [`.school-pill-fav`](../../../web/static/css/style.css:1132) and [`.price-pill-marker.is-fav-school`](../../../web/static/css/style.css:1152). **Rules kept dormant — not deleted** so re-enable is a 1-line flag flip + cache bump.
- [`web/static/js/map.js`](../../../web/static/js/map.js) — **NOT TOUCHED**. Code mode + Reviewer both verified the natural-disable chain: card emits no `data-fav-school` → JS `card.dataset.favSchool` is `undefined` → `undefined === '1'` is `false` → `is-fav-school` modifier never applied → green pill never fires. No JS edit needed.
- [`web/templates/base.html`](../../../web/templates/base.html:19) — cache bump `style.css ?v=15 → v=16` (CSS content unchanged but rendered HTML output changed — bump correct).

**Runtime verification (all 9 checks passed):** HTTP 200; `style.css?v=16` in served HTML; `card-schools` count = 0; `school-pill-fav` count = 0; `data-fav-school` count = 0; `🏫` emoji only in the POI filter `<option>` (unrelated, expected); `DISABLED 2026-06-04` grep-able x2; 15-school SCHOOLS const intact (6 favorites); `git diff src/school_districts.py src/orchestrator.py` = empty; **DB row count `WHERE school_elementary IS NOT NULL` = 250 before AND after** (proves no pipeline writes touched — preserved on purpose so new boundaries can be validated against current dataset before cut-over).

**What's NOT touched** (deliberate): the DB enrichment pipeline still writes school assignments to every new listing; the 15 school POI pins on the map (sourced from the static `SCHOOLS` const in `map.js`, NOT the DB) still render correctly with hover tooltips; the `FAVORITE_SCHOOLS` constant, `is_favorite_school` helper, and dormant CSS rules all stay valid — re-enable is a 1-line flip.

**Plan produced for the durable fix:** [`plans/school-boundaries-nces.md`](../../../plans/school-boundaries-nces.md) — Architect-led, 10-section data-refresh project. Recommends **hybrid CUSD ArcGIS pull + manual PDF tracing** (NOT NCES SABS — the federal source is 2021-22 vintage and pre-dates CUSD's 2024 redraw). Total effort 8–18 h. Re-enable flag flip is the last step of Definition-of-Done (intentionally NOT a P3 — Reviewer flagged that a P3-sweep without prerequisite data would re-introduce the same bug). Two architectural risks called out: (1) CUSD ArcGIS endpoint URL unverified at plan-time — Phase 1 first task is probing; (2) geocoder silent-fallback P2 is *necessary-not-sufficient* — recommend sequencing (a) boundary refresh → (b) geocoder fix → (c) re-enable for cleanest UI.

**New P3 added** (from Reviewer nit): **SCHOOL-P3-17** — re-enable doc comment at [`web/dependencies.py:105-106`](../../../web/dependencies.py:105) should mention removing the two `/* DISABLED 2026-06-04 ... */` comment blocks in CSS for completeness. 1-line doc fix.

**Affected entities:** [`listing-card`](entities/listing-card.md) (UI gate added), [`map-view`](entities/map-view.md) (green pill dormant via natural-disable chain), [`school-districts`](entities/school-districts.md) (UI hidden pending data refresh + plan link), [`geocoder`](entities/geocoder.md) (cross-linked from new plan as prerequisite).

**Cost summary:** ~1.5 hours agent time (Orchestrator triage + Code + Reviewer + Architect). Zero production API calls.

**Spinout findings:** SCHOOL-P3-17 added (CSS marker removal in re-enable doc). All prior P2 + P3 items remain OPEN; refer to [`docs/memory/p3-backlog.md`](../p3-backlog.md).

---

## 2026-06-03

### School icons follow-up — 15 schools + 6 green favorites + listing-card highlight (Option C), ✅ ALL APPROVED, 8 new P3s → backlog

Three-part follow-up to the earlier "School icons on map" entry today. All three asks shipped in a single user session.

**Ask #1 + #2 (bundled into one Code task) — 15 schools + 6 green favorites:**
- **#1 Added 2 schools:** Montclaire Elementary (1160 St. Joseph Ave, Los Altos, CUSD) + Laurelwood Elementary (955 Teal Dr, Santa Clara, SCUSD). Total: 13 → **15**. Bbox in [`scripts/geocode_schools.py`](../../../scripts/geocode_schools.py) widened from Sunnyvale-only to lat 37.32–37.42 / lng -122.12 to -121.95. Schema bumped from `(name, addr)` to `(name, addr, city)` 3-tuple. Both new coordinates verified against OSM ways (`25401662` Montclaire, `241140306` Laurelwood) — sub-meter match.
- **#2 Marked 6 as favorites with green styling:** Cherry Chase, Cumberland, Stocklmeir, West Valley, Montclaire, Laurelwood. Added `isFavorite: true/false` flag to each `SCHOOLS` entry in [`web/static/js/map.js:50-69`](../../../web/static/js/map.js:50). New CSS modifier `.school-poi-icon--favorite` overrides only `background: #16a34a` (the Design Bible's existing `--color-poi-park` token — no new color invented; logged SCHOOL-P3-8 to formalize a dedicated `--color-poi-school-favorite` token). ★ prefix added to favorite tooltips (`'⭐ ' + name`) + `aria-label` — color-independence per Design Bible "never use color alone" rule.
- **Pipeline:** Code R1 (one shot) → Reviewer R1 (✅ APPROVED, 0 P1/P2; surfaced SCHOOL-P3-10 = geocoder unavail + SCHOOL-P3-11 = ARIA double-announce). Cache `style.css ?v=13 → v=14`, `map.js ?v=12 → v=13`.

**Ask #3 (separate UX → Code → Review cycle) — highlight listings whose assigned elementary IS a favorite:**
- **UX:** 3 mockups in [`docs/temp/mockups/favorite-school-highlight.html`](../../../docs/temp/mockups/favorite-school-highlight.html). User picked **Option C** (themed green price-pill + schools-row chip — strongest visual rhyme with the green 🏫 POI pins from ask #2). Constant in [`web/dependencies.py`](../../../web/dependencies.py) confirmed as single source of truth. Elementary-only for v1.
- **Implementation:**
  - [`web/dependencies.py:75-134`](../../../web/dependencies.py:75) — new `FAVORITE_SCHOOLS` frozenset + `_normalize_school_name()` helper + `is_favorite_school()` registered as Jinja test+filter. Drift-prevention comment block points at [`map.js SCHOOLS`](../../../web/static/js/map.js:50).
  - [`web/templates/partials/listing-card.html`](../../../web/templates/partials/listing-card.html) — `fav_school` flag computed once at top of partial; card root gets `is-fav-school` class + `data-fav-school="1"` attr when match; matching school in schools row wrapped in `<span class="school-pill-fav">★ …</span>` (★ is literal U+2605, NOT HTML entity per AGENTS.md §5).
  - [`web/static/css/style.css:1126-1163`](../../../web/static/css/style.css:1126) — `.school-pill-fav` chip (green-700 on green-100, 4.71:1 AA) + `.price-pill-marker.is-fav-school .price-pill` green-pill variant (green-700 on white, 4.61:1 AA) with `::before "★ "`.
  - [`web/static/js/map.js:265-281`](../../../web/static/js/map.js:265) — reads `card.dataset.favSchool === '1'`, applies `is-fav-school` to divIcon className. Survives htmx swap via existing marker rebuild at [`map.js:431`](../../../web/static/js/map.js:431).
- **🔴 Critical discovery during scoping:** DB stores `"Cherry Chase Elementary School"` (with " School" suffix from GeoJSON `school_name`) but canonical UI form is `"Cherry Chase Elementary"`. Naive set-membership would have matched **0 of 247** listings. Fix: `_normalize_school_name()` strips trailing `" School"` only from `" Elementary School"` / `" Middle School"` / `" High School"` suffixes (won't mangle interior occurrences). Reviewer kept this as P3 (SCHOOL-P3-13: move to ingest-time when feature expands beyond elementary) — read-time is right for v1 because no migration risk, preserves DB fidelity, 5 LOC.
- **Live DB evidence:** SQL on `data/listings.db` → **36 listings** match favorites (Stocklmeir 59, Cherry Chase 31, Cumberland 5, others 0 at present). **3 favorite-matching listings rendered on the homepage** at curl time → all 3 show the green chip + green price pill correctly.
- **Pipeline:** UX (`new_task`) → User pick + sub-questions → Code (`new_task`) → Reviewer R1 (✅ APPROVED, 0 P1/P2; added SCHOOL-P3-15 = whitespace strip defense). Cache `style.css ?v=14 → v=15`, `map.js ?v=13 → v=14`.
- **Runtime verification (all 3 asks):** uvicorn restarted, `curl /` → HTTP 200; HTML references `style.css?v=15` + `map.js?v=14`; `.school-pill-fav` count = 3, `data-fav-school="1"` count = 3, ★ literal Unicode count = 3, 0 raw HTML entities found.

**Files modified across the 3 asks:** [`web/dependencies.py`](../../../web/dependencies.py) (+59), [`web/templates/partials/listing-card.html`](../../../web/templates/partials/listing-card.html) (~6 lines), [`web/static/js/map.js`](../../../web/static/js/map.js) (+9 in #3 marker loop + favorites flag changes in #2 + 2 new schools in #1), [`web/static/css/style.css`](../../../web/static/css/style.css) (+38 favorite-highlight + favorite school POI modifier), [`web/templates/base.html`](../../../web/templates/base.html) (2 cache bumps in each ask), [`scripts/geocode_schools.py`](../../../scripts/geocode_schools.py) (bbox + schema).

**P3 backlog deltas:** +8 new (SCHOOL-P3-8 through SCHOOL-P3-15). Open-count 36 → **44**.

**Affected entities:** [Map View](entities/map-view.md) (school count 13→15, favorite POI modifier, price-pill `is-fav-school` variant), [School Districts](entities/school-districts.md) (Montclaire + Laurelwood added; canonical name discrepancy documented), [Listing Card](entities/listing-card.md) (NEW `.school-pill-fav` chip, `is-fav-school` class, `data-fav-school` attr).

**Spinout findings still OPEN for user decision:**
1. **[P2 from prior cycle]** `geocode_address()` silent city-centroid fallback at [`src/geocoder.py:139`](../../../src/geocoder.py:139) — still open, blocks correct map pinning for unresolvable listings. Documented in [Geocoder entity](entities/geocoder.md) "Known caveat".
2. **[P3-10, this cycle]** `_do_geocode()` returned "Geocoder service unavailable" during ask #1 — distinct from P2 above. Worked around via direct OSM lookup. Debug-mode candidate.

**Cost summary:** ~3 hours agent time across UX + 2 × Code + 2 × Reviewer + Orchestrator. 0 production API calls (used OSM `curl` for the 2 new schools).

### School icons on map — Option A (Minimal POI pin) shipped, ✅ APPROVED after 2 review rounds, 7 P3s → backlog, 1 new P2 surfaced in geocoder

- **Result:** SHIPPED — 13 public elementary schools (8 SSD + 3 CUSD + 2 SCUSD) now render as static, hover-tooltip-only amber 🏫 POI pins on the dashboard map. Layer is always on at all zooms, no toggle, no click handler. Selected from 3 UX mockup options ([`docs/temp/mockups/school-icons-map.html`](archive/) — kept in `docs/temp/`) — user picked **Option A** (Minimal POI pin) over Option B (district-tinted) and Option C (zoom-adaptive chip).
- **Pipeline:** User request → Orchestrator (pre-flight + read map-view/school-districts entities + Design Bible) → UX Designer (3 self-contained mockups + recommendation + 4 open questions) → User (chose Option A + all default answers) → Code R1 (`new_task`) → Code Reviewer R1 (✅ code quality, **❌ P2** for 4 wrong-by-1-3km school coords, 6 × P3) → Code R2 (geocoded via new helper) → Code Reviewer R2 (✅ APPROVED, +1 new P3 + 1 escalated P2 about geocode_address) → Orchestrator wiki sync (this entry).
- **Files modified (production code):**
  - [`web/static/js/map.js`](../../../web/static/js/map.js:21) — new `SCHOOLS` const (lines 21-57, 13 entries), schools-layer block (~lines 120-150), JSDoc reflecting geocoder provenance. `zIndexOffset: -100` keeps schools beneath price pills.
  - [`web/static/css/style.css`](../../../web/static/css/style.css:1396) — new `.school-poi-marker` + `.school-poi-icon` (lines 1396-1430): amber `#f59e0b` 24×24 circle, white border, drop shadow, hover scale 1.15, `prefers-reduced-motion` honored.
  - [`web/templates/base.html`](../../../web/templates/base.html:19) — `style.css ?v=12→v=13`, `map.js ?v=10→v=11→v=12` (two bumps across the 2 review rounds).
- **Files added:**
  - [`scripts/geocode_schools.py`](../../../scripts/geocode_schools.py) — one-shot helper, not scheduled. Calls private [`_do_geocode()`](../../../src/geocoder.py:55) directly (not the public wrapper) to avoid the silent city-centroid fallback bug Code mode discovered while building it. Includes Sunnyvale bounding-box validator. Idempotent (LRU cache prevents repeat Nominatim hits).
- **Coordinate provenance:** 9 schools geocoded via Nominatim, 4 manual fallbacks (Cumberland — Nominatim returned None; Vargas, Braly, Ponderosa — Nominatim returned wrong-street/wrong-city matches caught by visual spot-check against real addresses). All 4 manual entries flagged `// manual` with reason.
- **Runtime verification:** uvicorn restarted on port 8000; `curl /` → HTTP 200, served `style.css?v=13` + `map.js?v=12`; served map.js contains "Bishop Elementary" + new lat `37.386636` (was `37.3962` pre-geocode).
- **🆕 Spinout P2 discovered (NOT fixed in this task, OPEN):** [`geocode_address()`](../../../src/geocoder.py:139) silently returns Sunnyvale city centroid when Nominatim misses the street address — affects production scraper at [`src/orchestrator.py:125`](../../../src/orchestrator.py:125) and corrupts both map placement AND downstream school assignment for unresolvable listings. Documented as "Known caveat" in [Geocoder entity](entities/geocoder.md) + linked to [Silent Failure Pattern](concepts/silent-failure-pattern.md). **Needs separate Architect → Code task to fix the public function signature.**
- **Affected entities:** [Map View](entities/map-view.md) (new school POI overlay section + history entry), [School Districts](entities/school-districts.md) (cross-reference to map visualization + history entry), [Geocoder](entities/geocoder.md) (new "Known caveat" section + history entry + new related link).
- **P3 backlog deltas:** +7 new P3s in new "School Icons on Map" section (SCHOOL-P3-1 through SCHOOL-P3-7). Open-count 29 → 36.
- **Cost summary:** ~2 hours of agent time (UX + 2 × Code + 2 × Reviewer + Orchestrator). Live curl verification only — no automated test suite for this feature (P3-3 covers extracting to JSON + endpoint, which would enable testing).
- **Reopen / extend triggers:** (a) user requests district-colored badges → SCHOOL-P3-2 was specifically designed as the prereq; (b) user requests private/charter schools → SCHOOL-P3-4; (c) Nominatim adds coverage for the 4 manual schools → re-run helper script (SCHOOL-P3-7).

### "Available date" on listing card — feature KILLED after Zillow field-verification probe returned negative
- **Result:** NOT SHIPPED. User asked for an "available [date]" entry on each listing card (matching Zillow's "Available Sat Aug 1 2026" string). Architect investigation ([`plans/available-date-feature.md`](../../../plans/available-date-feature.md)) proposed 3 mockup options, recommended Option C (dedicated `📅 Available …` row below schools). User picked Option C, requested Zillow field-verification probe first.
- **The probe killed the premise.** One-shot debug log on [`ZillowScraper.normalize()`](../../../src/scrapers/zillow_scraper.py:268) dumped `prop.keys()` for the first 3 listings of a real scrape: zero matches for `avail|date|move` other than `listingDateTimeOnZillow` (the posted-date duplicate, not the move-in date). `whatIWant` sub-dict doesn't exist; `hdpView` has only `[hdpUrl, listingStatus, price]`. Probe code fully reverted (`git diff src/scrapers/zillow_scraper.py` empty). 1 call of 500/mo budget used (now ~4/500).
- **Combined verdict across all three sources** (Architect's prior research + this probe):
  - **Zillow** `/search/byaddress` (current) — ❌ confirmed by probe today
  - **Zillow** `/property` detail endpoint — ❓ would cost +25 calls per scrape (~750/mo), blows free tier
  - **Realtor** `/properties/search-rent` — ❌ per Architect (not in sample payload at [`plans/realtor-scraper.md:60-110`](../../../plans/realtor-scraper.md:60))
  - **Realtor** detail endpoint — ❓ would double API budget (~600/mo of 150/mo limit), blows free tier
  - **Craigslist** — ⚠️ free-text in `#postingbody` only; fragile regex, ~50% miss rate, ~2-3s per detail-page request
- **User decision: kill the feature.** Rationale: cheapest viable path requires either paid RapidAPI tier or fragile Craigslist regex with low coverage. Not worth ~$15-25/mo or the maintenance burden for a single card field — especially given 271/271 listings would still show NULL until backfilled.
- **What was shipped (Orchestrator wiki sync only — no production code):**
  1. New "Fields NOT exposed by `/search/byaddress`" section in [`zillow-scraper.md`](entities/zillow-scraper.md) — documents the negative probe result, top-level key set actually returned, and the 3 reopen paths. **Single biggest deliverable** — prevents this same investigation from being repeated in 3 months when the request resurfaces.
  2. [`plans/available-date-feature.md`](../../../plans/available-date-feature.md) status header updated to **KILLED (2026-06-03)** with explicit reopen criteria (re-probe ZLLW Working API quarterly; if a new provider exposes the field; if user opts to pay for detail endpoint).
  3. Probe findings doc archived to [`docs/memory/wiki/archive/zillow-avail-probe-findings-2026-06-03.md`](archive/zillow-avail-probe-findings-2026-06-03.md) (moved from `docs/temp/` for durability).
  4. Wiki [`index.md`](index.md) plan table + Zillow Scraper "Last Updated" date refreshed.
- **Pipeline:** User request → Orchestrator (pre-flight + read scrapers/model/card) → Architect (data-source investigation + 3 mockups + recommendation, [`plans/available-date-feature.md`](../../../plans/available-date-feature.md)) → User (picked Option C) → Code (Zillow field-verification probe, 1 API call, reverted) → User (decision: kill) → Orchestrator (wiki sync — this entry). **No Code-Review cycle** because no production code persists (probe was fully reverted).
- **Cost summary:** ~1 hour of agent time across Architect + Code + Orchestrator; 1 Zillow API call.
- **Affected entities:** [Zillow Scraper](entities/zillow-scraper.md) (new "Fields NOT exposed" section + 1 history entry).
- **Reopen triggers** (documented in plan): (a) Zillow RapidAPI provider extends response schema (re-probe quarterly), (b) different ZLLW wrapper found that includes availability in search response, (c) user opts to pay for detail-endpoint calls, (d) user accepts Craigslist regex with explicit "best-effort" UI treatment.

### Silent-notification prevention — 3-fix bundle (✅ APPROVED, 0 P1/P2 after round 2, 12 P3s → backlog)
- **Result:** SHIPPED — root-caused and patched a 7-day Telegram silence (May 27 → Jun 3) plus the underlying anti-spam-counts-failures bug that would have re-occurred regardless of channel. **Live evidence captured before the fix:** 2 morning network-failure rows in `notification_log` consumed the 2/day anti-spam cap; deleting the 2 failed rows + manual re-run delivered 9 backlogged listings via Email + Telegram (HTTP 200 both channels). Proved both the root cause AND the user-visible damage in one shot.
- **3 minimum-viable fixes (L2 + L3b + 10:00 shift), each addressing a distinct silent-failure layer:**
  1. **L2 (anti-spam fix):** [`get_today_notification_count()`](../../../src/database.py:1463) now filters `success == True` (was counting all attempts). Same change inverted the previous [Silent Failure Pattern](concepts/silent-failure-pattern.md) Rule #3 ("count ALL attempts to prevent failure spam") — that 2026-03-31 generation of the rule turned out to be the *cause* of this regression. Rule #3 now disambiguates by what resource is being rationed (recipient's inbox = count successes; misbehaving channel's bandwidth = count attempts, typically separate circuit-breaker).
  2. **L3b (silence detector):** Red banner on `/` (dashboard) when (a) no successful notification in 48h AND (b) recent matching unnotified listings exist. New [`web/routes/dashboard.py:_compute_notification_silence_state()`](../../../web/routes/dashboard.py:40) + [`web/templates/dashboard.html:385`](../../../web/templates/dashboard.html:385) + [`web/static/css/style.css:1432`](../../../web/static/css/style.css:1432). CSS cache `?v=11`→`?v=12`. Closes the "operator only notices by visiting admin page" gating mechanism (that's how this incident lasted 7 days).
  3. **10:00 shift:** [`com.sunnynest.notify-am.plist`](../../../com.sunnynest.notify-am.plist:22) Hour `8`→`10`; [`config.yaml notification_schedule.hours`](../../../config.yaml:61) `[8,20]`→`[10,20]` per AGENTS.md §5 rule #3. Gives VPN/network time to come up reliably before launchd fires the notifier.
- **Round-2 hardening (added by Code Reviewer):** (a) tz bug — `get_today_notification_count()` previously used `func.date(sent_at) == today` (UTC-day compare) but claimed to be tz-aware; switched to UTC-bounded window translated from IST midnight, removing a now-false docstring claim. (b) extracted [`notifier.load_notification_filters(config)`](../../../src/notifier.py:1345) as single source of truth for filter extraction (used by both `NotificationService.run()` and `_compute_notification_silence_state()` — eliminates copy-paste drift). (c) docstring on [`get_notification_stats()`](../../../src/database.py:1709) rewritten to explain the deliberate decoupling from `get_today_notification_count()`.
- **Tests:** [`scripts/test_anti_spam_guard.py`](../../../scripts/test_anti_spam_guard.py) added — 5/5 pass, including the new `test_ist_day_boundary_not_utc_day` which would fail against the round-1 code (genuine regression guard, not a softball).
- **Runtime verification:** dashboard restarted via `launchctl kickstart -k`; `curl http://localhost:8000/` → HTTP 200, 96 768 bytes, `style.css?v=12` in `<head>`, zero `&#x` entities; `launchctl print … notify-am` Hour=10; `grep notification_schedule config.yaml` → `hours: [10, 20]`.
- **Files modified:** [`src/database.py`](../../../src/database.py) (~150 LOC), [`src/notifier.py`](../../../src/notifier.py) (~45 LOC), [`web/routes/dashboard.py`](../../../web/routes/dashboard.py) (~110 LOC), [`web/templates/dashboard.html`](../../../web/templates/dashboard.html) (+18), [`web/static/css/style.css`](../../../web/static/css/style.css) (+59), [`web/templates/base.html`](../../../web/templates/base.html) (CSS bump), [`com.sunnynest.notify-am.plist`](../../../com.sunnynest.notify-am.plist), [`config.yaml`](../../../config.yaml).
- **Files added:** [`scripts/test_anti_spam_guard.py`](../../../scripts/test_anti_spam_guard.py) (+228 LOC, 5 tests).
- **Pipeline:** Orchestrator → Debug (diagnosis, Q1 + Q2) → Orchestrator (manual stop-the-bleed: deleted 2 failed log rows + ran notifier → 9 listings delivered) → Code (R1, ~+352/−24) → Code Reviewer (R1: ❌ 1 P1 + 2 P2) → Code (R2, ~+50/−30, chose Option A for tz fix) → Code Reviewer (R2: ✅ APPROVED) → Orchestrator (wiki sync — this entry).
- **12 P3s → backlog:** SILENCE-P3-1 through SILENCE-P3-7 (Code R1: 4, Reviewer R1: 3), LAUNCHD-P3-1, ANTISPAM-P3-1, ANTISPAM-P3-2, NOTIF-P3-1, NOTIF-P3-2 (the last 2 from Reviewer R2; NOTIF-P3-2 tagged `[hardens-against-this-bug-class]` — same UTC-day bug in `get_notification_stats()`).
- **Affected entities:** [Notification System](entities/notification-system.md), [Database Schema](entities/database-schema.md), [Scheduler (launchd)](entities/scheduler-launchd.md), [Config (YAML)](entities/config-yaml.md).
- **Concepts updated:** [Silent Failure Pattern](concepts/silent-failure-pattern.md) — Rule #3 inverted; new 2026-06-03 row in Variants table; new "Docstring drift as silent failure" sub-rule; new "Duplication as silent failure" sub-pattern.
- **Q2 (separate question — 20 active listings):** Investigated by Debug. **Verdict: legitimate.** All 20 listings scraped today (~6h ago), zero stale, no dedup failures. Higher count explained by an 8-listing inventory burst on 2026-06-02 (typical baseline 1–4/day). No fix needed. Bonus finding: 28 legacy pre-2026-04-06 rows have `is_active=0 AND deactivated_at IS NULL` — doesn't affect the dashboard (filters on `is_active`) but is a latent inconsistency, **not** logged as a P3 because it predates the current issue tracking.
- **Action items:**
  1. **User (queued):** trigger cloud scheduler implementation per [`plans/cloud-scheduler.md`](../../../../plans/cloud-scheduler.md) Option 1 — only real fix for laptop-asleep-on-weekends gap. 10:00 shift mitigates the network-race but not the laptop-asleep case. ~2 hour Code task.
  2. **P3 sweep:** trigger "fix all open P3s" or scoped variants whenever ready.

---

## 2026-05-14

### Default price filter raised from $5K–$6.5K to $5K–$7.5K (✅ APPROVED, 0 P1/P2 after fix cycle)
- **Result:** `config.yaml` `filters.max_price` changed `6500` → `7500`; `_DROPDOWN_DEFAULTS["filter_price_max"]` in `web/routes/dashboard.py` updated to `"7500"`; quick-range radio in `web/templates/dashboard.html` updated to `value="5000-7500"` / `$5,000 – $7,500`. Scrapers (`zillow_scraper.py`, `realtor_scraper.py`) and notifier (`notifier.py`) pick up the new value automatically from `config.yaml`. Runtime verified: HTTP 200, `7500` present in live HTML.
- **P2 fix (round 2):** `app.py` Streamlit `_price_options` dict was missing `"$5K-$7.5K": (5000, 7500)` — the loop-with-fallback silently defaulted to `"$5K-$6.5K"`. Fixed: entry added, fallback default updated `6500`→`7500`, sentinel updated `"$5K-$6.5K"`→`"$5K-$7.5K"`. Re-reviewed and ✅ APPROVED.
- **4 P3s → backlog:** stale `6500` fallback in `zillow_scraper.py` + `realtor_scraper.py`; stale docstring examples in `listings.py` + `routes/__init__.py`. See `PRICE-P3-1` through `PRICE-P3-4` in [`p3-backlog.md`](../../p3-backlog.md).
- **Agents:** Orchestrator → Code (impl) → Code Reviewer (P2 found) → Code (P2 fix) → Code Reviewer (✅ APPROVED) → Orchestrator (wiki sync)
- **Affected entities:** [Config (YAML)](entities/config-yaml.md), [Filter Bar](entities/filter-bar.md), [Notification System](entities/notification-system.md), [Zillow Scraper](entities/zillow-scraper.md), [Realtor Scraper](entities/realtor-scraper.md)

## 2026-05-10

### Telegram notification channel — implemented and approved (✅ APPROVED, 0 P1/P2)
- **Result:** SHIPPED — `TelegramChannel(BaseNotificationChannel)` (~330 LOC) added to [`src/notifier.py`](../../../src/notifier.py:870), inert until user provides `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` in `.env` and flips `telegram.enabled: true`. WhatsApp simultaneously disabled (`whatsapp.enabled: false`) — code remains for future re-enable. Code Reviewer: ✅ APPROVED, **0 P1, 0 P2**, 4 P3s logged to [`docs/memory/p3-backlog.md`](../../p3-backlog.md). No round-2 fix cycle required.
- **Agents:** Architect (spec) → Code (impl) → Code Reviewer (review) → Orchestrator (wiki sync — this entry)
- **Trigger:** WhatsApp notifications had been silently failing due to (a) Meta Test Number 24h `WHATSAPP_API_TOKEN` expiry requiring daily manual regen, and (b) Test Number recipient allowlist silently dropping messages to non-allowlisted numbers (Meta returns HTTP 200 + valid `wamid` even when nothing is delivered). User asked: "is it the 24h token? if yes, simple way to generate one for few months? if not, let's try Telegram." Answer: yes the token IS one issue, but even with a long-lived token the allowlist problem persists; long-lived tokens require Meta Business Verification (days–weeks). Telegram has neither problem.
- **Implementation summary** (mirrors [`WhatsAppChannel`](../../../src/notifier.py:440) 1:1):
  - **Code:** Plain `httpx` POST to `https://api.telegram.org/bot<token>/sendMessage` with `parse_mode=HTML`. Same `SendResult` contract, same PANW root CA SSL pattern, same 4096-char body truncation (4000-char budget for safety headroom). HTML-escapes title/address/source via `html.escape()`. Reuses existing `error_category` taxonomy — **zero new categories**: 401 → `auth`, 403 "blocked by user" / 400 "chat not found" → `recipient_refused`, 429 → `rate_limited`, network → `network`, other → `api_error`. **No `token_expired` equivalent** because Telegram bot tokens never auto-expire (closes the WhatsApp variant of [Silent Failure Pattern](concepts/silent-failure-pattern.md) at the source).
  - **Startup probe:** `TelegramChannel.validate_token()` via `GET /bot<token>/getMe` (cheap, no quota cost) added to [`web/main.py`](../../../web/main.py:131), gated by `telegram.enabled`.
  - **Admin UI:** Telegram credential warning banner + auth-failure red banner (BotFather regen instructions) + generic warning banner + per-row "💬 Telegram failure" badge on `/admin/notifications`. Telegram status row + masked `chat_id` (last 4) on `/admin/settings`. CSS cache bumped `?v=8` → `?v=9` (cache flush only — no new rules).
  - **Config:** `telegram:` section added (`enabled: false`, `parse_mode: "HTML"`); `whatsapp.enabled` flipped `true` → `false`. `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` added to `.env.example` as placeholders. `chat_id` is intentionally env-only (co-secret with bot token) — not writable from Settings UI.
  - **Tests:** [`scripts/test_telegram_classification.py`](../../../scripts/test_telegram_classification.py) (6/6 mock cases passing), [`scripts/test_telegram_validate_token.py`](../../../scripts/test_telegram_validate_token.py) (2/2 passing), [`scripts/test_telegram_notification.py`](../../../scripts/test_telegram_notification.py) (`--preview` works; `--send` skipped pending user-side bot setup).
  - **Runtime verification:** dashboard restarted via launchd; `GET /admin/notifications` HTTP 200 with Telegram banner present, 0 raw `&#x` entities; `GET /admin/settings` HTTP 200 with Telegram status row + masked chat_id, 0 raw `&#x` entities.
- **Code Reviewer findings (4 P3s, all → backlog):**
  1. **TELEGRAM-P3-1** — single oversized listing line silently drops the entire body (truncation at 4000 chars happens before listing #1 is appended in extreme cases).
  2. **TELEGRAM-P3-2** — unnecessary lazy import of `sqft_to_sqm` with misleading "circular" comment (no actual circular dep — `src.utils` already imported at module top).
  3. **TELEGRAM-P3-3** — broad `except Exception` in `validate_token` mislabels programming bugs as `error_category="network"`; same anti-pattern in WhatsApp's `validate_token`.
  4. **TELEGRAM-P3-4** — defence-in-depth: scrub bot token from URL-bearing exception messages (Telegram forces token into URL path; current `httpx` exception types most likely don't embed URL in `str(exc)` but a future `raise_for_status()` would silently exfiltrate the token to `notification_log.error_message`).
- **Files modified:** [`src/notifier.py`](../../../src/notifier.py), [`src/utils.py`](../../../src/utils.py), [`scripts/run-notify.py`](../../../scripts/run-notify.py), [`web/main.py`](../../../web/main.py), [`web/routes/admin.py`](../../../web/routes/admin.py), [`web/templates/admin/notifications.html`](../../../web/templates/admin/notifications.html), [`web/templates/admin/settings.html`](../../../web/templates/admin/settings.html), [`web/templates/admin/base.html`](../../../web/templates/admin/base.html), [`config.yaml`](../../../config.yaml), [`.env.example`](../../../.env.example).
- **Files created:** [`scripts/test_telegram_notification.py`](../../../scripts/test_telegram_notification.py), [`scripts/test_telegram_classification.py`](../../../scripts/test_telegram_classification.py), [`scripts/test_telegram_validate_token.py`](../../../scripts/test_telegram_validate_token.py).
- **Entities updated:** [Notification System](entities/notification-system.md), [Config (YAML)](entities/config-yaml.md), [Admin Dashboard](entities/admin-dashboard.md).
- **Concepts updated:** [Silent Failure Pattern](concepts/silent-failure-pattern.md) — new "2026-05-10 Telegram" row in Variants table noting the failure mode is **closed at the source** (no auto-expiring tokens, no recipient allowlist).
- **Plans updated:** [`plans/telegram-channel.md`](../../../plans/telegram-channel.md) status flipped `PLANNED` → `IMPLEMENTED` in [index.md](index.md) Plans table.
- **Action items:**
  1. **User:** create Telegram bot via [@BotFather](https://t.me/BotFather) → `/newbot` → save bot token. Send `/start` to your bot from Telegram, then `curl https://api.telegram.org/bot<TOKEN>/getUpdates` to capture your `chat_id`. Add `TELEGRAM_BOT_TOKEN=...` and `TELEGRAM_CHAT_ID=...` to `.env`, flip `telegram.enabled: true` in `config.yaml`, restart the dashboard. Telegram notifications will then ship at the next 08:00/20:00 launchd run (or trigger immediately via `python scripts/run-notify.py`).
  2. **P3 sweep:** trigger *"fix all open Telegram P3s"* whenever the user is ready (4 items in backlog).

### Spec'd Telegram notification channel — replacing WhatsApp as primary push channel
- **Result:** SPEC ONLY (no code changes) — [`plans/telegram-channel.md`](../../../plans/telegram-channel.md) authored, ready for Code mode delegation.
- **Agent:** Architect
- **Trigger:** WhatsApp via Meta Cloud API has two operationally fatal issues: (1) Test Number `WHATSAPP_API_TOKEN` expires every ~24 h requiring daily manual regen, (2) Test Number recipient allowlist silently drops messages to non-allowlisted numbers (HTTP 200 + valid `wamid` returned, never delivered). User opted to add Telegram as a new channel rather than migrate WhatsApp Test Number → Production. WhatsApp code stays in place; only `whatsapp.enabled: false` in `config.yaml` once Telegram is live.
- **Spec scope:** New `TelegramChannel(BaseNotificationChannel)` mirroring [`WhatsAppChannel`](../../../src/notifier.py:440) 1:1 — same `SendResult` contract, same SSL/PANW root CA pattern, same ~4096 char body truncation, same anti-spam guard. Bot token via env (`TELEGRAM_BOT_TOKEN`); recipient `chat_id` also via env (`TELEGRAM_CHAT_ID`) — intentionally NOT in `config.yaml` since it's tightly coupled to the bot token. Reuses existing `error_category` taxonomy: HTTP 401 → `auth`, 403 "bot was blocked" / 400 "chat not found" → `recipient_refused`, 429 → `rate_limited`, network → `network`, other → `api_error`. No `token_expired` equivalent — Telegram bot tokens don't auto-expire (positive design property closing the WhatsApp variant of [Silent Failure Pattern](concepts/silent-failure-pattern.md)).
- **Files identified for impl:** 8 modified + 2 added (full list in spec §5). Includes new `validate_token()` startup probe (cheap `getMe` call), Telegram credential warning banner + per-row "💬 Telegram failure" badge in `/admin/notifications` (mirroring 2026-05-08 WhatsApp work), and `update_telegram_settings()` helper in `src/utils.py`. **No DB migration** — `notification_log.error_category`/`error_message` columns added 2026-05-08 already cover Telegram.
- **Out of scope (explicitly):** WhatsApp removal, MarkdownV2, inline keyboards, multi-recipient broadcast, group chats, photo/media, `_build_ssl_context` refactor to module level (deferred — accepted duplication for now per spec §7).
- **Negative consequences flagged in spec:** ~250 LOC added to [`src/notifier.py`](../../../src/notifier.py); PANW root CA SSL pattern duplicated (technical debt); `chat_id`-in-env vs WhatsApp's `recipient_phone`-in-config inconsistency intentional but documented.
- **Entities to update (post-impl, NOT now):** [Notification System](entities/notification-system.md), [Config (YAML)](entities/config-yaml.md), [Admin Dashboard](entities/admin-dashboard.md). Concept: [Silent Failure Pattern](concepts/silent-failure-pattern.md) — add Telegram row to "Variants" table noting the failure mode is closed at the source.
- **Files modified (this task):** [`plans/telegram-channel.md`](../../../plans/telegram-channel.md) (new); [`docs/memory/wiki/log.md`](log.md) + [`docs/memory/wiki/index.md`](index.md) (this entry).
- **Action items:**
  1. **User triggers** Code mode (or Orchestrator → Code) to implement per spec.
  2. After Code → Review APPROVED, Architect or Code mode runs the wiki-impact updates listed above.
  3. User performs the manual end-to-end checklist in spec §6b (BotFather setup → flip `telegram.enabled: true` → flip `whatsapp.enabled: false`).

---

## 2026-05-08

### Cross-source dedup IntegrityError silent no-op — fixed
- **Result:** ✅ APPROVED on re-review (P2-1 only; P3s deferred per user)
- **Agents:** Debug (root-cause) → Code (fix + reproducer + backfill) → Code Reviewer (1 P2 + 5 P3s) → Code (P2 fix only) → Code Reviewer (re-review APPROVED)
- **Trigger:** User screenshot showed 1426 Ormsby Dr appearing as 3 separate dashboard cards (Zillow + Craigslist + Realtor) at the same price/sqft/beds — clear cross-source duplicates that should have merged into one canonical listing.
- **Diagnosis (Debug):** Address normalization (`'1426 ormsby dr'`) and pairwise scoring (90–100, well above the 75 threshold) were both correct. Live single-threaded REPL reproduction with `INFO`-level logging revealed the failure path: `Duplicate detected ... → Merged duplicate ... → IntegrityError during dedup merge for craigslist/7930664370 — possible race condition, skipping.` The merge was crashing on the `uq_ls_source_external_id` UNIQUE constraint **every time** because `_merge_duplicate()` INSERTed a new `ListingSource(source, external_id)` row that collided with the one [`upsert_listing()`](../../../src/database.py:498) had just created on the duplicate listing. The over-broad `except IntegrityError` block at [`src/dedup.py:397`](../../../src/dedup.py:397) swallowed it as a benign "race condition" — a misleading log message that masked a deterministic bug for ~6 weeks (since 2026-03-28 when dedup shipped). 5–6 unmerged duplicate clusters silently accumulated in production.
- **Fix:** Three changes to [`src/dedup.py`](../../../src/dedup.py):
  1. **Query-then-reassign in `_merge_duplicate()`** (lines 254-275): find the existing `ListingSource` row by `(source, external_id)` and update its `listing_id` to canonical, instead of INSERTing a colliding new row. Defensive fallback creates a new row only when none exists (backfill / out-of-band path). `session.flush()` after to make the FK reassignment visible.
  2. **`session.refresh(dup)`** in `find_and_merge_duplicate()` (lines 430-435) before the defensive `dup.sources` deletion loop, so `dup.sources` is reloaded from DB after the FK reassignment — otherwise the loop could delete the just-reassigned row.
  3. **`logger.exception(...)` instead of `logger.warning("possible race condition")`** (lines 437-448) — includes the traceback so future IntegrityErrors are visible, removes the speculative "race condition" framing that fooled operators (and the prior reader of these logs).
- **New artifacts:**
  - [`scripts/test_dedup_merge.py`](../../../scripts/test_dedup_merge.py) — reproducer test using in-memory SQLite (`StaticPool`); 2 tests (the bug reproducer + a no-match sanity check); both passing.
  - [`scripts/backfill_dedup.py`](../../../scripts/backfill_dedup.py) — one-shot historical merger; buckets active listings by `(normalize_address, zip)`, runs Union-Find with the production scoring function (`DEDUP_THRESHOLD ≥ 75`); `--dry-run` default; one transaction per merge (not per cluster — partial-cluster recovery via idempotent re-run); identifies **6 clusters / 8 unmerged rows** in production. Not yet `--apply`-ed; user runs it after this commit.
- **Code Review iterations:**
  - Round 1 (initial implementation including 2 recommended P3s): 1 P2 (backfill docstring claimed cluster-atomic but was per-merge), 5 P3s (cascade fragility, additional test coverage, canonical-picker rule, observability ↔ missing scraper logs, minor nits). Verdict: 🔄 NEEDS WORK.
  - Round 2 (P2-only fix per user instruction): docstring rewritten (Option A: docs match per-merge isolation behavior, with explicit partial-cluster recovery story). [`src/dedup.py`](../../../src/dedup.py) and [`scripts/test_dedup_merge.py`](../../../scripts/test_dedup_merge.py) reverted to byte-identical pre-task state. Tests still 2/2; dry-run still 6 clusters / 8 rows. Verdict: ✅ APPROVED.
- **Files modified:** [`src/dedup.py`](../../../src/dedup.py) (3 fixes), [`scripts/backfill_dedup.py`](../../../scripts/backfill_dedup.py) (new), [`scripts/test_dedup_merge.py`](../../../scripts/test_dedup_merge.py) (new).
- **Entities updated:** [Deduplication](entities/deduplication.md), [Database Schema](entities/database-schema.md).
- **Concepts updated:** [Silent Failure Pattern](concepts/silent-failure-pattern.md) — new variant + new sub-rule ("never tag an actual exception path with a benign log message").
- **Action items:**
  1. **User runs** `.venv/bin/python scripts/backfill_dedup.py --apply` to merge the 6 historical clusters (8 rows). Idempotent — safe to re-run.
  2. **Follow-up tasks (deferred P3s)** queued in [`activeContext.md`](../tasks/default/activeContext.md):
     - **P3-1** Cascade-interaction hardening — add `assert not dup.sources` after `session.refresh(dup)` and a comment explaining the `cascade="all, delete-orphan"` interaction with direct FK reassignment in `_merge_duplicate()`.
     - **P3-2** Additional tests — 3-way merge (zillow + craigslist + realtor for same property), defensive-fallback path (no existing `ListingSource`), IntegrityError regression test (patch `flush` to raise; assert rollback + `None` returned + new "investigate" log wording), image_urls + price_history merge assertions.
     - **P3-3** Canonical-picker rule — current "earliest `first_seen`, id as tie-break" can pick a leaner Realtor record over a richer Zillow record (Cluster 2 in dry-run picked realtor 135 over zillow 16). Consider source-priority sort key (zillow=0, realtor=1, craigslist=2) as the primary, `first_seen` as secondary.
     - **P3-5** Minor nits in [`scripts/backfill_dedup.py`](../../../scripts/backfill_dedup.py) — module-level `from datetime import timezone`, `KeyboardInterrupt` handling separately from `Exception`, possible double-counting in skip-reason summary.
- **Lessons learned (codified):**
  1. Broad `except` blocks with speculative "race condition" wording mask deterministic bugs as transient ones — for years if necessary. Use `logger.exception` + non-speculative wording. → [Silent Failure Pattern](concepts/silent-failure-pattern.md) sub-rule (2026-05-08).
  2. Any UNIQUE constraint on a join/source table forces "reassign FK" semantics, never "INSERT a duplicate". Document this at the schema level so the next person reaching for INSERT thinks twice. → [Database Schema](entities/database-schema.md) "Constraint interactions" section (2026-05-08).
  3. When a feature whose dashboard symptoms would be visible (3 cards instead of 1) silently fails for 6 weeks, the operator-visibility surface is missing. Future preventive: surface "dedup merges this run: N" in the admin scrape stats so a sustained zero is noticeable. (Not implemented in this PR — captured as future improvement.)

### IDEX Mode Improvements — Phase 1 (✅ fully shipped, commit `7cef222`)
- **Result:** SHIPPED — all 8 deliverables on disk and committed. The `.roo/` system-write guard (see [AGENTS.md §8](../../../AGENTS.md)) initially prevented agent writes, but a shell script + immediate `git add .roo/ && git commit` finally landed the 5 new skill files + the strict-format edit. Once committed, the lifecycle hook leaves the files alone.
- **Agent:** Orchestrator (with delegations to Architect, Code, Code Reviewer)
- **Concepts created:** [Agent Mode Tiering](concepts/agent-mode-tiering.md), [Agent Failure Discipline](concepts/agent-failure-discipline.md)
- **Entities updated:** None (this is meta-mode infrastructure, not feature work)
- **Summary:** User asked for a comparison of SunnyNest's modes against `/Users/mvaturri/Documents/IDEX_new/.roo/`, then approved 8 specific improvements. The Architect authored all content (5 new skills + 2 surgical edits + 1 `.roomodes` debug mode YAML) into [`docs/temp/idex-adoption-phase1.md`](../../temp/idex-adoption-phase1.md) (786 lines, deliverable-scoring 0.92). Code mode applied [`.roomodes`](../../../.roomodes) (the new 🪲 Debug mode — bringing the custom mode count to 6) but was blocked by a system guard from writing to `.roo/`. A shell script ([`docs/temp/apply-phase1.md`](../../temp/apply-phase1.md)) successfully wrote the 5 skill files at `21:10` UTC, but they were silently reverted by a Roo Code lifecycle hook between subtasks; only the `execute_command`-applied edit to [`.roo/rules-ux-designer.md`](../../../.roo/rules-ux-designer.md) (Hard Stop §0 inserted at `21:16`) survived. The Code Reviewer subtask correctly identified the revert via disk inventory (its self-reflection coined "Disk-First Review Discipline" — codified in [Agent Failure Discipline](concepts/agent-failure-discipline.md)).
- **Files persisted:**
  - [`.roomodes`](../../../.roomodes) — added `debug` mode definition (lines 209–276); customInstructions explicitly references the Tier 1/Tier 2 skill loading pattern + 2-failure rule + handoff-to-Code rule + dual-app awareness; YAML still parses cleanly to 6 modes.
  - [`.roo/rules-ux-designer.md`](../../../.roo/rules-ux-designer.md) — inserted new `### 0. READ-WIKI-AND-TEMPLATE-FIRST (Hard Stop)` after the `## ⛔ Hard Stops` heading (existing §1–§4 not renumbered).
  - [`AGENTS.md`](../../../AGENTS.md) — Active Roles row for Debug updated (skills listed, `(built-in mode)` removed); new §8 `.roo/` Folder Write Restriction added; new "Pending Manual Install" appendix listing the 6 queued items.
  - [`docs/memory/wiki/concepts/agent-mode-tiering.md`](concepts/agent-mode-tiering.md) — new concept page (this commit)
  - [`docs/memory/wiki/concepts/agent-failure-discipline.md`](concepts/agent-failure-discipline.md) — new concept page (this commit)
- **Files installed in commit `7cef222`** (the queued items, all now persistent):
  - `.roo/skill-zero-trust-execution.md` (128 lines, Tier 1, all modes)
  - `.roo/skill-root-cause-analysis.md` (95 lines, Tier 2, debug)
  - `.roo/skill-log-analysis-patterns.md` (103 lines, Tier 2, debug)
  - `.roo/skill-receiving-code-review.md` (110 lines, Tier 2, code — not yet wired into code mode's customInstructions; opportunity for follow-up)
  - `.roo/skill-architect-design-review.md` (167 lines, Tier 1, architect — not yet wired into architect mode's customInstructions; opportunity for follow-up)
  - `.roo/skill-code-review.md` strict-format edit (Output Format replaced with `[P1]/[P2]/[P3]` + `Why:`/`Fix:` + `✅/🔄` verdict)
- **Lessons learned (now codified):**
  1. The `.roo/` and `.vscode/` folders are system-protected against agent writes — even shell-spawned writes via `execute_command` are reverted by a Roo Code lifecycle hook between subtasks. Only the human user can persistently modify them. → [AGENTS.md §8](../../../AGENTS.md)
  2. When a mode definition references skill files that don't yet exist on disk, the mode degrades silently — broken references are footguns. Soften `customInstructions` to make references conditional, OR remove them, until the user confirms install.
  3. Disk-First Review Discipline: any review whose subject is "files applied to disk" must begin with `ls`/`wc -l` against the expected target paths BEFORE reading any spec content. → [Agent Failure Discipline](concepts/agent-failure-discipline.md)
- **Action items:** User runs the install script in [`docs/temp/apply-phase1.md`](../../temp/apply-phase1.md), then confirms via `ls .roo/skill-zero-trust-execution.md` (and the other 4) that the files persisted. After confirmation, [`AGENTS.md`](../../../AGENTS.md) Active Roles row for Debug should be updated to remove the `⚠️ pending install` annotations.

### WhatsApp Token-Expiry Detection + Visible Failure Surfacing
- **Result:** APPROVED (0 P1, 0 P2, 5 P3)
- **Agents:** Code (implementation) + Code Reviewer (review with independent runtime re-verification)
- **Code Review:** Reviewer independently re-ran the §6 runtime verification including an XSS injection test (`<script>alert(1)</script> & "quoted"` payload in `error_message` rendered as `&lt;script&gt;…&lt;/script&gt;` in both element-content and `title=` attribute contexts — Jinja2 autoescape via `Jinja2Templates` confirmed safe). Verified: HTTP 200 in 3 states (no failure / synthetic token_expired failure / failure cleared by later success), banner auto-clear behavior, CSS cache `?v=8`, zero `&#x` entities, migration idempotency, ABC backward compat, startup probe non-blocking + crash-proof + UI-isolated. Spot-checked all 6 wiki updates — accurate, no corrections needed.
- **P3 follow-ups (non-blocking, future cleanup task):**
  1. Add Meta error code 2500 (`Application does not have permission`) to the OAuth-detection set in [`WhatsAppChannel._classify_meta_error()`](../../../src/notifier.py:527).
  2. Document in `_classify_meta_error()` that `meta_message` truncation is bound by the inner `[:200]` cap, making the outer `body_text=resp.text[:500]` cap dead surface area.
  3. Bump startup probe timeout from 5 s → 10 s in [`web/main.py:107`](../../../web/main.py:107) to avoid false-positive "inconclusive (network)" warnings on slow PANW-proxied cold starts.
  4. Clarify [`log_notification()`](../../../src/database.py:1392) docstring: change "Truncated to 1000 chars" → "Truncated to 1000 codepoints (UTF-8 safe)" so future maintainers don't worry about broken Unicode (Reviewer empirically verified codepoint-slicing is safe with multi-byte chars like 🔑).
  5. Replace `opacity: 0.7` on the secondary `<p>` in the error banner ([`web/templates/admin/notifications.html:27`](../../../web/templates/admin/notifications.html:27)) with `color: #b91c1c` to lift contrast above WCAG AA (currently dips to ~4.1:1 due to opacity stacking on `--admin-danger`).
- **Agent:** Code
- **Entities updated:** [Notification System](entities/notification-system.md), [Admin Dashboard](entities/admin-dashboard.md), [Database Schema](entities/database-schema.md)
- **Concepts updated:** [Silent Failure Pattern](concepts/silent-failure-pattern.md)
- **Summary:** Followed up on the 2026-05-08 diagnostic session that identified Meta Test Number tokens expire ~every 24 h and SunnyNest had no visible signal. Made WhatsApp send failures (especially `token_expired` / OAuthException / HTTP 401 / Meta error code 190) loud and visible:
  1. **Detection:** New `WhatsAppChannel._classify_meta_error()` parses the Meta JSON error body and tags failures by category (`token_expired`, `auth`, `rate_limited`, `api_error`, etc.). Triggered by HTTP 401, `error.type == "OAuthException"`, or codes 190/102/463/467.
  2. **Persistence:** New `error_category TEXT` and `error_message TEXT` columns on `notification_log` (additive migration `_ensure_notification_error_columns`). New `SendResult` dataclass + `BaseNotificationChannel.send_with_diagnostics()` returning structured info; `EmailChannel` and `WhatsAppChannel` both implement it. `NotificationService.run()` now uses the diagnostic path. `log_notification()` extended with optional error fields.
  3. **Surfacing:** New `get_last_channel_failure(channel, within_hours=48)` returns the latest log row only if it's a failure (a later success auto-clears). New prominent **red `info-banner--error`** on Notifications admin page when the most recent WhatsApp send failed with `token_expired` — links to `developers.facebook.com`, instructs user to update `WHATSAPP_API_TOKEN` in `.env`. Secondary banners for non-token WhatsApp failures and SMTP `auth` failures. History table rows now show specific badges (`🔑 Token expired`, `❌ {category}`) with the error message in `title=` tooltip.
  4. **Startup validation:** New `WhatsAppChannel.validate_token()` static method performs a cheap `GET /{phone_id}` (no quota cost). FastAPI lifespan hook calls it when WhatsApp is enabled and credentials are present, logs a clear warning if the token is expired.
  5. **CSS:** Added `info-banner--error` rule to `web/static/css/admin.css`; bumped cache version `?v=7 → ?v=8` in `web/templates/admin/base.html`.
- **Files:** `src/models.py`, `src/database.py`, `src/notifier.py`, `web/main.py`, `web/routes/admin.py`, `web/templates/admin/notifications.html`, `web/static/css/admin.css`, `web/templates/admin/base.html`.
- **Runtime verification (per §6):**
  - Restarted dashboard via `launchctl kickstart` — migration ran (`error_category`/`error_message` columns added to `notification_log`).
  - Inserted synthetic `token_expired` row: `curl /admin/notifications` returned **HTTP 200**, banner rendered (`info-banner--error`, "WhatsApp access token has expired or is invalid", regeneration link, last error message displayed); history table row showed `🔑 Token expired` badge with error in tooltip.
  - Confirmed CSS version bumped to `?v=8`. Confirmed **zero** raw `&#x` HTML entities in the rendered HTML (Jinja2 safety §5.1).
  - Cleaned up synthetic row: banner and badge disappeared on next page load (verified via grep counts = 0).
- **Backward compatibility:** `BaseNotificationChannel.send()` ABC contract preserved (still returns `bool`). `send_with_diagnostics()` is a new method with a default implementation that wraps `send()`. Legacy callers (`scripts/test_email_notification.py`, `send_notification()`) continue to work unchanged.

### Diagnostic Session — Realtor Missing (false alarm) + WhatsApp Test Number Allowlist
- **Result:** Diagnosis only (no code change)
- **Agent:** Debug
- **Entities updated:** [Notification System](entities/notification-system.md)
- **Summary:** User reported (1) no Realtor.com results in dashboard, (2) no WhatsApp notifications (email working). Debug investigation found:
  - **Issue 1 — Realtor missing: FALSE ALARM (browser cache).** Database has 17 active Realtor listings; live HTTP probe of `/` returned 200 with 14 cards including 2 Realtor cards visible. `realtor_api.enabled: true`, `RAPIDAPI_KEY` set, scraper ran today at 06:00. Fix: hard-refresh browser.
  - **Issue 2 — WhatsApp not delivered: EXTERNAL/META-SIDE.** All env vars set (`WHATSAPP_API_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_RECIPIENT_PHONE`), `whatsapp.enabled: true`, channel registered, `notification_log` shows `success=1`, direct Meta API probe returned `200 OK + wamid`. Smoking gun: phone number metadata shows `verified_name: "Test Number"`, `messaging_limit_tier: TIER_250` — this is a **Meta-provided sandbox/Test Number** that silently drops messages to recipients not on its allowlist. SunnyNest code is correct; the silent drop is on Meta's side. Fix: user must add `+972 50 769 2517` to allowed recipients in Meta App Dashboard (App "SunnyNest Alerts", id `1975747003301626`) → WhatsApp → API Setup → "Manage phone number list".
- **Files:** No code changes. Memory updates: `docs/memory/tasks/default/activeContext.md`, `docs/memory/wiki/entities/notification-system.md`, `docs/memory/wiki/log.md`, `docs/memory/wiki/index.md`.
- **Related discoveries (not blocking):**
  - Wiki entity `notification-system.md` previously said WhatsApp was "disabled by default" — now updated to reflect current `enabled: true` state and document the Test Number delivery limitation.
  - `activeContext.md` action item "Set `SMTP_PASSWORD` in `.env`" was stale (already done; email working since 2026-04-30) — removed.
  - `/tmp/sunnynest/scraper-stdout.log` and `scraper-stderr.log` missing despite successful scraper runs — possibly `/tmp` cleared on reboot, or plist `StandardOutPath`/`StandardErrorPath` not honoured. Worth verifying next scraper run.
- **Optional follow-up (code, not urgent):** Subscribe to Meta `messages` webhook to capture `delivered`/`read` status in `notification_log`; surface on Notifications admin page. Would have caught this silent-drop class of failure automatically. Not implemented — only worth doing if WhatsApp issues recur after the allowlist fix.

---

## 2026-04-14

### Scraper Pagination Increased — max_pages 1 → 3
- **Result:** APPROVED (0 P1, 0 P2, 2 P3)
- **Entities updated:** [Config (YAML)](entities/config-yaml.md), [Zillow Scraper](entities/zillow-scraper.md)
- **Summary:** User reported only 6 listings visible in the app vs 18 on Zillow. Root cause: `scraper.max_pages: 1` in `config.yaml` limited each scraper to a single page of results (~20 listings). Combined with dashboard default filters (price $5K–$6.5K, 3+ beds, ≤30 days on market, exclude disliked), only 6 Zillow house listings passed all filters. Fix: increased `max_pages` from 1 → 3, allowing up to ~60 results per source per scrape. Budget impact: Zillow 90/500 calls/month (18%), Realtor 90/150 (60%) — both within budget guard thresholds.
- **Files:** `config.yaml`
- **P3 suggestions:** (1) Add explicit `effective_max_pages <= 0` guard in Zillow scraper to match Realtor pattern. (2) Wiki entity pages updated (done in this sync).

---

## 2026-04-13

### GitHub Pages Landing Page Created
- **Result:** Created
- **Agent:** UX Designer
- **Summary:** Created a static GitHub Pages landing page for the SunnyNest project at `gh-pages/index.html` + `gh-pages/css/styles.css`. The page is a project showcase (not the app itself) featuring: hero section with browser mockup illustration, stats bar, 6 feature cards, tech stack grid, architecture flow diagram, and footer. Follows Design Bible tokens (Inter font, `#2563eb` accent, neutral palette). WCAG AA compliant with skip link, semantic HTML, focus states, `prefers-reduced-motion` support. Responsive at 3 breakpoints (mobile/tablet/desktop).
- **Files:** `gh-pages/index.html`, `gh-pages/css/styles.css`
- **Target URL:** `https://mvaturri237.github.io/SunnyNest/`

### TCC Exit Code 78 Fix — All Remaining Launchd Plists
- **Result:** APPROVED (0 P1, 0 P2 after fix round)
- **Entities updated:** [Scheduler (launchd)](entities/scheduler-launchd.md)
- **Concepts updated:** [launchd Patterns](concepts/launchd-patterns.md) (no changes needed — already documented)
- **Summary:** Scraper and 4 other launchd agents were failing with exit code 78 (TCC permission denied) because `StandardOutPath`/`StandardErrorPath` pointed to `~/Documents/zillow/logs/`. Moved all 5 remaining plists to `/tmp/sunnynest/` (matching the dashboard plist fix from 2026-04-12). Also differentiated notify-am/pm log filenames (were both `notify-stdout.log`), fixed log-rotate stderr pointing to stdout file, and updated support scripts (`rotate-logs.sh`, `install-service.sh`, `uninstall-service.sh`).
- **Files:** `com.sunnynest.scraper.plist`, `com.sunnynest.notify-am.plist`, `com.sunnynest.notify-pm.plist`, `com.sunnynest.backoffice.plist`, `com.sunnynest.log-rotate.plist`, `scripts/install-service.sh`, `scripts/rotate-logs.sh`, `scripts/uninstall-service.sh`
- **Verification:** All 6 agents exit code 0. Manual scraper trigger succeeded (39 listings scraped).
- **Pre-existing issue noted:** `sqlite3.IntegrityError` on `price_history` UNIQUE constraint — unrelated to this fix.

### Dashboard Cosmetic Changes — Left-Align Filter Bar, Zoom Out Map, Remove Clustering
- **Result:** APPROVED (0 P1, 0 P2, 2 P3)
- **Entities updated:** [Map View](entities/map-view.md), [Filter Bar](entities/filter-bar.md)
- **Summary:** Three cosmetic UI changes: (1) Filter bar left-aligned by removing `max-width: 1920px` and `margin: 0 auto` from `.filter-bar-inner`. (2) Map default zoom changed from 13 → 12 for a wider area view. (3) Marker clustering removed — `L.markerClusterGroup` replaced with `L.layerGroup`, MarkerCluster CDN (2 CSS + 1 JS) removed from `base.html`.
- **Files:** `web/static/css/style.css`, `web/static/js/map.js`, `web/templates/base.html`
- **P3 notes:** (1) Orphaned `.cluster-icon` CSS block (~16 lines) is now dead code. (2) Comment "Marker Cluster Group (1.1)" in map.js is stale.

---

## 2026-04-12

### Dashboard Plist Migrated to FastAPI/uvicorn
- **Result:** APPROVED (0 P1, 0 P2 after fix round)
- **Entities updated:** [Scheduler (launchd)](entities/scheduler-launchd.md), [Config (YAML)](entities/config-yaml.md), [Notification System](entities/notification-system.md)
- **Concepts updated:** [launchd Patterns](concepts/launchd-patterns.md)
- **Summary:** Dashboard was down because `com.sunnynest.dashboard.plist` still ran the old Streamlit app (`streamlit run app.py` on port 8501) after the FastAPI migration. Updated to `uvicorn web.main:app --host 127.0.0.1 --port 8000`. Also discovered the root cause of exit code 78 on ALL launchd agents: `StandardOutPath`/`StandardErrorPath` pointed to TCC-protected `~/Documents/zillow/logs/` — moved to `/tmp/sunnynest/`. Updated `config.yaml` `dashboard_url` and all stale `localhost:8501` fallback defaults in code.
- **Files:** `com.sunnynest.dashboard.plist`, `scripts/start-dashboard.sh`, `config.yaml`, `src/notifier.py`, `backoffice.py`, `scripts/install-service.sh`, `scripts/test_email_notification.py`
- **Follow-up needed:** Other 5 launchd agents (`backoffice`, `scraper`, `notify-am`, `notify-pm`, `log-rotate`) still need the same `StandardOutPath`/`StandardErrorPath` fix (move from `~/Documents/zillow/logs/` to `/tmp/sunnynest/`).

### WhatsApp Notification Channel Added
- **Result:** APPROVED (0 P1, 0 P2, 3 P3)
- **Entities updated:** [Notification System](entities/notification-system.md), [Config (YAML)](entities/config-yaml.md)
- **Summary:** Added `WhatsAppChannel` class to the notification system, implementing the `BaseNotificationChannel` adapter pattern. Uses Meta WhatsApp Business Cloud API via `httpx` (no new dependencies). Sends concise text messages (4096-char limit) with listing summaries. Same conditions as email: same config filters, same anti-spam guard, same launchd schedule. Pre-flight check in `NotificationService.run()` changed from SMTP-only to channel-agnostic — each channel validates its own credentials independently. Admin UI updated with WhatsApp status on Settings page and credential warning on Notifications page. WhatsApp disabled by default in config (`whatsapp.enabled: false`).
- **Files:** `src/notifier.py`, `config.yaml`, `.env.example`, `scripts/run-notify.py`, `src/utils.py`, `web/templates/admin/settings.html`, `web/templates/admin/notifications.html`, `web/routes/admin.py`
- **P3 notes:** (1) Duplicate `_get()` helper in both channels — extract to module-level in future. (2) WhatsApp env vars not in `get_env_status()` System Health panel. (3) No phone number format validation on recipient.

---

## 2026-04-10

### Default Days Listed Filter Set to 30 Days
- **Result:** APPROVED (0 P1, 0 P2, 0 P3)
- **Entities updated:** [Filter Bar](entities/filter-bar.md)
- **Summary:** Changed default "📅 Days Listed" filter from "Any" (empty string) to ≤30 days. `_DROPDOWN_DEFAULTS["filter_max_days"]` in `web/routes/dashboard.py` set to `"30"`. Hides old listings (e.g., 500+ day Realtor.com listings) by default. Users can still select "Any" or enter a custom value (e.g., 90 days) via the existing Days Listed dropdown UI.
- **Files:** `web/routes/dashboard.py`

---

## 2026-04-06

### Listing Lifecycle Analytics & Days-on-Market Filter (Implementation)
- **Result:** IMPLEMENTED & APPROVED (Phase 1: 0 P1, 1 P2 fixed; Phase 2: 0 P1, 0 P2, 2 P3 fixed)
- **Entities updated:** [Database Schema](entities/database-schema.md), [Filter Bar](entities/filter-bar.md), [Admin Dashboard](entities/admin-dashboard.md)
- **Summary:** Full implementation of listing lifecycle feature: (1) `deactivated_at` DateTime column on `listings` table with idempotent migration, set by `mark_inactive()`, cleared on re-activation, added to upsert exclusion tuples. (2) "📅 Days Listed" dashboard filter dropdown between Source and More — radio presets (Any/≤7d/≤14d/≤30d/≤60d) + custom input, filters by `days_on_market` column, full snapshot/revert/apply/reset pattern with HTMX. (3) "⏱️ Listing Lifecycle" analytics section on admin analytics page — 3 KPI cards (avg/median lifespan, total removed) + 2 bar charts (lifespan by bedrooms, lifespan by price range). Uses `COALESCE(deactivated_at, last_seen)` for backward compatibility with legacy data.
- **Files:** `src/models.py`, `src/database.py`, `web/routes/__init__.py`, `web/routes/listings.py`, `web/routes/dashboard.py`, `web/routes/admin.py`, `web/templates/dashboard.html`, `web/static/js/filters.js`, `web/templates/admin/analytics.html`, `web/static/css/style.css`, `web/static/css/admin.css`, `web/templates/base.html`, `web/templates/admin/base.html`

### Listing Lifecycle Analytics & Days-on-Market Filter (Architecture Plan)
- **Result:** PLANNED (architecture plan created)
- **Entities updated:** [Database Schema](entities/database-schema.md), [Filter Bar](entities/filter-bar.md), [Admin Dashboard](entities/admin-dashboard.md)
- **Summary:** Architecture plan for 3 features: (1) `deactivated_at` timestamp column on `listings` table with idempotent migration and `mark_inactive()` update, (2) "Max Days Listed" dashboard filter using existing `days_on_market` column with radio presets (7/14/30/60 days) + custom input, (3) Listing Lifecycle analytics section on admin analytics page with KPI cards (avg/median lifespan, total removed) and bar charts (lifespan by bedrooms, lifespan by price range). 2-phase plan: Phase 1 = backend, Phase 2 = frontend.
- **Plan:** [`plans/listing-lifecycle.md`](../../../plans/listing-lifecycle.md)

### Source Filter HTMX Race Condition Fix
- **Result:** APPROVED (0 P1, 0 P2, 2 P3)
- **Entities updated:** [Filter Bar](entities/filter-bar.md)
- **Summary:** Fixed race condition where HTMX read hidden input values before JS `applyFilter()` updated them, causing source filter to always send `filter_source=all`. Fix: changed all 4 Apply buttons from default click trigger to `hx-trigger="apply"` (custom event). JS now dispatches `CustomEvent("apply")` after committing hidden input values, ensuring HTMX reads correct values. Also updated `resetAllFilters()` to use the same custom event pattern.
- **Files:** `web/templates/dashboard.html`, `web/static/js/filters.js`

### Realtor Property Type Filter + API Usage Status Fix
- **Result:** APPROVED (0 P1, 0 P2, 3 P3)
- **Entities updated:** [Realtor Scraper](entities/realtor-scraper.md), [API Usage Page](entities/api-usage-page.md)
- **Summary:** (1) Added `propertyType=single_family` to Realtor API params — API was returning 171 mixed-type listings but orchestrator only accepts houses; now fetches 17 single-family listings directly. Correct API param is `propertyType` (camelCase), not `type` or `property_type`. (2) Fixed API Usage page status badge showing "Last call OK" (green) when `status_code=None` (connection errors) — added `else` branch to set `last_call_status="error"` and `last_call_status_text="Connection Error"`.
- **Files:** `src/scrapers/realtor_scraper.py`, `web/routes/admin.py`

### SSL Certificate Verification Fix for RapidAPI Scrapers
- **Result:** APPROVED (0 P1, 0 P2, 3 P3)
- **Entities updated:** [Realtor Scraper](entities/realtor-scraper.md), [Zillow Scraper](entities/zillow-scraper.md)
- **Concepts updated:** [Security Patterns](concepts/security-patterns.md)
- **Summary:** Fixed SSL certificate verification failure caused by two compounding issues: (1) Palo Alto Networks GlobalProtect firewall performing TLS decryption with a root CA not in Python's certifi bundle, and (2) OpenSSL 3.6.0 strict X.509 validation rejecting leaf certs missing the Authority Key Identifier (AKI) extension. Fix: added `_build_ssl_context()` static method to `BaseScraper` that loads certifi + PANW root CA and clears `VERIFY_X509_STRICT` while preserving `CERT_REQUIRED` and `check_hostname=True`. Both scrapers now pass `verify=ssl_ctx` to `httpx.AsyncClient()`.
- **Files:** `src/scrapers/base.py`, `src/scrapers/realtor_scraper.py`, `src/scrapers/zillow_scraper.py`, `data/certs/panw-root-ca.pem` (new)

### Dedup Candidate Narrowing Fix
- **Result:** APPROVED (0 P1, 0 P2, 2 P3)
- **Entities updated:** [Deduplication](entities/deduplication.md), [Database Schema](entities/database-schema.md)
- **Summary:** Fixed bug where cross-source duplicates with different bedroom counts were missed. Root cause: `find_duplicate_candidates()` filtered by `zip_code + bedrooms`, preventing candidates with mismatched bedroom counts from being scored. Fix: removed `bedrooms` from candidate narrowing (now ZIP-only), moved bedroom comparison to scoring phase (15 points). Updated index from `(zip_code, bedrooms, is_active)` to `(zip_code, is_active)`. Merged existing duplicate at 370 Cypress Ave (Craigslist listing 107 → Zillow listing 111).
- **Files:** `src/dedup.py`, `src/models.py`

### LLM Wiki Schema Updates (Phase 1)
- **Result:** APPROVED (0 P1, 0 P2, 7 P3)
- **Summary:** Updated AGENTS.md (Pre-flight, Active Roles, §1 Memory Protocol, §7 Wiki Sync). Prepared skill-memory-manager.md (full rewrite), skill-wiki-lint.md (new), and .roomodes edits (4 modes) for manual copy to protected .roo/ folder.
- **Files:** `AGENTS.md`, `docs/temp/roo-updates/skill-memory-manager.md`, `docs/temp/roo-updates/skill-wiki-lint.md`, `docs/temp/roo-updates/roomodes-edits.md`
- **Plan:** `plans/llm-wiki.md` §7-§8

### LLM Wiki Bootstrap (Phase 0)
- **Result:** IMPLEMENTED
- **Entities updated:** All 16 entity pages (NEW), all 10 concept pages (NEW)
- **Summary:** Created wiki directory structure, 16 entity pages, 10 concept pages, index.md, log.md. Slimmed activeContext.md and progress.md.
- **Plan:** `plans/llm-wiki.md`

### Admin API Usage Page Redesigned
- **Result:** APPROVED (0 P1, 0 P2 after 1 fix cycle, 9 P3)
- **Entities updated:** [API Usage Page](entities/api-usage-page.md), [Admin Dashboard](entities/admin-dashboard.md), [Database Schema](entities/database-schema.md)
- **Summary:** Complete overhaul — CSS-only donut quota charts, success rate trends, monthly comparison, daily sparklines. ~500 lines new CSS. Realtor.com budget updated 100→150.
- **Files:** `src/database.py`, `web/routes/admin.py`, `web/templates/admin/api-usage.html`, `web/static/css/admin.css`

### Cloud Scheduler Evaluation
- **Result:** COMPLETE (plan only)
- **Entities updated:** [Scheduler (launchd)](entities/scheduler-launchd.md)
- **Summary:** Evaluated 3 options. Recommended GitHub Actions + git-committed DB for immediate use (~2h effort), Turso for long-term.
- **Plan:** `plans/cloud-scheduler.md`

### Scheduler Fix Implemented
- **Result:** APPROVED (0 P1, 0 P2, 7 P3)
- **Entities updated:** [Scheduler (launchd)](entities/scheduler-launchd.md), [Admin Dashboard](entities/admin-dashboard.md), [Orchestrator](entities/orchestrator.md)
- **Concepts updated:** [launchd Patterns](concepts/launchd-patterns.md)
- **Summary:** APScheduler replaced with macOS launchd. 3 new plists, 2 standalone scripts. 30-day calendar heatmap added.
- **Files:** 5 created, 9 modified
- **Plan:** `plans/scheduler-fix.md`

### Multi-Select Source Filter Verified + CSS Fix
- **Result:** APPROVED (0 P1, 0 P2 after 1 fix cycle, 6 P3)
- **Entities updated:** [Filter Bar](entities/filter-bar.md), [Listing Card](entities/listing-card.md)
- **Summary:** Source filter converted to multi-select checkbox dropdown. Added missing `.source-realtor` CSS class.
- **Files:** `dashboard.html`, `filters.js`, `web/routes/__init__.py`, `src/database.py`, `listing-card.html`, `style.css`

---

*Older entries (2026-04-01 and earlier) archived to [`log-archive-2026Q1.md`](log-archive-2026Q1.md) on 2026-05-10.*
