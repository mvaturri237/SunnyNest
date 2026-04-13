"""Dashboard route — serves the main SunnyNest page at GET /."""

from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, Request

from src.database import get_filtered_listings
from src.poi import list_pois
from web.dependencies import templates
from web.routes import parse_filters

logger = logging.getLogger("rental_finder.web.dashboard")

router = APIRouter()

# Dropdown default values — the source of truth for initial page load.
# These MUST match the hidden input values in dashboard.html.
# Defaults derived from config.yaml filters (min_price=5000, max_price=6500,
# min_bedrooms=3) so the initial view shows the same ~8 listings the user expects.
_DROPDOWN_DEFAULTS = {
    "filter_price_min": "5000",
    "filter_price_max": "6500",
    "filter_beds": "3",
    "filter_baths": "any",
    "filter_source": "all",
    "filter_sort": "newest",
    "filter_sqft_min": "",
    "filter_sqft_max": "",
    "filter_pet": "",
    "filter_ac": "",
    "filter_furnished": "",
    "filter_favorites": "",
    "filter_max_days": "30",
}


@router.get("/")
async def dashboard(request: Request):
    """Render the full dashboard page with listings from the database."""
    filters = parse_filters(
        filter_price_min=_DROPDOWN_DEFAULTS["filter_price_min"],
        filter_price_max=_DROPDOWN_DEFAULTS["filter_price_max"],
        filter_beds=_DROPDOWN_DEFAULTS["filter_beds"],
        filter_baths=_DROPDOWN_DEFAULTS["filter_baths"],
        filter_source=_DROPDOWN_DEFAULTS["filter_source"],
        filter_sqft_min=_DROPDOWN_DEFAULTS["filter_sqft_min"],
        filter_sqft_max=_DROPDOWN_DEFAULTS["filter_sqft_max"],
        filter_pet=_DROPDOWN_DEFAULTS["filter_pet"],
        filter_ac=_DROPDOWN_DEFAULTS["filter_ac"],
        filter_furnished=_DROPDOWN_DEFAULTS["filter_furnished"],
        filter_favorites=_DROPDOWN_DEFAULTS["filter_favorites"],
        filter_max_days=_DROPDOWN_DEFAULTS["filter_max_days"],
    )

    listings = get_filtered_listings(filters)

    # Sort by newest first
    listings.sort(
        key=lambda l: l.listed_date or (l.first_seen.date() if l.first_seen else date.min),
        reverse=True,
    )

    # Load POIs for the panel
    pois = list_pois()
    category_icons = {
        "work": "🏢",
        "school": "🏫",
        "park": "🌳",
        "transit": "🚉",
        "shopping": "🛒",
        "custom": "📍",
    }

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        context={
            "listings": listings,
            "listing_count": len(listings),
            "today": date.today(),
            "active_filters": _DROPDOWN_DEFAULTS,
            "pois": pois,
            "category_icons": category_icons,
        },
    )
