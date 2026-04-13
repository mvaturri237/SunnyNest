"""Shared utilities for web routes."""

from __future__ import annotations


def parse_filters(
    *,
    filter_price: str | None = None,
    filter_price_min: str | None = None,
    filter_price_max: str | None = None,
    filter_beds: str | None = None,
    filter_baths: str | None = None,
    filter_source: str | None = None,
    filter_sqft_min: str | None = None,
    filter_sqft_max: str | None = None,
    filter_pet: str | None = None,
    filter_ac: str | None = None,
    filter_furnished: str | None = None,
    filter_favorites: str | None = None,
    filter_max_days: str | None = None,
) -> dict:
    """Parse dropdown filter values into a database filter dict.

    Shared by both the dashboard (initial page load) and the listings
    endpoint (HTMX partial updates) so that the same dropdown values
    always produce the same query filters.

    Supports both the legacy ``filter_price`` range format (e.g. ``"5000-6500"``)
    and the new ``filter_price_min`` / ``filter_price_max`` individual params
    from the redesigned filter bar.
    """
    filters: dict = {"is_active": True, "exclude_disliked": True}

    # Parse price — new min/max params take precedence over legacy range format
    if filter_price_min or filter_price_max:
        if filter_price_min:
            try:
                filters["min_price"] = int(filter_price_min)
            except (ValueError, TypeError):
                pass
        if filter_price_max:
            try:
                filters["max_price"] = int(filter_price_max)
            except (ValueError, TypeError):
                pass
    elif filter_price and filter_price != "any":
        # Legacy range format: "5000-6500" or "8000+"
        try:
            if filter_price.endswith("+"):
                filters["min_price"] = int(filter_price.rstrip("+"))
            else:
                parts = filter_price.split("-")
                if len(parts) == 2:
                    filters["min_price"] = int(parts[0])
                    filters["max_price"] = int(parts[1])
        except (ValueError, IndexError):
            pass

    # Parse bedrooms
    if filter_beds and filter_beds != "any":
        try:
            filters["min_bedrooms"] = int(filter_beds)
        except ValueError:
            pass

    # Parse bathrooms
    if filter_baths and filter_baths != "any":
        try:
            filters["min_bathrooms"] = int(filter_baths)
        except ValueError:
            pass

    # Parse source (supports comma-separated multi-select)
    if filter_source and filter_source not in ("any", "all"):
        sources = [s.strip() for s in filter_source.split(",") if s.strip()]
        if sources:
            filters["source"] = sources  # Pass as list

    # Parse square footage
    if filter_sqft_min:
        try:
            filters["min_sqft"] = int(filter_sqft_min)
        except (ValueError, TypeError):
            pass
    if filter_sqft_max:
        try:
            filters["max_sqft"] = int(filter_sqft_max)
        except (ValueError, TypeError):
            pass

    # Parse boolean feature filters
    if filter_pet and filter_pet == "1":
        filters["pet_friendly"] = True
    if filter_ac and filter_ac == "1":
        filters["ac"] = True
    if filter_furnished and filter_furnished == "1":
        filters["furnished"] = True

    # Parse favorites filter
    if filter_favorites and filter_favorites == "1":
        filters["is_favorite"] = True

    # Parse max days on market
    if filter_max_days and filter_max_days != "any":
        try:
            filters["max_days_listed"] = int(filter_max_days)
        except (ValueError, TypeError):
            pass

    return filters
