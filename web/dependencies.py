"""Shared dependencies for the FastAPI web application."""

from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi.templating import Jinja2Templates

from src.utils import load_config

# Templates directory relative to the project root
_TEMPLATES_DIR = Path(__file__).parent / "templates"

templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


# ---------------------------------------------------------------------------
# Custom Jinja2 filters
# ---------------------------------------------------------------------------

# Known placeholder image patterns that should be treated as "no image"
_PLACEHOLDER_PATTERNS = ("empty.png",)


def _parse_first_image(image_urls_str: str | None) -> str | None:
    """Extract the first valid HTTP(S) image URL from a JSON-encoded list.

    Skips known placeholder images (e.g. Craigslist's ``empty.png``).

    Replaces the brittle ``listing.image_urls[2:-2].split(...)`` slicing
    that was previously done inside the template.
    """
    if not image_urls_str:
        return None
    try:
        urls = json.loads(image_urls_str)
        if isinstance(urls, list):
            for url in urls:
                url = str(url)
                if not url.startswith(("http://", "https://")):
                    continue
                if any(p in url for p in _PLACEHOLDER_PATTERNS):
                    continue
                return url
    except (json.JSONDecodeError, TypeError):
        pass
    return None


def _abbreviate_school(name: str | None) -> str:
    """Abbreviate common school-level suffixes for compact display.

    Examples:
        - ``"Cherry Chase Elementary School"`` → ``"Cherry Chase Elem"``
        - ``"Columbia Middle School"`` → ``"Columbia Middle"``
        - ``"Fremont High School"`` → ``"Fremont HS"``
        - ``"Sunnyvale Elementary"`` → ``"Sunnyvale Elem"``
    """
    if not name:
        return ""
    # Order matters — match longer patterns first
    replacements = [
        ("Elementary School", "Elem"),
        ("Elementary", "Elem"),
        ("Middle School", "Middle"),
        ("High School", "HS"),
    ]
    for pattern, replacement in replacements:
        name = name.replace(pattern, replacement)
    return name.strip()


# ---------------------------------------------------------------------------
# Favorite-school highlighting
# ---------------------------------------------------------------------------

# Feature flag — DISABLED 2026-06-04.
#
# The DB-derived school assignments (column `listing.school_elementary`,
# written by src/school_districts.py) are inaccurate: the GeoJSON polygons
# at data/school-boundaries/elementary.geojson are simplified rectangles,
# not official attendance boundaries. They produce visibly wrong tagging
# (e.g. Mountain View listings tagged "Cherry Chase Elementary", a Sunnyvale
# school). Until the planned NCES SABS attendance-boundary refresh lands
# (separate Architect plan), the two user-facing surfaces that depend on
# this column are hidden:
#
#   1. The "🏫 ..." schools row on listing cards
#      (web/templates/partials/listing-card.html)
#   2. The green ★ price-pill highlight on the map
#      (driven by data-fav-school="1" on the card, consumed by
#       web/static/js/map.js — when the attribute is absent, the
#       JS condition `card.dataset.favSchool === '1'` is false,
#       so no green class is applied; no JS change required.)
#
# What stays untouched (so re-enable is a one-line flip):
#   - FAVORITE_SCHOOLS frozenset + is_favorite_school helper below
#   - The 15-school SCHOOLS const in map.js (POI pins, hardcoded coords)
#   - .school-pill-fav and .price-pill-marker.is-fav-school CSS rules
#     (dormant, marked with DISABLED 2026-06-04 comments)
#   - The DB column + the school_districts.py enrichment pipeline
#
# Re-enable: set SCHOOLS_UI_ENABLED = True (and bump the style.css cache
# version in web/templates/base.html so users see the resurrected chip).
SCHOOLS_UI_ENABLED: bool = False


# Hardcoded v1 favorites — per-user upgrade tracked in P3-SCHOOL-FAVORITES-CFG.
#
# IMPORTANT — Cross-file drift warning:
# Must match the `name` field of `isFavorite: true` entries in the SCHOOLS
# array at web/static/js/map.js:50-69 byte-for-byte (case, spacing, the
# word "Elementary" vs "Elem"). If you edit one, edit the other.
#
# Naming-convention note: the canonical form here omits the trailing
# " School" word (e.g. "Cherry Chase Elementary"), matching map.js.
# The DB column `listing.school_elementary` is populated by
# src/school_districts.py from GeoJSON `school_name` properties, which
# include the suffix (e.g. "Cherry Chase Elementary School"). The
# `is_favorite_school()` helper normalizes that suffix before comparing,
# so the same constant works for both inputs.
FAVORITE_SCHOOLS: frozenset[str] = frozenset({
    "Cherry Chase Elementary",
    "Cumberland Elementary",
    "Louis E. Stocklmeir Elementary",
    "West Valley Elementary",
    "Montclaire Elementary",
    "Laurelwood Elementary",
})


