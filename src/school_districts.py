"""School district and attendance zone lookup for Sunnyvale, CA.

This module provides two levels of school information:

1. **District lookup** — ``get_school_district(zip_code)`` maps ZIP codes to
   district names (existing functionality).
2. **School assignment lookup** — ``get_assigned_schools(lat, lng)`` performs
   point-in-polygon lookups against GeoJSON attendance zone boundaries to
   determine the specific elementary, middle, and high school assigned to
   a given address.

The boundary data is loaded lazily from ``data/school-boundaries/`` on first
use and cached in a thread-safe singleton.
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    from shapely.geometry import Point, shape
    _HAS_SHAPELY = True
except ImportError:
    _HAS_SHAPELY = False

logger = logging.getLogger("rental_finder.school_districts")

if not _HAS_SHAPELY:
    logger.warning("shapely not installed — school assignment lookups will be disabled")

# ---------------------------------------------------------------------------
# ZIP code → school district mapping (existing functionality)
# ---------------------------------------------------------------------------

_ZIP_TO_DISTRICT: dict[str, str] = {
    "94085": "Sunnyvale School District / Fremont Union High School District",
    "94086": "Sunnyvale School District / Fremont Union High School District",
    "94087": "Cupertino Union School District / Fremont Union High School District",
    "94089": "Sunnyvale School District / Fremont Union High School District",
}


def get_school_district(zip_code: str) -> str | None:
    """Return the school district name for a Sunnyvale ZIP code.

    Args:
        zip_code: Five-digit ZIP code string (e.g. ``"94087"``).

    Returns:
        The district name, or ``None`` if the ZIP code is not in the
        Sunnyvale mapping.
    """
    district = _ZIP_TO_DISTRICT.get(zip_code)
    if district is None:
        logger.debug("No school district mapping for ZIP %s", zip_code)
    return district


# ---------------------------------------------------------------------------
# School attendance zone boundary lookup
# ---------------------------------------------------------------------------

# Base directory for boundary GeoJSON files
_BOUNDARIES_DIR = Path(__file__).resolve().parent.parent / "data" / "school-boundaries"

# School levels and their corresponding GeoJSON filenames
_LEVEL_FILES: dict[str, str] = {
    "elementary": "elementary.geojson",
    "middle": "middle.geojson",
    "high": "high.geojson",
}


@dataclass
class SchoolZone:
    """A single school attendance zone with its polygon geometry.

    Attributes:
        school_name: Full name of the school (e.g. "Cherry Chase Elementary School").
        district: District name (e.g. "Sunnyvale School District").
        polygon: Shapely geometry object for point-in-polygon testing.
    """

    school_name: str
    district: str
    polygon: Any  # shapely.geometry.Polygon or MultiPolygon


class _SchoolBoundaryStore:
    """Lazy-loaded, thread-safe singleton for school attendance zone boundaries.

    Loads GeoJSON boundary files from ``data/school-boundaries/`` on first
    access and caches the parsed polygons for sub-millisecond lookups.

    Usage::

        store = _SchoolBoundaryStore.instance()
        zones = store.zones  # dict[str, list[SchoolZone]]
    """

    _instance: _SchoolBoundaryStore | None = None
    _lock: threading.Lock = threading.Lock()

    def __init__(self) -> None:
        self._zones: dict[str, list[SchoolZone]] = {}
        self._loaded: bool = False
        self._load_lock: threading.Lock = threading.Lock()

    @classmethod
    def instance(cls) -> _SchoolBoundaryStore:
        """Return the singleton instance, creating it on first call."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @property
    def zones(self) -> dict[str, list[SchoolZone]]:
        """Return the loaded zones, triggering a load on first access."""
        if not self._loaded:
            with self._load_lock:
                if not self._loaded:
                    self._load_boundaries()
                    self._loaded = True
        return self._zones

    def _load_boundaries(self) -> None:
        """Load all GeoJSON boundary files from disk."""
        for level, filename in _LEVEL_FILES.items():
            filepath = _BOUNDARIES_DIR / filename
            if not filepath.exists():
                logger.warning(
                    "School boundary file not found: %s — %s lookups will return None",
                    filepath,
                    level,
                )
                self._zones[level] = []
                continue

            try:
                with open(filepath, encoding="utf-8") as f:
                    geojson = json.load(f)

                zones: list[SchoolZone] = []
                for feature in geojson.get("features", []):
                    props = feature.get("properties", {})
                    school_name = props.get("school_name", "Unknown School")
                    district = props.get("district", "")
                    geometry = feature.get("geometry")

                    if geometry is None:
                        logger.warning(
                            "Skipping feature with no geometry in %s: %s",
                            filename,
                            school_name,
                        )
                        continue

                    try:
                        polygon = shape(geometry)
                        zones.append(
                            SchoolZone(
                                school_name=school_name,
                                district=district,
                                polygon=polygon,
                            )
                        )
                    except Exception:
                        logger.exception(
                            "Failed to parse geometry for %s in %s",
                            school_name,
                            filename,
                        )

                self._zones[level] = zones
                logger.info(
                    "Loaded %d %s school zones from %s",
                    len(zones),
                    level,
                    filename,
                )

            except json.JSONDecodeError:
                logger.exception("Invalid JSON in %s", filepath)
                self._zones[level] = []
            except Exception:
                logger.exception("Failed to load %s", filepath)
                self._zones[level] = []


def get_assigned_schools(lat: float, lng: float) -> dict[str, str | None]:
    """Look up the assigned schools for a geographic coordinate.

    Performs point-in-polygon tests against the loaded attendance zone
    boundaries for each school level (elementary, middle, high).

    Args:
        lat: Latitude of the address.
        lng: Longitude of the address.

    Returns:
        A dictionary with keys ``"elementary"``, ``"middle"``, ``"high"``,
        each mapping to the school name (``str``) or ``None`` if no
        matching zone was found.

    Note:
        GeoJSON uses ``(longitude, latitude)`` coordinate order, so
        ``shapely.Point(lng, lat)`` is correct.
    """
    if not _HAS_SHAPELY:
        return {"elementary": None, "middle": None, "high": None}

    store = _SchoolBoundaryStore.instance()
    point = Point(lng, lat)  # GeoJSON order: (lng, lat)

    result: dict[str, str | None] = {
        "elementary": None,
        "middle": None,
        "high": None,
    }

    for level in ("elementary", "middle", "high"):
        zones = store.zones.get(level, [])
        for zone in zones:
            try:
                if zone.polygon.contains(point):
                    result[level] = zone.school_name
                    break
            except Exception:
                logger.exception(
                    "Point-in-polygon test failed for %s zone: %s",
                    level,
                    zone.school_name,
                )

    return result
