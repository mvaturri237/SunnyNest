"""Geocoding service using Nominatim (OpenStreetMap) via geopy.

Provides address-to-coordinate lookups with in-memory caching and
rate limiting to comply with Nominatim's usage policy (max 1 req/s).
"""

from __future__ import annotations

import logging
import time
from collections import OrderedDict
from typing import Optional, Tuple

from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
from geopy.geocoders import Nominatim

logger = logging.getLogger("rental_finder.geocoder")

# ---------------------------------------------------------------------------
# Singleton Nominatim instance (P2-4)
# ---------------------------------------------------------------------------
_geolocator = Nominatim(user_agent="sunnyvale-rental-finder", timeout=10)

# ---------------------------------------------------------------------------
# Bounded LRU cache: full_address_string → (lat, lon)  (P2-5)
# ---------------------------------------------------------------------------
_CACHE_MAX_SIZE: int = 1024
_cache: OrderedDict[str, Tuple[float, float]] = OrderedDict()


def _cache_put(key: str, value: Tuple[float, float]) -> None:
    """Insert into the bounded cache, evicting oldest half when full."""
    _cache[key] = value
    _cache.move_to_end(key)
    if len(_cache) > _CACHE_MAX_SIZE:
        # Evict the oldest half
        evict_count = _CACHE_MAX_SIZE // 2
        for _ in range(evict_count):
            _cache.popitem(last=False)
        logger.info("Geocode cache evicted %d oldest entries (size was %d).", evict_count, _CACHE_MAX_SIZE + 1)


# Timestamp of the last geocoding request (for rate limiting)
_last_request_time: float = 0.0

# Circuit breaker: after N consecutive failures, skip geocoding entirely
# until auto-reset after a cooldown period.
_consecutive_failures: int = 0
_CIRCUIT_BREAKER_THRESHOLD: int = 3  # Trip after 3 consecutive failures
_circuit_open: bool = False
_circuit_open_since: Optional[float] = None  # P2-6: timestamp when circuit opened
_CIRCUIT_RESET_SECONDS: float = 1800.0  # 30 minutes


def _do_geocode(full_address: str) -> tuple[float, float] | None:
    """Perform a single geocode request with rate limiting and caching.

    Includes a circuit breaker: after 3 consecutive failures, all
    subsequent geocoding requests are skipped for 30 minutes, then
    the circuit auto-resets.

    Args:
        full_address: The complete address string to geocode.

    Returns:
        A ``(latitude, longitude)`` tuple, or ``None`` on failure.
    """
    global _last_request_time, _consecutive_failures, _circuit_open, _circuit_open_since

    # --- Circuit breaker: skip if service is known to be down ---
    if _circuit_open:
        # P2-6: Auto-reset after cooldown period
        if _circuit_open_since is not None and (time.time() - _circuit_open_since) >= _CIRCUIT_RESET_SECONDS:
            _circuit_open = False
            _consecutive_failures = 0
            _circuit_open_since = None
            logger.info(
                "⚡ Geocoder circuit breaker AUTO-RESET after %.0f s cooldown.",
                _CIRCUIT_RESET_SECONDS,
            )
        else:
            return None

    # --- Check cache first ---
    if full_address in _cache:
        logger.debug("Geocode cache hit: %s", full_address)
        _cache.move_to_end(full_address)  # Mark as recently used
        return _cache[full_address]

    # --- Rate limiting (1 req/s for Nominatim) ---
    elapsed = time.time() - _last_request_time
    if elapsed < 1.0:
        time.sleep(1.0 - elapsed)

    try:
        _last_request_time = time.time()
        location = _geolocator.geocode(full_address)

        if location is None:
            logger.warning("Geocoding returned no result for: %s", full_address)
            return None

        coords = (location.latitude, location.longitude)
        _cache_put(full_address, coords)
        # Reset circuit breaker on success
        _consecutive_failures = 0
        logger.info(
            "Geocoded %s → (%.6f, %.6f)",
            full_address,
            coords[0],
            coords[1],
        )
        return coords

    except GeocoderTimedOut:
        _consecutive_failures += 1
        logger.error("Geocoding timed out for: %s", full_address)
    except GeocoderUnavailable:
        _consecutive_failures += 1
        logger.error("Geocoder service unavailable for: %s", full_address)
    except Exception:
        _consecutive_failures += 1
        logger.exception("Unexpected geocoding error for: %s", full_address)

    # Check if we should trip the circuit breaker
    if _consecutive_failures >= _CIRCUIT_BREAKER_THRESHOLD:
        _circuit_open = True
        _circuit_open_since = time.time()
        logger.warning(
            "⚡ Geocoder circuit breaker OPEN after %d consecutive failures — "
            "skipping geocoding requests for %.0f s.",
            _consecutive_failures,
            _CIRCUIT_RESET_SECONDS,
        )

    return None


def geocode_address(
    address: str,
    city: str = "Sunnyvale",
    state: str = "CA",
) -> tuple[float, float] | None:
    """Geocode a street address and return its coordinates.

    Uses the free Nominatim geocoder with a 1-request-per-second rate
    limit.  Results are cached in a module-level dictionary so repeated
    lookups for the same address are instantaneous.

    Tries the full address first, then falls back to ``city, state`` if
    the specific address cannot be resolved (e.g. when only a
    neighbourhood name is available).

    Args:
        address: Street address (e.g. ``"123 Main St"``).
        city: City name.  Defaults to ``"Sunnyvale"``.
        state: US state abbreviation.  Defaults to ``"CA"``.

    Returns:
        A ``(latitude, longitude)`` tuple, or ``None`` when the address
        cannot be resolved.
    """
    full_address = f"{address}, {city}, {state}"
    result = _do_geocode(full_address)

    if result is not None:
        return result

    # Fallback: try geocoding with just city + state so the marker at
    # least appears in the correct city rather than being absent entirely.
    fallback_address = f"{city}, {state}"
    logger.info(
        "Primary geocode failed for %r — falling back to %r",
        full_address,
        fallback_address,
    )
    return _do_geocode(fallback_address)
