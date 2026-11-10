# Zillow `available_date` Field-Verification Probe — Findings

**Date:** 2026-06-03
**Probe target:** ZLLW Working API `/search/byaddress` endpoint
**Sample size:** First 3 listings of a real scrape run (page 1, 25 total returned)
**Log:** `/tmp/avail-probe-1780494290.log` (lines tagged `[AVAIL-PROBE]`)

---

## TL;DR — Negative Result

**The `/search/byaddress` endpoint does NOT return any availability/move-in-date field.** Phase 1 (as scoped in [`plans/available-date-feature.md`](../../plans/available-date-feature.md:1)) **cannot** be implemented against the current Zillow scraper without a new API call.

**Populated rate: 0 of 3 sampled listings** had any field matching `avail|date|move` other than `listingDateTimeOnZillow` (which is the listing-creation timestamp, not the available-date).

---

## What the probe inspected

For each of 3 listings, the probe dumped (at `WARNING` level, prefixed `[AVAIL-PROBE]`):

1. `sorted(prop.keys())` — full top-level key set
2. Top-level keys matching `re.search(r"avail|date|move", k, re.IGNORECASE)`
3. `whatIWant` sub-dict keys — **did not exist in any sample**
4. `hdpView` sub-dict keys — exists but minimal: `['hdpUrl', 'listingStatus', 'price']`
5. `unitsGroup[0]` keys — **N/A**, all 3 samples were `resultType=property`, no `propertyGroup` in this sample
6. One-level-deep nested scan: every `prop[k]` that is a dict, scan its sub-keys for the same pattern — **zero matches**

## Top-level keys observed (identical structure across all 3 listings)

```
['address', 'bathrooms', 'bedrooms', 'bestGuessTimeZone', 'country',
 'currency', 'daysOnZillow', 'estimates', 'hasFloorPlan', 'hdpView',
 'isFeatured', 'isPreforeclosureAuction', 'isShowcaseListing',
 'isUnmappable', 'listCardRecommendation', 'listing',
 'listingDateTimeOnZillow', 'livingArea', 'location', 'media',
 'personalizedResult', 'price', 'propertyDisplayRules',
 'propertyHasLasViolation', 'propertyType', 'region', 'rental',
 'ssid', 'taxAssessment', 'zillowOwnedProperty', 'zpid']
```

The only key matching the search pattern is `listingDateTimeOnZillow`:

| Listing | `prop['listingDateTimeOnZillow']` |
|---|---|
| 1 | `'1780465627413'` (Unix-ms → 2026-06-03 08:47 UTC, **today** — listing date) |
| 2 | `'1780206684978'` (Unix-ms → 2026-05-31 09:11 UTC — listing date) |
| 3 | `'1780435634694'` (Unix-ms → 2026-06-03 00:27 UTC — listing date) |

These are clearly **listing-creation timestamps**, not availability dates. They correspond to what the scraper already derives from `daysOnZillow` into the `listed_date` column.

The nested `listing` and `rental` sub-dicts were scanned one level deep — **no `avail*`/`date*`/`move*` sub-keys were found in either**.

## propertyGroup case — unknown

This sample contained zero `resultType=propertyGroup` items (all 25 page-1 results were single properties). The probe block for `unitsGroup[0]` therefore never fired. We have **no evidence** about apartment-complex listings; a future probe would need to either widen the filter (`homeType` parameter currently set to `Houses`) or wait until a complex appears organically.

## Recommended Phase 1 extraction snippet

**None.** No snippet can reliably extract a value that the endpoint does not return.

```python
# Cannot be implemented against /search/byaddress — field does not exist.
# Possible future paths (each a separate spec):
#  (a) Call the per-listing detail endpoint /property?zpid=… for each result
#      — costs +25 API calls per page (5× our current usage; would blow the
#      500/mo free-tier budget in ~4 scrapes).
#  (b) Subscribe to a different Zillow RapidAPI provider that exposes
#      availability in search results.
#  (c) Drop Zillow availability and source the field from Realtor.com / Craigslist
#      only (where the probe has not yet been run).
```

## Recommendation for Orchestrator / next step

**Do NOT proceed with the Phase 1 wiring as originally scoped** (`prop["availabilityDate"]`-style extraction). Instead, route back to Architect to:

1. Re-scope the feature: investigate the Zillow `/property` detail endpoint cost-benefit (option a) **OR** scope availability as a Realtor-only / Craigslist-only feature (option c).
2. Run a second probe against `RealtorScraper.normalize()` and `CraigslistScraper.normalize()` (same 3-listing pattern) before any UI work — Phase 1 cannot be Zillow-only.
3. Update [`plans/available-date-feature.md`](../../plans/available-date-feature.md:1) to reflect the data-source reality.

## Probe hygiene

- Probe block added to [`src/scrapers/zillow_scraper.py`](../../src/scrapers/zillow_scraper.py:268), ran once, **reverted in full**.
- `git diff src/scrapers/zillow_scraper.py` is empty (verified post-revert).
- Zillow API budget impact: 1 call (page 1 only — page 2 not requested because page 1 returned a `lastPage` marker). Budget now ~4/500 for the month.
