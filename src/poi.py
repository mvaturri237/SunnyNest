"""POI (Points of Interest) CRUD module backed by data/interest-points.json.

Provides functions to list, add, and delete user-defined interest points
such as workplaces, schools, parks, transit stops, and shopping centres.
"""

from __future__ import annotations

import json
import logging
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.geocoder import geocode_address

logger = logging.getLogger("rental_finder.poi")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
VALID_CATEGORIES = {"work", "school", "park", "transit", "shopping", "custom"}

_DATA_FILE = Path(__file__).parent.parent / "data" / "interest-points.json"

_file_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _read_store() -> list[dict[str, Any]]:
    """Read the JSON store and return the list of POI dicts."""
    if not _DATA_FILE.exists():
        return []
    try:
        with open(_DATA_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data.get("points", [])
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Failed to read POI store %s: %s", _DATA_FILE, exc)
        return []


def _write_store(points: list[dict[str, Any]]) -> None:
    """Persist the list of POI dicts back to the JSON file."""
    _DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(_DATA_FILE, "w", encoding="utf-8") as fh:
            json.dump({"points": points}, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
    except OSError as exc:
        logger.error("Failed to write POI store %s: %s", _DATA_FILE, exc)
        raise


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def list_pois() -> list[dict[str, Any]]:
    """Return all stored POIs as a list of dicts."""
    return _read_store()


def add_poi(
    category: str,
    name: str,
    address: str,
    lat: float | None = None,
    lng: float | None = None,
) -> dict[str, Any]:
    """Create a new POI, geocoding the address if coordinates are not provided.

    Args:
        category: One of the ``VALID_CATEGORIES``.
        name: Human-readable label (e.g. "My Office").
        address: Full street address.
        lat: Optional latitude — skips geocoding when provided.
        lng: Optional longitude — skips geocoding when provided.

    Returns:
        The newly created POI dict.

    Raises:
        ValueError: If *category* is invalid or geocoding fails.
    """
    if category not in VALID_CATEGORIES:
        raise ValueError(
            f"Invalid category '{category}'. Must be one of: {', '.join(sorted(VALID_CATEGORIES))}"
        )

    # Geocode if coordinates not supplied
    if lat is None or lng is None:
        # Pass the full address as-is (may include city/state already)
        coords = geocode_address(address, city="", state="")
        if coords is None:
            raise ValueError(f"Could not geocode address: {address}")
        lat, lng = coords

    poi: dict[str, Any] = {
        "id": f"poi_{uuid.uuid4().hex[:12]}",
        "category": category,
        "name": name,
        "address": address,
        "latitude": lat,
        "longitude": lng,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    with _file_lock:
        points = _read_store()
        points.append(poi)
        _write_store(points)

    logger.info("Added POI %s (%s) at (%.6f, %.6f)", poi["id"], name, lat, lng)
    return poi


def delete_poi(poi_id: str) -> bool:
    """Remove a POI by its ID.

    Returns:
        ``True`` if the POI was found and deleted, ``False`` otherwise.
    """
    with _file_lock:
        points = _read_store()
        original_len = len(points)
        points = [p for p in points if p.get("id") != poi_id]

        if len(points) == original_len:
            logger.warning("POI %s not found for deletion.", poi_id)
            return False

        _write_store(points)
        logger.info("Deleted POI %s", poi_id)
        return True
