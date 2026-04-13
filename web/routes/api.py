"""API routes — serves data files (GeoJSON boundary, etc.) and POI CRUD."""

from __future__ import annotations

import logging
from enum import Enum
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field, ValidationError

from src.poi import VALID_CATEGORIES, add_poi, delete_poi, list_pois
from web.dependencies import templates

logger = logging.getLogger("rental_finder.web.api")

router = APIRouter(prefix="/api")

_DATA_DIR = Path(__file__).parent.parent.parent / "data"


# ---------------------------------------------------------------------------
# Boundary endpoint
# ---------------------------------------------------------------------------

@router.get("/boundary")
async def get_boundary():
    """Return the Sunnyvale city boundary as GeoJSON."""
    path = _DATA_DIR / "sunnyvale-boundary.geojson"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Boundary file not found")
    return FileResponse(path, media_type="application/json")


# ---------------------------------------------------------------------------
# POI Pydantic models
# ---------------------------------------------------------------------------

class POICategoryEnum(str, Enum):
    work = "work"
    school = "school"
    park = "park"
    transit = "transit"
    shopping = "shopping"
    custom = "custom"


class POICreate(BaseModel):
    category: POICategoryEnum
    name: str = Field(..., min_length=1, max_length=200)
    address: str = Field(..., min_length=1, max_length=500)
    lat: Optional[float] = None
    lng: Optional[float] = None


# ---------------------------------------------------------------------------
# POI endpoints
# ---------------------------------------------------------------------------

def _is_htmx(request: Request) -> bool:
    """Check if the request originates from HTMX."""
    return request.headers.get("HX-Request") == "true"


def _render_poi_list(request: Request):
    """Render the poi-list.html partial with current POIs."""
    pois = list_pois()
    # Build category icon lookup for the template
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
        "partials/poi-list.html",
        context={"pois": pois, "category_icons": category_icons},
    )


@router.get("/poi")
async def get_pois():
    """Return all POIs as a JSON array."""
    return JSONResponse(content=list_pois())


@router.post("/poi")
async def create_poi(request: Request):
    """Create a new POI.

    Accepts form data (from HTMX) or JSON (from API clients).
    Returns HTML partial for HTMX requests, JSON otherwise.
    """
    content_type = request.headers.get("content-type", "")

    # Parse input from form data or JSON
    if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
        form = await request.form()
        try:
            poi_data = POICreate(
                category=form.get("category", "").strip(),
                name=form.get("name", "").strip(),
                address=form.get("address", "").strip(),
                lat=float(form.get("lat")) if form.get("lat") else None,
                lng=float(form.get("lng")) if form.get("lng") else None,
            )
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        category = poi_data.category.value
        name = poi_data.name
        address = poi_data.address
        lat = poi_data.lat
        lng = poi_data.lng
    else:
        body = await request.json()
        try:
            poi_data = POICreate(**body)
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        category = poi_data.category.value
        name = poi_data.name
        address = poi_data.address
        lat = poi_data.lat
        lng = poi_data.lng

    try:
        poi = add_poi(category=category, name=name, address=address, lat=lat, lng=lng)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    if _is_htmx(request):
        return _render_poi_list(request)

    return JSONResponse(content=poi, status_code=201)


@router.delete("/poi/{poi_id}")
async def remove_poi(poi_id: str, request: Request):
    """Delete a POI by ID.

    Returns HTML partial for HTMX requests, JSON otherwise.
    """
    deleted = delete_poi(poi_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"POI '{poi_id}' not found.")

    if _is_htmx(request):
        return _render_poi_list(request)

    return JSONResponse(content={"deleted": True, "id": poi_id})
