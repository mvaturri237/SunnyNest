# Geocoder

> Nominatim-based geocoding service with module-level singleton, LRU cache (1024 entries), and circuit breaker with 30-minute auto-reset.

**Status:** Active  
**Owner files:** `src/geocoder.py`  
**Config:** N/A (hardcoded settings)  
**Added:** 2026-03-27  
**Last updated:** 2026-03-27

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

## Key Files

| File | Purpose |
|------|---------|
| `src/geocoder.py` | Geocoding implementation with cache and circuit breaker |

## History

- [2026-03-27] Code review fixes: singleton pattern, bounded cache (1024), circuit breaker auto-reset (30 min)
- [2026-03-27] Initial implementation

## Related

- [Orchestrator](orchestrator.md) — calls geocoder in pipeline step 5
- [School Districts](school-districts.md) — uses geocoded lat/lng for point-in-polygon lookups
- [Security Patterns](../concepts/security-patterns.md) — no API key needed (free service)
