"""Zillow rental listing scraper using the ZLLW Working API on RapidAPI.

Uses the ZLLW Working API ``/search/byaddress`` endpoint to fetch rental
listings for Sunnyvale, CA.  This avoids Zillow's aggressive anti-bot
protection (PerimeterX CAPTCHA) that blocks direct scraping.

Subscribe to the free tier (500 req/month) at:
https://rapidapi.com  →  search "ZLLW Working API" by ONEAPI
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
from datetime import date, timedelta
from typing import Any

import httpx

from src.database import log_api_call, get_api_call_count
from src.scrapers.base import BaseScraper
from src.utils import load_config

logger = logging.getLogger("rental_finder.scrapers.zillow")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SEARCH_URL = "https://zllw-working-api.p.rapidapi.com/search/byaddress"


# ---------------------------------------------------------------------------
# Helper: property-type mapping
# ---------------------------------------------------------------------------

_PROPERTY_TYPE_MAP: dict[str, str] = {
    "singlefamily": "house",
    "single_family": "house",
    "house": "house",
    "townhome": "townhouse",
    "townhouse": "townhouse",
    "apartment": "apartment",
    "condo": "condo",
    "multi_family": "apartment",
    "multifamily": "apartment",
    "manufactured": "house",
    "lot": "house",
}


def _map_property_type(raw_type: str | None) -> str:
    """Normalise a Zillow property-type string to our canonical set."""
    if not raw_type:
        return "house"
    return _PROPERTY_TYPE_MAP.get(raw_type.lower().replace("-", "").replace(" ", ""), "house")


# ---------------------------------------------------------------------------
# Scraper implementation
# ---------------------------------------------------------------------------


class ZillowScraper(BaseScraper):
    """Scraper for Zillow rental listings via the ZLLW Working API on RapidAPI.

    Requires a valid RapidAPI key configured in ``config.yaml``
    under ``zillow_api.rapidapi_key``.
    """

    def __init__(self) -> None:
        try:
            config = load_config()
        except FileNotFoundError:
            config = {}

        zillow_cfg = config.get("zillow_api", {})
        self.api_key: str = os.environ.get("RAPIDAPI_KEY") or zillow_cfg.get("rapidapi_key", "")
        self.api_host: str = zillow_cfg.get(
            "rapidapi_host", "zllw-working-api.p.rapidapi.com"
        )

        filters_cfg = config.get("filters", {})
        search_cfg = config.get("search", {})

        self.location: str = (
            f"{search_cfg.get('city', 'Sunnyvale')}, "
            f"{search_cfg.get('state', 'CA')}"
        )
        self.min_price: int = filters_cfg.get("min_price", 5000)
        self.max_price: int = filters_cfg.get("max_price", 6500)
        self.min_beds: int = filters_cfg.get("min_bedrooms", 3)
        self.max_beds: int = filters_cfg.get("max_bedrooms", 4)

        scraper_cfg = config.get("scraper", {})
        self.max_pages: int = scraper_cfg.get("max_pages", 5)
        self.delay_min: int = scraper_cfg.get("request_delay_min", 3)
        self.delay_max: int = scraper_cfg.get("request_delay_max", 8)

    # ----- BaseScraper interface ------------------------------------------

    async def scrape(self) -> list[dict]:
        """Fetch Zillow rental listings via the ZLLW Working API.

        Returns:
            A list of raw listing dictionaries from the API response.
        """
        if not self.api_key:
            logger.warning(
                "Zillow RapidAPI key not configured — skipping Zillow scrape. "
                "Set zillow_api.rapidapi_key in config.yaml"
            )
            return []

        # --- Budget guard: skip if near monthly API limit ---
        api_count = get_api_call_count("zillow")
        api_limit = 500
        budget_threshold = 450  # 90% of limit
        if api_count >= budget_threshold:
            logger.warning(
                "⚠️ Zillow API budget guard: %d/%d calls used this month "
                "(threshold: %d). Skipping Zillow scrape to preserve quota.",
                api_count,
                api_limit,
                budget_threshold,
            )
            return []

        # Calculate remaining budget for this sync
        remaining_budget = api_limit - api_count
        effective_max_pages = min(self.max_pages, remaining_budget)
        if effective_max_pages < self.max_pages:
            logger.info(
                "Zillow API budget: %d calls remaining, limiting to %d pages.",
                remaining_budget,
                effective_max_pages,
            )

        all_listings: list[dict] = []

        headers = {
            "Content-Type": "application/json",
            "x-rapidapi-key": self.api_key,
            "x-rapidapi-host": self.api_host,
        }

        # Build the monthlyPayment filter string
        monthly_payment = f"min:{self.min_price}, max:{self.max_price}"

        try:
            ssl_ctx = self._build_ssl_context()
            async with httpx.AsyncClient(
                timeout=30.0,
                verify=ssl_ctx,
            ) as client:
                for page_num in range(1, effective_max_pages + 1):
                    params: dict[str, str] = {
                        "location": self.location,
                        "page": str(page_num),
                        "sortOrder": "Rental_Priority_Score",
                        "listingStatus": "For_Rent",
                        "monthlyPayment": monthly_payment,
                        "bed_min": str(self.min_beds),
                        "bed_max": str(self.max_beds),
                        "bathrooms": "Any",
                        "homeType": "Houses",
                    }

                    logger.info(
                        "Zillow API request page %d: location=%s, price=%d-%d, beds=%d-%d",
                        page_num,
                        self.location,
                        self.min_price,
                        self.max_price,
                        self.min_beds,
                        self.max_beds,
                    )

                    try:
                        response = await client.get(
                            _SEARCH_URL, headers=headers, params=params
                        )
                        # Log the API call
                        log_api_call("zillow", endpoint=_SEARCH_URL, status_code=response.status_code)
                        response.raise_for_status()
                    except httpx.HTTPStatusError as exc:
                        log_api_call("zillow", endpoint=_SEARCH_URL, status_code=exc.response.status_code)
                        logger.error(
                            "Zillow API HTTP %d on page %d: %s",
                            exc.response.status_code,
                            page_num,
                            exc,
                        )
                        if exc.response.status_code == 429:
                            logger.warning("Rate limited — stopping pagination.")
                        break
                    except httpx.RequestError as exc:
                        log_api_call("zillow", endpoint=_SEARCH_URL, status_code=None)
                        logger.error(
                            "Zillow API request error on page %d: %s",
                            page_num,
                            exc,
                        )
                        break

                    try:
                        data = response.json()
                    except Exception:
                        logger.error(
                            "Failed to parse Zillow API JSON on page %d",
                            page_num,
                        )
                        break

                    # Check for API-level errors
                    if data.get("message") != "200":
                        logger.error(
                            "Zillow API returned non-200 message: %s",
                            data.get("message"),
                        )
                        break

                    # Extract search results
                    search_results = data.get("searchResults", [])
                    if not search_results:
                        logger.info(
                            "No more results on page %d — stopping.", page_num
                        )
                        break

                    all_listings.extend(search_results)
                    logger.info(
                        "Zillow API page %d: %d listings (total so far: %d)",
                        page_num,
                        len(search_results),
                        len(all_listings),
                    )

                    # Check if there are more pages
                    pages_info = data.get("pagesInfo", {})
                    total_pages = pages_info.get("totalPages", 1)
                    if page_num >= total_pages:
                        logger.info("Reached last page (%d).", total_pages)
                        break

                    # Random delay between API calls (matching Craigslist pattern)
                    delay = random.uniform(self.delay_min, self.delay_max)
                    logger.debug("Sleeping %.1f s before next Zillow API page", delay)
                    await asyncio.sleep(delay)

        except Exception:
            logger.exception("Fatal error during Zillow API scrape")

        logger.info(
            "Zillow scrape complete — %d raw listings collected.",
            len(all_listings),
        )

        # NOTE: Client-side price filtering has been removed.
        # All scraped listings are stored in the database regardless of price.
        # Price filtering is handled by the UI dashboard at query time,
        # allowing users to dynamically adjust the price range via the slider.
        return all_listings

    def normalize(self, raw: dict) -> dict:
        """Map a raw ZLLW Working API listing dict to Listing model fields.

        Handles both ``resultType: "property"`` (single listing) and
        ``resultType: "propertyGroup"`` (apartment complex with units).

        Args:
            raw: A single item from the ``searchResults`` array.

        Returns:
            A dictionary whose keys correspond to Listing column names.
        """
        prop = raw.get("property", {})
        result_type = raw.get("resultType", "property")

        # --- Identification -----------------------------------------------
        zpid = str(prop.get("zpid", ""))

        # --- Address ------------------------------------------------------
        addr = prop.get("address", {})
        street = addr.get("streetAddress", "")
        city = addr.get("city", "Sunnyvale")
        state = addr.get("state", "CA")
        zip_code = str(addr.get("zipcode", ""))

        # Build full address string
        if street and street != "(undisclosed Address)":
            address = f"{street}, {city}, {state} {zip_code}".strip(", ")
        else:
            address = f"{city}, {state} {zip_code}".strip(", ")

        # --- Price --------------------------------------------------------
        price = self._extract_price(prop, result_type)

        # --- Bedrooms / Bathrooms -----------------------------------------
        bedrooms = prop.get("bedrooms", 0)
        bathrooms = prop.get("bathrooms", 0.0)

        # For propertyGroup, try to get from unitsGroup
        if result_type == "propertyGroup" and not bedrooms:
            units = prop.get("unitsGroup", [])
            if units:
                bedrooms = units[0].get("bedrooms", 0)

        # --- Square footage -----------------------------------------------
        sqft = prop.get("livingArea")
        if isinstance(sqft, str):
            try:
                sqft = int(sqft.replace(",", ""))
            except ValueError:
                sqft = None
        elif isinstance(sqft, float):
            sqft = int(sqft)

        # --- Property type ------------------------------------------------
        property_type = _map_property_type(prop.get("propertyType"))

        # Also check groupType for apartment complexes
        if result_type == "propertyGroup" and prop.get("groupType") == "apartmentComplex":
            property_type = "apartment"

        # --- URL ----------------------------------------------------------
        detail_url = f"https://www.zillow.com/homedetails/{zpid}_zpid/"

        # --- Images -------------------------------------------------------
        media = prop.get("media", {})
        all_photos = media.get("allPropertyPhotos", {})
        high_res = all_photos.get("highResolution", [])
        # Limit to first 10 images to save database space
        image_urls: list[str] = high_res[:10] if high_res else []

        # Fallback to main photo if no gallery
        if not image_urls:
            photo_links = media.get("propertyPhotoLinks", {})
            main_photo = photo_links.get("highResolutionLink") or photo_links.get("mediumSizeLink")
            if main_photo:
                image_urls = [main_photo]

        # --- Title --------------------------------------------------------
        title = prop.get("title", "") or address

        # --- Geolocation --------------------------------------------------
        location = prop.get("location", {})
        lat = location.get("latitude")
        lng = location.get("longitude")

        # --- Dates --------------------------------------------------------
        days_on_zillow = prop.get("daysOnZillow")
        listed_date = None
        if days_on_zillow is not None:
            try:
                listed_date = date.today() - timedelta(days=int(days_on_zillow))
            except (ValueError, TypeError):
                pass

        # --- Year built ---------------------------------------------------
        # Available on some listings but not in our model; skip for now

        # --- Pet policy ---------------------------------------------------
        pet_friendly = self._extract_pet_friendly(prop)

        # --- Parking ------------------------------------------------------
        parking = self._extract_parking(prop)

        # --- Laundry ------------------------------------------------------
        laundry = self._extract_laundry(prop)

        return {
            "external_id": zpid,
            "source": "zillow",
            "url": detail_url,
            "title": title,
            "address": address,
            "neighborhood": None,
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
    def _extract_price(prop: dict, result_type: str) -> float | None:
        """Extract the monthly rent from various locations in the response.

        The API stores price in different places depending on the listing type:
        - ``property.price.value`` — most common for individual listings
        - ``property.rental.baseRent`` — alternative location
        - ``property.minPrice`` / ``property.maxPrice`` — for property groups
        - ``property.hdpView.price`` — fallback

        Args:
            prop: The ``property`` dict from the API response.
            result_type: Either ``"property"`` or ``"propertyGroup"``.

        Returns:
            The monthly rent as a float, or None if not found.
        """
        # Try price.value first (most reliable)
        price_obj = prop.get("price", {})
        if isinstance(price_obj, dict):
            value = price_obj.get("value")
            if value and isinstance(value, (int, float)) and value > 0:
                return float(value)

        # Try rental.baseRent
        rental = prop.get("rental", {})
        base_rent = rental.get("baseRent")
        if base_rent and isinstance(base_rent, (int, float)) and base_rent > 0:
            return float(base_rent)

        # For property groups, try minPrice
        if result_type == "propertyGroup":
            min_price = prop.get("minPrice")
            if min_price and isinstance(min_price, (int, float)) and min_price > 0:
                return float(min_price)

        # Fallback: hdpView.price
        hdp = prop.get("hdpView", {})
        hdp_price = hdp.get("price")
        if hdp_price and isinstance(hdp_price, (int, float)) and hdp_price > 0:
            return float(hdp_price)

        return None

    @staticmethod
    def _extract_pet_friendly(prop: dict) -> bool | None:
        """Extract pet policy from the Zillow API response.

        The API may store pet info in several locations:
        - ``property.resoFacts.petsAllowed`` — boolean or string
        - ``property.rental.petsAllowed`` — boolean
        - ``property.petsAllowed`` — boolean
        - ``property.resoFacts.petPolicy`` — string like "Dogs OK", "Cats OK"
        - ``property.petPolicy`` — string

        Args:
            prop: The ``property`` dict from the API response.

        Returns:
            ``True`` if pets are allowed, ``False`` if not, ``None`` if unknown.
        """
        # Check multiple possible locations for pet data
        # 1. resoFacts.petsAllowed (most common in ZLLW API)
        reso_facts = prop.get("resoFacts", {})
        if isinstance(reso_facts, dict):
            pets_allowed = reso_facts.get("petsAllowed")
            if pets_allowed is not None:
                if isinstance(pets_allowed, bool):
                    return pets_allowed
                if isinstance(pets_allowed, str):
                    lower = pets_allowed.lower()
                    if lower in ("yes", "true", "allowed", "dogs ok", "cats ok", "dogs and cats ok"):
                        return True
                    if lower in ("no", "false", "not allowed", "no pets", "none"):
                        return False
                # Could be a list like ["Dogs OK", "Cats OK"]
                if isinstance(pets_allowed, list):
                    return len(pets_allowed) > 0

            # Also check petPolicy string
            pet_policy = reso_facts.get("petPolicy")
            if pet_policy and isinstance(pet_policy, str):
                lower = pet_policy.lower()
                if any(kw in lower for kw in ("dog", "cat", "pet", "allowed", "ok", "yes")):
                    return True
                if any(kw in lower for kw in ("no pet", "not allowed", "none")):
                    return False

        # 2. rental.petsAllowed
        rental = prop.get("rental", {})
        if isinstance(rental, dict):
            pets = rental.get("petsAllowed")
            if pets is not None:
                if isinstance(pets, bool):
                    return pets
                if isinstance(pets, str):
                    lower = pets.lower()
                    if lower in ("yes", "true", "allowed"):
                        return True
                    if lower in ("no", "false", "not allowed"):
                        return False

        # 3. Top-level petsAllowed
        pets_top = prop.get("petsAllowed")
        if pets_top is not None:
            if isinstance(pets_top, bool):
                return pets_top
            if isinstance(pets_top, str):
                lower = pets_top.lower()
                if lower in ("yes", "true", "allowed"):
                    return True
                if lower in ("no", "false", "not allowed"):
                    return False

        # 4. Top-level petPolicy
        pet_policy_top = prop.get("petPolicy")
        if pet_policy_top and isinstance(pet_policy_top, str):
            lower = pet_policy_top.lower()
            if any(kw in lower for kw in ("dog", "cat", "pet", "allowed", "ok", "yes")):
                return True
            if any(kw in lower for kw in ("no pet", "not allowed", "none")):
                return False

        return None

    @staticmethod
    def _extract_parking(prop: dict) -> str | None:
        """Extract parking information from the Zillow API response.

        Checks ``resoFacts.parkingFeatures``, ``resoFacts.parkingCapacity``,
        and ``resoFacts.garageSpaces``.

        Args:
            prop: The ``property`` dict from the API response.

        Returns:
            A parking description string, or ``None`` if not available.
        """
        reso_facts = prop.get("resoFacts", {})
        if not isinstance(reso_facts, dict):
            return None

        # Check parkingFeatures (list or string)
        parking_features = reso_facts.get("parkingFeatures")
        if parking_features:
            if isinstance(parking_features, list):
                return ", ".join(str(f) for f in parking_features if f)
            if isinstance(parking_features, str):
                return parking_features

        # Check garageSpaces
        garage = reso_facts.get("garageSpaces")
        if garage and isinstance(garage, (int, float)) and garage > 0:
            return f"{int(garage)}-car garage"

        # Check parkingCapacity
        capacity = reso_facts.get("parkingCapacity")
        if capacity and isinstance(capacity, (int, float)) and capacity > 0:
            return f"{int(capacity)} parking spaces"

        # Check hasGarage
        has_garage = reso_facts.get("hasGarage")
        if has_garage is True:
            return "garage"

        return None

    @staticmethod
    def _extract_laundry(prop: dict) -> str | None:
        """Extract laundry information from the Zillow API response.

        Checks ``resoFacts.laundryFeatures``.

        Args:
            prop: The ``property`` dict from the API response.

        Returns:
            A laundry description string, or ``None`` if not available.
        """
        reso_facts = prop.get("resoFacts", {})
        if not isinstance(reso_facts, dict):
            return None

        laundry = reso_facts.get("laundryFeatures")
        if laundry:
            if isinstance(laundry, list):
                features = ", ".join(str(f) for f in laundry if f).lower()
                if "in unit" in features or "in-unit" in features:
                    return "in-unit"
                if "hookup" in features:
                    return "hookups"
                if "shared" in features or "common" in features:
                    return "shared"
                return features if features else None
            if isinstance(laundry, str):
                lower = laundry.lower()
                if "in unit" in lower or "in-unit" in lower:
                    return "in-unit"
                if "hookup" in lower:
                    return "hookups"
                if "shared" in lower or "common" in lower:
                    return "shared"
                return laundry

        return None
