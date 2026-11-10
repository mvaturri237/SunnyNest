"""One-shot helper to geocode the 15 elementary schools used by the map.

Run manually; output is pasted into `web/static/js/map.js` (the `SCHOOLS`
constant near the top of the file). NOT scheduled — there is no need to
re-run unless the school list changes.

Usage:
    .venv/bin/python scripts/geocode_schools.py

Notes:
    - Uses the production geocoder at src.geocoder, so results are cached
      in the in-process LRU and the Nominatim circuit breaker is respected.
    - Nominatim is rate-limited to 1 req/s; 15 schools ≈ ~17s on a cold run
      (cache hits return instantly).
    - Validates each result against a widened bbox covering Sunnyvale +
      Los Altos + Santa Clara (the 3 cities where favorite-eligible
      elementary schools serving Sunnyvale-area renters are located) and
      flags out-of-bounds / null results so the operator can manually fix
      them.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on sys.path so `import src.geocoder` works when
# the script is invoked from anywhere.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.geocoder import _do_geocode  # noqa: E402

# We use the low-level `_do_geocode` (not `geocode_address`) because the
# public wrapper falls back to the city centroid when the specific
# address can't be resolved, which would silently produce a wrong-looking
# pin for the school. For this one-shot, we want to KNOW which addresses
# failed so we can apply a manual fallback.


# (school_name, street_address, city) — state defaults to CA.
# Most schools are Sunnyvale; the two CUSD/SCUSD outliers serving
# Sunnyvale-area renters live in Los Altos and Santa Clara.
SCHOOLS: list[tuple[str, str, str]] = [
    # Sunnyvale School District (SSD) — 8 schools
    ("Bishop Elementary",             "450 N Sunnyvale Ave",   "Sunnyvale"),
    ("Cherry Chase Elementary",       "1138 Heatherstone Way", "Sunnyvale"),
    ("Cumberland Elementary",         "824 Cumberland Dr",     "Sunnyvale"),
    ("Ellis Elementary",              "550 E Olive Ave",       "Sunnyvale"),
    ("Fairwood Explorer Elementary",  "1110 Fairwood Ave",     "Sunnyvale"),
    ("Lakewood Elementary",           "750 Lakechime Dr",      "Sunnyvale"),
    ("San Miguel Elementary",         "777 San Miguel Ave",    "Sunnyvale"),
    ("Vargas Elementary",             "1054 Carson Dr",        "Sunnyvale"),
    # Cupertino Union School District (CUSD) — 4 schools
    ("Chester W. Nimitz Elementary",     "545 E Cheyenne Dr",  "Sunnyvale"),
    ("Louis E. Stocklmeir Elementary",   "592 Dunholme Way",   "Sunnyvale"),
    ("West Valley Elementary",           "1635 Belleville Way","Sunnyvale"),
    ("Montclaire Elementary",            "1160 St. Joseph Ave","Los Altos"),
    # Santa Clara Unified School District (SCUSD) — 3 schools
    ("Braly Elementary",              "675 Gail Ave",          "Sunnyvale"),
    ("Ponderosa Elementary",          "804 Ponderosa Ave",     "Sunnyvale"),
    ("Laurelwood Elementary",         "955 Teal Dr",           "Santa Clara"),
]

# Widened bounding box: Sunnyvale + Los Altos (south-west, ~37.36/-122.08)
# + Santa Clara (east, ~37.36/-121.99). Was lat 37.34–37.42 / lng
# -122.07 to -121.96 — too tight for Los Altos addresses.
LAT_MIN, LAT_MAX = 37.32, 37.42
LNG_MIN, LNG_MAX = -122.12, -121.95


def in_bounds(lat: float, lng: float) -> bool:
    return LAT_MIN <= lat <= LAT_MAX and LNG_MIN <= lng <= LNG_MAX


def main() -> int:
    print("// --- BEGIN geocoded SCHOOLS block (paste into map.js) ---")
    failures: list[str] = []
    name_width = max(len(name) for name, _, _ in SCHOOLS) + 2  # +2 for quotes
    for name, addr, city in SCHOOLS:
        full = f"{addr}, {city}, CA"
        result = _do_geocode(full)
        quoted = f"'{name}',"
        if result is None:
            failures.append(f"{name}: returned None for '{full}'")
            print(f"    {{ name: {quoted:<{name_width + 1}} lat: null,      lng: null      }}, // GEOCODE FAILED — use manual fallback")
            continue
        lat, lng = result
        if not in_bounds(lat, lng):
            failures.append(
                f"{name}: out of bounds ({lat:.6f}, {lng:.6f}) for '{full}'"
            )
            print(
                f"    {{ name: {quoted:<{name_width + 1}} lat: {lat:.6f}, lng: {lng:.6f} }}, // OUT OF BOUNDS — verify or use manual fallback"
            )
            continue
        print(
            f"    {{ name: {quoted:<{name_width + 1}} lat: {lat:.6f}, lng: {lng:.6f} }},"
        )
    print("// --- END geocoded SCHOOLS block ---")

    if failures:
        print("\n// FAILURES (must be patched manually):", file=sys.stderr)
        for f in failures:
            print(f"//   - {f}", file=sys.stderr)
        return 1

    print(f"\n// All {len(SCHOOLS)} schools geocoded successfully and within widened bbox.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