def _normalize_school_name(name: str) -> str:
    """Strip the trailing " School" word so DB names match map.js names.

    DB form:    "Cherry Chase Elementary School"  →  "Cherry Chase Elementary"
    map.js form:"Cherry Chase Elementary"         →  "Cherry Chase Elementary"
    """
    # Only strip the trailing " School" — never an interior occurrence.
    for suffix in (" Elementary School", " Middle School", " High School"):
        if name.endswith(suffix):
            return name[: -len(" School")]
    return name


def is_favorite_school(name: str | None) -> bool:
    """True if ``name`` is one of the user's 6 favorite elementary schools.

    Case-sensitive on the full form. Tolerates the trailing " School" word
    so it works against both the DB column (written by ``school_districts.py``)
    and the canonical names used in ``map.js``.
    """
    if not name:
        return False
    return _normalize_school_name(name) in FAVORITE_SCHOOLS


templates.env.filters["first_image"] = _parse_first_image
templates.env.filters["abbreviate_school"] = _abbreviate_school
# Registered as a `test` (used as `value is is_favorite_school` in Jinja)
# so the syntax reads naturally. Also exposed as a filter for parity.
templates.env.tests["is_favorite_school"] = is_favorite_school
templates.env.filters["is_favorite_school"] = is_favorite_school

# Expose the feature flag to every template (incl. partials rendered via
# htmx swaps) without requiring per-route context wiring.
templates.env.globals["SCHOOLS_UI_ENABLED"] = SCHOOLS_UI_ENABLED


# ---------------------------------------------------------------------------
# Environment health check
# ---------------------------------------------------------------------------


def get_env_status() -> dict[str, dict[str, str]]:
    """Return the configuration status of each monitored env var.

    Used by the admin dashboard to render the System Health panel.

    Returns:
        A dict keyed by env-var name, each value being a dict with
        ``status`` (``"configured"`` | ``"missing"``) and ``detail``.
    """
    status: dict[str, dict[str, str]] = {}

    # RAPIDAPI_KEY
    if os.environ.get("RAPIDAPI_KEY"):
        status["RAPIDAPI_KEY"] = {
            "status": "configured",
            "detail": "Zillow scraper is active",
        }
    else:
        status["RAPIDAPI_KEY"] = {
            "status": "missing",
            "detail": "Zillow scraper will be disabled",
        }

    # REALTOR_RAPIDAPI_KEY (with RAPIDAPI_KEY fallback)
    realtor_key = os.environ.get("REALTOR_RAPIDAPI_KEY") or os.environ.get("RAPIDAPI_KEY")
    if realtor_key:
        status["REALTOR_RAPIDAPI_KEY"] = {
            "status": "configured",
            "detail": (
                "Realtor.com scraper is active"
                + (" (using RAPIDAPI_KEY fallback)" if not os.environ.get("REALTOR_RAPIDAPI_KEY") else "")
            ),
        }
    else:
        try:
            config = load_config()
            realtor_enabled = config.get("realtor_api", {}).get("enabled", True)
        except FileNotFoundError:
            realtor_enabled = True

        if realtor_enabled:
            status["REALTOR_RAPIDAPI_KEY"] = {
                "status": "missing",
                "detail": "Realtor.com scraper will be disabled",
            }
        else:
            status["REALTOR_RAPIDAPI_KEY"] = {
                "status": "configured",
                "detail": "Realtor.com scraper is disabled in config — key not required",
            }

    # SMTP_PASSWORD
    if os.environ.get("SMTP_PASSWORD"):
        status["SMTP_PASSWORD"] = {
            "status": "configured",
            "detail": "Email credentials set",
        }
    else:
        try:
            config = load_config()
            email_enabled = config.get("email", {}).get("enabled", False)
        except FileNotFoundError:
            email_enabled = False

        if email_enabled:
            status["SMTP_PASSWORD"] = {
                "status": "missing",
                "detail": "Email is enabled but password not set — notifications will fail",
            }
        else:
            status["SMTP_PASSWORD"] = {
                "status": "configured",
                "detail": "Email is disabled in config — password not required",
            }

    # NOTIFICATION_RECIPIENT
    if os.environ.get("NOTIFICATION_RECIPIENT"):
        status["NOTIFICATION_RECIPIENT"] = {
            "status": "configured",
            "detail": "Recipient set via env var",
        }
    else:
        status["NOTIFICATION_RECIPIENT"] = {
            "status": "configured",
            "detail": "Using recipient_email from config.yaml",
        }

    return status
