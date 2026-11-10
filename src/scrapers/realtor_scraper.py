"""Realtor.com rental listing scraper using the Realtor Search API on RapidAPI.

Uses the Realtor Search API ``/properties/search-rent`` endpoint to fetch
rental listings for Sunnyvale, CA.  This complements the Zillow and
Craigslist scrapers by adding a third data source.

Subscribe to the free tier (100 req/month) at:
https://rapidapi.com  →  search "Realtor Search" by API_Jeeves
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
from datetime import date, datetime
from typing import Any

import httpx

from src.database import log_api_call, get_api_call_count
from src.scrapers.base import BaseScraper
from src.utils import load_config, resolve_cities

logger = logging.getLogger("rental_finder.scrapers.realtor")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SEARCH_URL = "https://realtor-search.p.rapidapi.com/properties/search-rent"


# ---------------------------------------------------------------------------
# Helper: property-type mapping
# ---------------------------------------------------------------------------

_PROPERTY_TYPE_MAP: dict[str, str] = {
    "single_family": "house",
    "multi_family": "apartment",
    "apartment": "apartment",
    "condo": "condo",
    "condos": "condo",
    "townhomes": "townhouse",
    "townhouse": "townhouse",
    "duplex_triplex": "apartment",
    "farm": "house",
    "land": "house",
    "mobile": "house",
    "mfd_mobile_home": "house",
}


def _map_property_type(raw_type: str | None) -> str:
    """Normalise a Realtor.com property-type string to our canonical set."""
    if not raw_type:
        return "house"
    return _PROPERTY_TYPE_MAP.get(raw_type.lower().replace("-", "").replace(" ", "_"), "house")


# ---------------------------------------------------------------------------
# Scraper implementation
# ---------------------------------------------------------------------------


class RealtorScraper(BaseScraper):
    """Scraper for Realtor.com rental listings via the Realtor Search API on RapidAPI.

    Requires a valid RapidAPI key configured via ``REALTOR_RAPIDAPI_KEY``
    (or ``RAPIDAPI_KEY`` as fallback) or in ``config.yaml``
    under ``realtor_api.rapidapi_key``.
    """

    def __init__(self) -> None:
        try:
            config = load_config()
        except FileNotFoundError:
            config = {}

        realtor_cfg = config.get("realtor_api", {})
        self.api_key: str = (
            os.environ.get("REALTOR_RAPIDAPI_KEY")
            or os.environ.get("RAPIDAPI_KEY")
            or realtor_cfg.get("rapidapi_key", "")
        )
        self.api_host: str = realtor_cfg.get(
            "rapidapi_host", "realtor-search.p.rapidapi.com"
        )
        self.enabled: bool = realtor_cfg.get("enabled", True)
        self.monthly_budget: int = realtor_cfg.get("monthly_budget", 100)
        self.budget_threshold: int = realtor_cfg.get("budget_threshold", 90)

        # Search params from shared config
        search_cfg = config.get("search", {})
        filters_cfg = config.get("filters", {})
        self.state: str = search_cfg.get("state", "CA")
        # Scrape territory: resolve the (possibly multi-city) list from config.
        # Backward-compatible with the legacy scalar ``search.city``.
        self.cities: list[str] = resolve_cities(search_cfg)
        self.min_price: int = filters_cfg.get("min_price", 5000)
        self.max_price: int = filters_cfg.get("max_price", 6500)
        self.min_beds: int = filters_cfg.get("min_bedrooms", 3)
        self.max_beds: int = filters_cfg.get("max_bedrooms", 4)

        # Scraper settings
        scraper_cfg = config.get("scraper", {})
        self.max_pages: int = scraper_cfg.get("max_pages", 2)
        self.delay_min: int = scraper_cfg.get("request_delay_min", 3)
        self.delay_max: int = scraper_cfg.get("request_delay_max", 8)

    # ----- BaseScraper interface ------------------------------------------

    async def scrape(self) -> list[dict]:
        """Fetch Realtor.com rental listings via the Realtor Search API.

        Returns:
            A list of raw listing dictionaries from the API response.
        """
        if not self.api_key:
            logger.warning(
                "Realtor.com RapidAPI key not configured — skipping Realtor.com scrape. "
                "Set REALTOR_RAPIDAPI_KEY (or RAPIDAPI_KEY) env var, "
                "or add realtor_api.rapidapi_key in config.yaml"
            )
            return []

        if not self.enabled:
            logger.info(
                "Realtor.com scraper is disabled in config (realtor_api.enabled=false). "
                "Skipping."
            )
            return []

        # --- Budget guard: skip if near monthly API limit ---
        api_count = get_api_call_count("realtor")
        if api_count >= self.budget_threshold:
            logger.warning(
                "⚠️ Realtor.com API budget guard: %d/%d calls used this month "
                "(threshold: %d). Skipping Realtor.com scrape to preserve quota.",
                api_count,
                self.monthly_budget,
                self.budget_threshold,
            )
            return []

        # Calculate remaining budget for this sync
        remaining_budget = self.monthly_budget - api_count
        effective_max_pages = min(self.max_pages, remaining_budget)
        if effective_max_pages < self.max_pages:
            logger.info(
                "Realtor.com API budget: %d calls remaining, limiting to %d pages.",
                remaining_budget,
                effective_max_pages,
            )

        if effective_max_pages <= 0:
            logger.warning(
                "Realtor.com API budget exhausted (%d/%d). Skipping.",
                api_count,
                self.monthly_budget,
            )
            return []

        all_listings: list[dict] = []

        headers = {
            "x-rapidapi-key": self.api_key,
            "x-rapidapi-host": self.api_host,
        }

        try:
            ssl_ctx = self._build_ssl_context()
            async with httpx.AsyncClient(
                timeout=30.0,
                verify=ssl_ctx,
            ) as client:
                # --- Outer loop: one page loop per configured city ---
                for city in self.cities:
                    logger.info(
                        "Realtor.com scrape starting for city=%s (%d configured "
                        "cit%s)",
                        city,
                        len(self.cities),
                        "y" if len(self.cities) == 1 else "ies",
                    )
                    total_pages_from_api: int | None = None

                    for page_num in range(1, effective_max_pages + 1):
                        # Per-API-call budget guard: re-check the live monthly
                        # count so a multi-city run halts pagination the moment
                        # the threshold is hit, regardless of how many cities
                        # remain. (ADR-002: reuse the existing guard per call.)
                        current_count = get_api_call_count("realtor")
                        if current_count >= self.budget_threshold:
                            logger.warning(
                                "⚠️ Realtor.com API budget guard tripped mid-run "
                                "(%d/%d, threshold %d) at city=%s page %d "
                                "— stopping all remaining requests.",
                                current_count,
                                self.monthly_budget,
                                self.budget_threshold,
                                city,
                                page_num,
                            )
                            return all_listings

                        # Stop if we already know we've passed the last page
                        if total_pages_from_api is not None and page_num > total_pages_from_api:
                            logger.info(
                                "Reached last page (%d) for city=%s — next city.",
                                total_pages_from_api,
                                city,
                            )
                            break

                        params: dict[str, Any] = {
                            "location": f"city:{city}, {self.state}",
                            "sortBy": "best_match",
                            "propertyType": "single_family",
                            "limit": 20,
                            "page": page_num,
                        }

                        logger.info(
                            "Realtor.com API request page %d: "
                            "location=city:%s, %s",
                            page_num,
                            city,
                            self.state,
                        )

                        try:
                            response = await client.get(
                                _SEARCH_URL, headers=headers, params=params
                            )
                            response.raise_for_status()
                            # Log successful API call (after raise_for_status to avoid double-logging)
                            log_api_call(
                                "realtor",
                                endpoint=_SEARCH_URL,
                                status_code=response.status_code,
                            )
                        except httpx.HTTPStatusError as exc:
                            log_api_call(
                                "realtor",
                                endpoint=_SEARCH_URL,
                                status_code=exc.response.status_code,
                            )
                            logger.error(
                                "Realtor.com API HTTP %d on page %d (city=%s): %s",
                                exc.response.status_code,
                                page_num,
                                city,
                                exc,
                            )
                            if exc.response.status_code == 429:
                                logger.warning("Rate limited — stopping pagination.")
                            break
                        except httpx.RequestError as exc:
                            log_api_call(
                                "realtor", endpoint=_SEARCH_URL, status_code=None
                            )
                            logger.error(
                                "Realtor.com API request error on page %d (city=%s): %s",
                                page_num,
                                city,
                                exc,
                            )
                            break

                        try:
                            data = response.json()
                        except Exception:
                            logger.error(
                                "Failed to parse Realtor.com API JSON on page %d "
                                "(city=%s)",
                                page_num,
                                city,
                            )
                            break

                        # Log raw response on first call for format verification
                        if page_num == 1:
                            logger.debug(
                                "Realtor.com raw response keys: %s",
                                list(data.keys()) if isinstance(data, dict) else type(data).__name__,
                            )

                        # Check for API-level errors — status is boolean True/False
                        api_status = data.get("status")
                        api_message = data.get("message", "")
                        if api_status is not True:
                            logger.error(
                                "Realtor.com API returned non-success status: %s, message: %s",
                                api_status,
                                api_message,
                            )
                            break

                        # Extract search results from data.results
                        results_container = data.get("data", {})
                        if isinstance(results_container, dict):
                            search_results = results_container.get("results", [])
                            total = results_container.get("total", 0)
                        else:
                            search_results = []
                            total = 0

                        # Extract pagination metadata from meta
                        meta = data.get("meta", {})
                        if isinstance(meta, dict):
                            total_pages_from_api = meta.get("totalPage", 1)
                        else:
                            total_pages_from_api = 1

                        if not search_results:
                            logger.info(
                                "No more results on page %d (city=%s) — next city.",
                                page_num,
                                city,
                            )
                            break

                        all_listings.extend(search_results)
                        logger.info(
                            "Realtor.com API page %d/%s (city=%s): %d listings "
                            "(total so far: %d, API reports %d total)",
                            page_num,
                            total_pages_from_api,
                            city,
                            len(search_results),
                            len(all_listings),
                            total,
                        )

                        # Check if we've reached the last page
                        if page_num >= total_pages_from_api:
                            logger.info(
                                "Reached last page (%d/%d) for city=%s. Next city.",
                                page_num,
                                total_pages_from_api,
                                city,
                            )
                            break

                        # Random delay between API calls
                        delay = random.uniform(self.delay_min, self.delay_max)
                        logger.debug(
                            "Sleeping %.1f s before next Realtor.com API page",
                            delay,
                        )
                        await asyncio.sleep(delay)

        except Exception:
            logger.exception("Fatal error during Realtor.com API scrape")

        logger.info(
            "Realtor.com scrape complete — %d raw listings collected.",
            len(all_listings),
        )
        return all_listings

    def normalize(self, raw: dict) -> dict:
        """Map a raw Realtor Search API listing dict to Listing model fields.

        Args:
            raw: A single item from the ``data.results`` array.

        Returns:
            A dictionary whose keys correspond to Listing column names.
        """
        # --- Identification -----------------------------------------------
        external_id = str(
            raw.get("property_id") or raw.get("listing_id") or ""
        )

        # --- Location -----------------------------------------------------
        location = raw.get("location", {})
        addr_obj = location.get("address", {}) if isinstance(location, dict) else {}
        street = addr_obj.get("line", "")
        city = addr_obj.get("city", "Sunnyvale")
        state = addr_obj.get("state_code", "CA")
        zip_code = str(addr_obj.get("postal_code", ""))

        # Build full address string
        if street:
            address = f"{street}, {city}, {state} {zip_code}".strip(", ")
        else:
            address = f"{city}, {state} {zip_code}".strip(", ")

        # Neighborhood — API uses "neighborhoods" (often null); fall back to county
        neighborhood = None
        if isinstance(location, dict):
            neighborhoods = location.get("neighborhoods")
            if isinstance(neighborhoods, list) and neighborhoods:
                first = neighborhoods[0]
                neighborhood = first.get("name") if isinstance(first, dict) else str(first)
            elif isinstance(neighborhoods, str) and neighborhoods:
                neighborhood = neighborhoods
            else:
                neighborhood = None
            if not neighborhood:
                county = location.get("county")
                if isinstance(county, dict):
                    neighborhood = county.get("name")

        # --- Price --------------------------------------------------------
        price = self._extract_price(raw)

        # --- Description fields -------------------------------------------
        description = raw.get("description", {})
        if not isinstance(description, dict):
            description = {}

        # Beds: single-unit has "beds", multi-unit has "beds_min"/"beds_max"
        bedrooms = description.get("beds")
        if bedrooms is None:
            beds_min = description.get("beds_min")
            beds_max = description.get("beds_max")
            bedrooms = beds_min if beds_min is not None else (beds_max if beds_max is not None else 0)

        # Baths: single-unit has "baths", multi-unit has "baths_min"/"baths_max"
        bathrooms = description.get("baths")
        if bathrooms is None:
            baths_min = description.get("baths_min")
            baths_max = description.get("baths_max")
            bathrooms = baths_min if baths_min is not None else (baths_max if baths_max is not None else 0.0)

        # Handle baths_full + baths_half if baths is still missing/zero
        if not bathrooms:
            baths_full = description.get("baths_full", 0) or 0
            baths_half = description.get("baths_half", 0) or 0
            bathrooms = baths_full + 0.5 * baths_half

        # --- Square footage -----------------------------------------------
        # Single-unit has "sqft", multi-unit has "sqft_min"/"sqft_max"
        sqft = description.get("sqft")
        if sqft is None:
            sqft_min = description.get("sqft_min")
            sqft_max = description.get("sqft_max")
            sqft = sqft_min if sqft_min is not None else sqft_max
        if isinstance(sqft, str):
            try:
                sqft = int(sqft.replace(",", ""))
            except ValueError:
                sqft = None
        elif isinstance(sqft, float):
            sqft = int(sqft)

        # --- Property type ------------------------------------------------
        property_type = _map_property_type(description.get("type"))

        # --- URL ----------------------------------------------------------
        # Use href from API response; fall back to constructed URL
        detail_url = raw.get("href", "")
        if not detail_url:
            detail_url = f"https://www.realtor.com/realestateandhomes-detail/{external_id}"

        # --- Images -------------------------------------------------------
        photos = raw.get("photos", [])
        if isinstance(photos, list):
            image_urls: list[str] = [
                p.get("href", "") for p in photos[:10]
                if isinstance(p, dict) and p.get("href")
            ]
        else:
            image_urls = []

        # --- Title --------------------------------------------------------
        desc_text = description.get("text", "")
        if desc_text:
            title = desc_text[:100]
        else:
            title = address

        # --- Geolocation --------------------------------------------------
        coordinate = addr_obj.get("coordinate", {})
        if not isinstance(coordinate, dict):
            coordinate = {}
        lat = coordinate.get("lat")
        lng = coordinate.get("lon")  # Note: Realtor.com uses "lon" not "lng"

        # --- Dates --------------------------------------------------------
        listed_date = self._parse_list_date(raw)

        # --- Pet policy ---------------------------------------------------
        pet_friendly = self._extract_pet_friendly(raw)

        # --- Parking ------------------------------------------------------
        parking = self._extract_parking(raw)

        # --- Laundry ------------------------------------------------------
        laundry = self._extract_laundry(raw)

        return {
            "external_id": external_id,
            "source": "realtor",
            "url": detail_url,
            "title": title,
            "address": address,
            "neighborhood": neighborhood,
            "city": city,
            "zip_code": zip_code,
            "price": price,
            "bedrooms": int(bedrooms) if bedrooms else 0,
            "bathrooms": float(bathrooms) if bathrooms else 0.0,
            "sqft": sqft,
            "property_type": property_type,
            "pet_friendly": pet_friendly,
            "parking": parking,
            "laundry": laundry,
            "image_urls": json.dumps(image_urls) if image_urls else None,
            "latitude": float(lat) if lat else None,
            "longitude": float(lng) if lng else None,
            "listed_date": listed_date,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_price(raw: dict) -> float | None:
        """Extract the monthly rent from the Realtor.com response.

        The price is usually at the top level as ``list_price``.
        Falls back to ``list_price_min`` for range listings.

        Args:
            raw: A single listing dict from the API response.

        Returns:
            The monthly rent as a float, or None if not found.
        """
        price = raw.get("list_price")
        if price is not None and isinstance(price, (int, float)) and price > 0:
            return float(price)
        # Fallback: check list_price_min for multi-unit/range listings
        price_min = raw.get("list_price_min")
        if price_min is not None and isinstance(price_min, (int, float)) and price_min > 0:
            return float(price_min)
        return None

    @staticmethod
    def _extract_pet_friendly(raw: dict) -> bool | None:
        """Extract pet policy from the Realtor.com response.

        Checks the ``pet_policy`` object for explicit boolean fields
        (``cats``, ``dogs``) and text descriptions.

        Args:
            raw: A single listing dict from the API response.

        Returns:
            ``True`` if pets are allowed, ``False`` if not, ``None`` if unknown.
        """
        pet_policy = raw.get("pet_policy")
        if not pet_policy or not isinstance(pet_policy, dict):
            return None
        # Check explicit boolean fields
        if pet_policy.get("cats") or pet_policy.get("dogs"):
            return True
        # Check text description
        text = pet_policy.get("text", "")
        if isinstance(text, str):
            lower = text.lower()
            # Check negative keywords first to avoid false positives
            # (e.g., "Pets not ok" should NOT match "ok" as True)
            if any(kw in lower for kw in ("no pet", "not allowed", "not ok", "none")):
                return False
            if any(kw in lower for kw in ("dog", "cat", "pet", "allowed", "ok")):
                return True
        return None

    @staticmethod
    def _extract_parking(raw: dict) -> str | None:
        """Extract parking information from the Realtor.com response.

        Checks the ``details`` array for parking/garage-related categories
        (e.g. "Exterior and Lot Features", "Community Features"),
        and falls back to ``description.garage``.

        Args:
            raw: A single listing dict from the API response.

        Returns:
            A parking description string, or ``None`` if not available.
        """
        _PARKING_CATEGORIES = (
            "parking", "garage", "exterior and lot features",
            "community features",
        )
        _PARKING_KEYWORDS = ("garage", "parking", "carport", "driveway")

        details = raw.get("details") or []
        if isinstance(details, list):
            for detail in details:
                if not isinstance(detail, dict):
                    continue
                category = (detail.get("category") or "").lower()
                if category in _PARKING_CATEGORIES:
                    texts = detail.get("text") or []
                    if isinstance(texts, list) and texts:
                        # If category is specifically parking/garage, return all texts
                        if category in ("parking", "garage"):
                            return ", ".join(str(t) for t in texts if t)
                        # For broader categories, filter to parking-related texts
                        parking_texts = [
                            str(t) for t in texts if t
                            and any(kw in str(t).lower() for kw in _PARKING_KEYWORDS)
                        ]
                        if parking_texts:
                            return ", ".join(parking_texts)
        # Fallback: check description.garage field
        description = raw.get("description", {})
        if isinstance(description, dict):
            garage = description.get("garage")
            if garage and isinstance(garage, (int, float)) and garage > 0:
                return f"{int(garage)}-car garage"
        return None

    @staticmethod
    def _extract_laundry(raw: dict) -> str | None:
        """Extract laundry information from the Realtor.com response.

        Checks the ``details`` array for laundry-related categories and text.

        Args:
            raw: A single listing dict from the API response.

        Returns:
            A laundry description string, or ``None`` if not available.
        """
        details = raw.get("details") or []
        if isinstance(details, list):
            for detail in details:
                if not isinstance(detail, dict):
                    continue
                category = (detail.get("category") or "").lower()
                texts = detail.get("text") or []
                if not isinstance(texts, list):
                    continue

                # Check if category is explicitly "laundry"
                if category == "laundry":
                    combined = ", ".join(str(t) for t in texts if t).lower()
                    if "in unit" in combined or "in-unit" in combined:
                        return "in-unit"
                    if "hookup" in combined:
                        return "hookups"
                    if "shared" in combined or "common" in combined:
                        return "shared"
                    if texts:
                        return ", ".join(str(t) for t in texts if t)

                # Also scan other categories for laundry-related text items
                laundry_texts = [
                    str(t) for t in texts if t
                    and "laundry" in str(t).lower()
                ]
                if laundry_texts:
                    combined = ", ".join(laundry_texts).lower()
                    if "in unit" in combined or "in-unit" in combined:
                        return "in-unit"
                    if "hookup" in combined:
                        return "hookups"
                    if "shared" in combined or "common" in combined:
                        return "shared"
                    return ", ".join(laundry_texts)
        return None

    @staticmethod
    def _parse_list_date(raw: dict) -> date | None:
        """Parse the listing date from the Realtor.com response.

        Expects an ISO 8601 string like ``"2026-03-15T00:00:00Z"``
        or with microseconds ``"2026-03-23T21:35:42.000000Z"``.

        Args:
            raw: A single listing dict from the API response.

        Returns:
            A ``date`` object, or ``None`` if not available or unparseable.
        """
        list_date_str = raw.get("list_date")
        if not list_date_str:
            return None
        try:
            # ISO 8601: "2026-03-15T00:00:00Z"
            return datetime.fromisoformat(
                list_date_str.replace("Z", "+00:00")
            ).date()
        except (ValueError, AttributeError):
            return None
