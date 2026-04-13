"""Listings route — returns HTMX partial for filtered listing cards."""

from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Query, Request

from src.database import get_filtered_listings
from web.dependencies import templates
from web.routes import parse_filters

logger = logging.getLogger("rental_finder.web.listings")

router = APIRouter()


@router.get("/listings")
async def filtered_listings(
    request: Request,
    filter_price: Optional[str] = Query(None, description="Price range, e.g. '5000-6500'"),
    filter_price_min: Optional[str] = Query(None, description="Min price, e.g. '5000'"),
    filter_price_max: Optional[str] = Query(None, description="Max price, e.g. '6500'"),
    filter_beds: Optional[str] = Query(None, description="Min bedrooms, e.g. '3'"),
    filter_baths: Optional[str] = Query(None, description="Min bathrooms, e.g. '2'"),
    filter_source: Optional[str] = Query(None, description="Source: zillow, craigslist, or all"),
    filter_sort: Optional[str] = Query(None, description="Sort: newest, price_asc, price_desc"),
    filter_sqft_min: Optional[str] = Query(None, description="Min sqft, e.g. '800'"),
    filter_sqft_max: Optional[str] = Query(None, description="Max sqft, e.g. '1500'"),
    filter_pet: Optional[str] = Query(None, description="Pet friendly: '1' or ''"),
    filter_ac: Optional[str] = Query(None, description="Air conditioning: '1' or ''"),
    filter_furnished: Optional[str] = Query(None, description="Furnished: '1' or ''"),
    filter_favorites: Optional[str] = Query(None, description="Favorites only: '1' or ''"),
    filter_max_days: Optional[str] = Query(None, description="Max days on market, e.g. '30'"),
):
    """Return only the listing cards HTML partial (for HTMX swaps)."""
    filters = parse_filters(
        filter_price=filter_price,
        filter_price_min=filter_price_min,
        filter_price_max=filter_price_max,
        filter_beds=filter_beds,
        filter_baths=filter_baths,
        filter_source=filter_source,
        filter_sqft_min=filter_sqft_min,
        filter_sqft_max=filter_sqft_max,
        filter_pet=filter_pet,
        filter_ac=filter_ac,
        filter_furnished=filter_furnished,
        filter_favorites=filter_favorites,
        filter_max_days=filter_max_days,
    )

    listings = get_filtered_listings(filters)

    # Sort
    sort_key = filter_sort or "newest"
    if sort_key == "price_asc":
        listings.sort(key=lambda l: l.price or 0)
    elif sort_key == "price_desc":
        listings.sort(key=lambda l: l.price or 0, reverse=True)
    else:
        # newest — sort by listed_date or first_seen
        listings.sort(
            key=lambda l: l.listed_date or (l.first_seen.date() if l.first_seen else date.min),
            reverse=True,
        )

    return templates.TemplateResponse(
        request,
        "partials/listing-cards.html",
        context={
            "listings": listings,
            "listing_count": len(listings),
            "today": date.today(),
        },
    )
