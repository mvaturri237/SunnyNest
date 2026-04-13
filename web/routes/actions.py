"""User action routes — favorite/dislike toggles via HTMX."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from src.database import get_session, toggle_dislike, toggle_favorite
from src.models import Listing
from web.dependencies import templates

logger = logging.getLogger("rental_finder.web.actions")

router = APIRouter()


def _get_listing_by_id(listing_id: int) -> Listing | None:
    """Fetch a single listing by primary key (detached from session)."""
    with get_session() as session:
        listing = session.get(Listing, listing_id)
        if listing is not None:
            session.expunge(listing)
        return listing


@router.post("/favorite/{listing_id}")
async def favorite(request: Request, listing_id: int):
    """Toggle favorite status and return the updated button partial."""
    try:
        new_state = toggle_favorite(listing_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Listing not found")
    listing = _get_listing_by_id(listing_id)
    return templates.TemplateResponse(
        request,
        "partials/favorite-button.html",
        context={"listing": listing, "is_fav": new_state},
    )


@router.post("/dislike/{listing_id}")
async def dislike(request: Request, listing_id: int):
    """Toggle dislike status and remove the card from the DOM.

    When a listing is disliked it should disappear from the visible list.
    The card's hx-target is ``closest .listing-card`` with
    ``hx-swap="outerHTML"``, so returning empty HTML removes the card.
    Disliking also clears ``is_favorite`` in the database (handled by
    ``toggle_dislike``), but since the card is removed there is no stale
    favorite button to worry about (P1-1 resolved).
    """
    try:
        toggle_dislike(listing_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Listing not found")
    # Return empty HTML — the card is removed from the DOM via outerHTML swap
    return HTMLResponse("")
