# Geocoder

> Nominatim-based geocoding service with module-level singleton, LRU cache (1024 entries), and circuit breaker with 30-minute auto-reset.

**Status:** Active
**Owner files:** `src/geocoder.py`
**Config:** N/A (hardcoded settings)
**Added:** 2026-03-27
**Last updated:** 2026-06-03

## Overview

The geocoder converts listing addresses to latitude/longitude coordinates using the OpenStreetMap Nominatim service. It's used in step 5 of the [Orchestrator](orchestrator.md) pipeline, after normalization and before school assignment.

The implementation follows several performance and reliability patterns: module-level singleton (no per-request instantiation), bounded LRU cache (prevents unbounded memory growth in long-running launchd processes), and circuit breaker with auto-reset (prevents hammering a failing service while allowing recovery).

## Architecture

- **Nominatim singleton:** Single `Nominatim()` instance at module level, reused across all geocode calls
- **LRU cache:** `OrderedDict` with max 1024 entries and LRU eviction — prevents unbounded memory growth
- **Circuit breaker:** Trips after 3 consecutive failures, auto-resets after 30 minutes (no process restart needed)
- **Free service:** No API key required, no budget constraints
- **Rate limiting:** Nominatim requires 1 request/second — respected via built-in delay

## Current State

- **Working:** Fully operational
- **Cache hit rate:** High for re-scrapes of existing listings (same addresses)
- **Circuit breaker:** Auto-resets after 30 minutes if Nominatim goes down temporarily

## ⚠️ Known caveat — silent city-centroid fallback in `geocode_address()` (discovered 2026-06-03, OPEN P2)

The public [`geocode_address(address, city)`](../../../src/geocoder.py:139) wrapper silently retries with just `"<city>, CA"` when Nominatim can't resolve the full street address, and returns the **city centroid** without any signal to the caller. Two production consequences:

1. **Map pin lies** — listings with poorly-known street addresses get pinned to Sunnyvale's geographic center instead of their true location. Filter-by-neighborhood is misleading.
2. **School assignment cascades the lie** — [`get_assigned_schools(lat, lng)`](../../../src/orchestrator.py:142) runs on the centroid and writes whatever schools happen to serve that point to `school_elementary` / `school_middle` / `school_high`. The DB is now persistently mis-tagged.

**Discovered while:** writing [`scripts/geocode_schools.py`](../../../scripts/geocode_schools.py) for the school-icons feature. Helper script worked around the bug by calling [`_do_geocode()`](../../../src/geocoder.py:55) directly so misses surface as `None`.

**Affected callers:** [`src/orchestrator.py:125`](../../../src/orchestrator.py:125) (scraper pipeline — all 3 sources), [`src/poi.py:99`](../../../src/poi.py:99).

**Fix options (deferred — needs separate task):**
- **Minimal:** Change return type to `(coords, source)` where `source ∈ {"address", "city_fallback", None}`; callers decide whether to accept fallback.
- **Cleanest:** Drop fallback from `geocode_address()` entirely; require explicit `fallback_to_city=True` opt-in. Touches a public signature, deserves planning cycle.

Tracked as part of the 2026-06-03 school-icons review cycle (see [log entry](../log.md)). Related concept: [Silent Failure Pattern](../concepts/silent-failure-pattern.md).

## Key Files

| File | Purpose |
|------|---------|
| `src/geocoder.py` | Geocoding implementation with cache and circuit breaker |

## History

- [2026-06-03] Silent city-centroid fallback in `geocode_address()` flagged as P2 by Code Reviewer (round-2 of school-icons feature). Not yet fixed — needs separate task. See "Known caveat" section above.
- [2026-03-27] Code review fixes: singleton pattern, bounded cache (1024), circuit breaker auto-reset (30 min)
- [2026-03-27] Initial implementation

## Related

- [Orchestrator](orchestrator.md) — calls geocoder in pipeline step 5
- [School Districts](school-districts.md) — uses geocoded lat/lng for point-in-polygon lookups
- [Map View](map-view.md) — also uses geocoder (one-shot via `scripts/geocode_schools.py`) for static school POI coordinates
- [Security Patterns](../concepts/security-patterns.md) — no API key needed (free service)
- [Silent Failure Pattern](../concepts/silent-failure-pattern.md) — `geocode_address()` city-centroid fallback is a textbook example
