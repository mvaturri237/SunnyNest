"""Craigslist rental listing scraper using Playwright and BeautifulSoup.

Craigslist now renders search results dynamically via JavaScript,
so a headless browser is required to load the actual listing data.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import re
from datetime import date
from typing import Any
from urllib.parse import urlencode, urljoin

from bs4 import BeautifulSoup, Tag
from playwright.async_api import async_playwright

from src.database import log_api_call
from src.scrapers.base import BaseScraper
from src.school_districts import get_school_district
from src.utils import load_config

logger = logging.getLogger("rental_finder.scrapers.craigslist")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_BASE_URL = "https://sfbay.craigslist.org/search/pen/apa"

_DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# ---------------------------------------------------------------------------
# Property type normalization mapping
# ---------------------------------------------------------------------------

_PROPERTY_TYPE_MAP: dict[str, str] = {
    "apartment": "apartment",
    "apt": "apartment",
    "condo": "condo",
    "condominium": "condo",
    "house": "house",
    "single family": "house",
    "sfh": "house",
    "townhouse": "townhouse",
    "townhome": "townhouse",
    "th": "townhouse",
    "duplex": "duplex",
    "triplex": "triplex",
    "studio": "apartment",
    "loft": "apartment",
    "flat": "apartment",
    "room": "room",
    "cottage": "house",
    "bungalow": "house",
}


def _normalize_property_type(raw_type: str | None) -> str:
    """Normalize a Craigslist property type string to a canonical type.

    Performs a case-insensitive lookup against :data:`_PROPERTY_TYPE_MAP`.
    If the type is not recognized, the original value is returned unchanged.

    Args:
        raw_type: The raw property type string from the listing.

    Returns:
        A canonical property type string (e.g. ``"house"``, ``"apartment"``).
        Defaults to ``"house"`` when *raw_type* is ``None`` or empty.
    """
    if not raw_type:
        return "house"
    normalized = _PROPERTY_TYPE_MAP.get(raw_type.strip().lower())
    return normalized if normalized is not None else raw_type.strip().lower()


# ---------------------------------------------------------------------------
# Helper parsers
# ---------------------------------------------------------------------------


def _parse_price(text: str | None) -> float | None:
    """Extract a numeric price from strings like ``"$5,800"``."""
    if not text:
        return None
    match = re.search(r"\$?([\d,]+)", text)
    if match:
        try:
            return float(match.group(1).replace(",", ""))
        except ValueError:
            return None
    return None


def _parse_bedrooms(text: str | None) -> int | None:
    """Extract bedroom count from strings like ``"3br"``."""
    if not text:
        return None
    match = re.search(r"(\d+)\s*br", text, re.IGNORECASE)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return None
    return None


def _parse_sqft(text: str | None) -> int | None:
    """Extract square footage from strings like ``"1850ft²"`` or ``"1644ft"``."""
    if not text:
        return None
    match = re.search(r"([\d,]+)\s*ft", text, re.IGNORECASE)
    if match:
        try:
            return int(match.group(1).replace(",", ""))
        except ValueError:
            return None
    return None


def _extract_zip_code(text: str) -> str | None:
    """Pull a 5-digit ZIP code from a text string."""
    match = re.search(r"\b(\d{5})\b", text)
    return match.group(1) if match else None


def _extract_external_id(url: str) -> str:
    """Derive a stable external ID from a Craigslist listing URL.

    Craigslist URLs typically end with ``/<numeric_id>.html``.
    """
    match = re.search(r"/(\d+)\.html", url)
    return match.group(1) if match else url


# ---------------------------------------------------------------------------
# Scraper implementation
# ---------------------------------------------------------------------------


class CraigslistScraper(BaseScraper):
    """Scraper for Craigslist apartment/rental listings on the SF Bay
    Peninsula (covers Sunnyvale).

    Uses Playwright to render JavaScript-loaded search results.
    """

    def __init__(self) -> None:
        try:
            config = load_config()
        except FileNotFoundError:
            config = {}

        scraper_cfg = config.get("scraper", {})
        filters_cfg = config.get("filters", {})

        self.max_pages: int = scraper_cfg.get("max_pages", 5)
        self.delay_min: int = scraper_cfg.get("request_delay_min", 3)
        self.delay_max: int = scraper_cfg.get("request_delay_max", 8)
        self.scrape_detail_pages: bool = scraper_cfg.get(
            "scrape_detail_pages", True
        )

        # Build default query parameters from config filters.
        # NOTE: Price filters are intentionally NOT passed to the Craigslist
        # query so that all listings are scraped and stored in the database.
        # Price filtering is handled by the UI dashboard at query time,
        # allowing users to dynamically adjust the price range via the slider.
        self.query_params: dict[str, Any] = {"query": "sunnyvale"}
        if "min_bedrooms" in filters_cfg:
            self.query_params["min_bedrooms"] = filters_cfg["min_bedrooms"]

    # ----- BaseScraper interface ------------------------------------------

    async def scrape(self) -> list[dict]:
        """Launch a headless browser and scrape Craigslist search results.

        Returns:
            A list of raw listing dictionaries.
        """
        all_listings: list[dict] = []
        url: str | None = None

        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent=_DEFAULT_USER_AGENT,
                    viewport={"width": 1920, "height": 1080},
                )
                page = await context.new_page()

                url = self._build_url()

                for page_num in range(1, self.max_pages + 1):
                    logger.info(
                        "Craigslist scrape page %d: %s", page_num, url
                    )

                    try:
                        await page.goto(
                            url,
                            wait_until="networkidle",
                            timeout=30_000,
                        )
                        # Wait for JS-rendered results to appear
                        await page.wait_for_timeout(3000)
                        log_api_call("craigslist", endpoint=url, status_code=200)
                    except Exception:
                        log_api_call("craigslist", endpoint=url, status_code=None)
                        logger.warning(
                            "Timeout or navigation error on page %d — stopping.",
                            page_num,
                        )
                        break

                    html = await page.content()
                    listings, next_url = self._parse_page(html)

                    if not listings:
                        logger.info(
                            "No listings found on page %d — stopping.",
                            page_num,
                        )
                        break

                    all_listings.extend(listings)
                    logger.info(
                        "Extracted %d listings from page %d (total so far: %d)",
                        len(listings),
                        page_num,
                        len(all_listings),
                    )

                    # Check for next page
                    if not next_url:
                        logger.info("No more pages to fetch — stopping.")
                        break

                    url = next_url

                    # Random delay between pages
                    if page_num < self.max_pages:
                        delay = random.uniform(self.delay_min, self.delay_max)
                        logger.debug("Sleeping %.1f s before next page", delay)
                        await asyncio.sleep(delay)

                # --- Second pass: visit detail pages for street addresses ---
                if self.scrape_detail_pages and all_listings:
                    all_listings = await self._scrape_detail_addresses(
                        page, all_listings
                    )

                await browser.close()

        except Exception:
            log_api_call("craigslist", endpoint=url, status_code=None)
            logger.exception("Fatal error during Craigslist scrape")

        logger.info(
            "Craigslist scrape complete — %d raw listings collected.",
            len(all_listings),
        )
        return all_listings

    def normalize(self, raw: dict) -> dict:
        """Map a raw Craigslist listing dict to Listing model fields.

        Args:
            raw: A single raw listing dictionary produced by :meth:`scrape`.

        Returns:
            A dictionary whose keys correspond to Listing column names.
        """
        title = raw.get("title", "")
        price = _parse_price(raw.get("price"))
        # Fallback: try to parse price from the title itself
        if price is None:
            price = _parse_price(title)

        meta_text = raw.get("meta_text", "")
        bedrooms = _parse_bedrooms(meta_text)
        sqft = _parse_sqft(meta_text)

        # --- Parse posted date ---
        listed_date = None
        posted_date_str = raw.get("posted_date_str")
        if posted_date_str:
            try:
                month, day = (int(x) for x in posted_date_str.split("/"))
                today = date.today()
                candidate = date(today.year, month, day)
                if candidate > today:
                    candidate = date(today.year - 1, month, day)
                listed_date = candidate
            except (ValueError, TypeError):
                listed_date = None

        # NOTE: No fallback to date.today() — the orchestrator uses
        # first_seen from the DB when listed_date is None.

        # Also try parsing from title (e.g. "3BD/2BA")
        if bedrooms is None:
            bd_match = re.search(r"(\d+)\s*(?:BD|bed)", title, re.IGNORECASE)
            if bd_match:
                bedrooms = int(bd_match.group(1))

        bathrooms = 0.0
        ba_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:BA|bath)", title, re.IGNORECASE)
        if ba_match:
            bathrooms = float(ba_match.group(1))

        # --- Address resolution (prefer street address from detail page) ---
        street_address = raw.get("street_address", "").strip()
        neighborhood = raw.get("neighborhood", "")
        if street_address:
            address = street_address
        elif neighborhood:
            address = neighborhood
        else:
            address = title

        zip_code = (
            _extract_zip_code(street_address)
            or _extract_zip_code(address)
            or _extract_zip_code(title)
            or ""
        )

        # --- School district lookup from zip code ---
        school_district: str | None = None
        if zip_code:
            school_district = get_school_district(zip_code)

        # --- Property type normalization ---
        raw_property_type = raw.get("property_type")
        property_type = _normalize_property_type(raw_property_type)

        image_urls = raw.get("image_urls", [])
        image_urls_json = json.dumps(image_urls) if image_urls else None

        return {
            "external_id": raw.get("external_id", ""),
            "source": "craigslist",
            "url": raw.get("url", ""),
            "title": title,
            "address": address,
            "neighborhood": neighborhood or None,
            "city": "Sunnyvale",
            "zip_code": zip_code,
            "price": price,
            "bedrooms": bedrooms or 0,
            "bathrooms": bathrooms,
            "sqft": sqft,
            "property_type": property_type,
            "school_district": school_district,
            "image_urls": image_urls_json,
            "listed_date": listed_date,
        }

    # ----- Internal helpers -----------------------------------------------

    async def _scrape_detail_addresses(
        self,
        page: Any,
        listings: list[dict],
    ) -> list[dict]:
        """Visit each listing's detail page to extract the street address.

        Craigslist only shows the full street address on the individual
        listing page (e.g. in ``div.mapaddress``), not on search result
        pages.  This method performs a second pass over the collected
        listings, visiting each detail URL to scrape the address.

        Args:
            page: The Playwright page instance (reused from the search pass).
            listings: The raw listing dicts collected from search pages.

        Returns:
            The same *listings* list, with ``street_address`` populated
            where extraction succeeded.
        """
        total = len(listings)
        success_count = 0

        logger.info(
            "Starting detail-page scrape for %d listings to extract "
            "street addresses…",
            total,
        )

        for idx, listing in enumerate(listings, start=1):
            detail_url = listing.get("url", "")
            if not detail_url:
                continue

            try:
                await page.goto(
                    detail_url,
                    wait_until="domcontentloaded",
                    timeout=15_000,
                )

                # Try multiple selectors — Craigslist layout varies
                address_el = await page.query_selector(
                    "div.mapaddress, "
                    "div.mapAndAttrs h2, "
                    ".street-address, "
                    "span.postingtitletext small"
                )
                if address_el:
                    raw_text = (await address_el.inner_text()).strip()
                    # Clean up parentheses that Craigslist sometimes wraps
                    # around the location, e.g. "(sunnyvale)"
                    cleaned = raw_text.strip("() ")
                    if cleaned and len(cleaned) > 2:
                        listing["street_address"] = cleaned
                        success_count += 1
                        logger.debug(
                            "[%d/%d] Address found: %s",
                            idx,
                            total,
                            cleaned,
                        )

                # Random delay to avoid rate-limiting
                delay = random.uniform(1, 3)
                await asyncio.sleep(delay)

            except Exception:
                logger.debug(
                    "[%d/%d] Failed to fetch detail page: %s",
                    idx,
                    total,
                    detail_url,
                )

        logger.info(
            "Detail-page scrape complete — extracted %d/%d street addresses.",
            success_count,
            total,
        )
        return listings

    def _build_url(self) -> str:
        """Construct the initial Craigslist search URL with query params."""
        return f"{_BASE_URL}?{urlencode(self.query_params)}"

    @staticmethod
    def _parse_page(html: str) -> tuple[list[dict], str | None]:
        """Parse a Craigslist search results page rendered by Playwright.

        Returns:
            A tuple of ``(listings, next_page_url)`` where
            *next_page_url* is ``None`` when there are no more pages.
        """
        soup = BeautifulSoup(html, "html.parser")
        results: list[dict] = []

        # Craigslist JS-rendered results use div.cl-search-result[data-pid]
        rows = soup.select("div.cl-search-result[data-pid]")

        logger.debug("Found %d cl-search-result elements with data-pid", len(rows))

        for row in rows:
            try:
                listing = _extract_row_data(row)
                if listing and listing.get("external_id"):
                    results.append(listing)
            except Exception:
                logger.debug(
                    "Failed to parse a Craigslist result row", exc_info=True
                )

        # --- Pagination ---
        next_url: str | None = None
        next_link = soup.select_one(
            "a.cl-next-page, "
            'a.button.next, '
            'a[class*="next"], '
            'button.bd-button[class*="next"]'
        )
        if next_link:
            href = next_link.get("href", "")
            if href:
                next_url = urljoin(_BASE_URL, str(href))

        return results, next_url


# ---------------------------------------------------------------------------
# Row-level extraction
# ---------------------------------------------------------------------------


def _extract_row_data(row: Tag) -> dict[str, Any]:
    """Pull fields from a single Craigslist search result element.

    The JS-rendered Craigslist uses ``div.cl-search-result[data-pid]``
    with a ``gallery-card`` inner structure.

    Args:
        row: A BeautifulSoup ``Tag`` representing one search result.

    Returns:
        A raw listing dictionary.
    """
    data: dict[str, Any] = {}

    # --- External ID from data-pid attribute ---
    data["external_id"] = row.get("data-pid", "")

    # --- Title from the title attribute of the div ---
    data["title"] = row.get("title", "")

    # --- Link / URL ---
    link_tag = row.select_one(
        'a.main[href], '
        'a[href*="/apa/d/"], '
        'a.posting-title[href], '
        'a.titlestring[href]'
    )
    if link_tag:
        href = str(link_tag.get("href", ""))
        if href.startswith("/"):
            href = urljoin("https://sfbay.craigslist.org", href)
        data["url"] = href
        # Use URL-based ID as fallback
        if not data["external_id"]:
            data["external_id"] = _extract_external_id(href)
    else:
        data["url"] = ""

    # --- Title fallback from link text ---
    if not data["title"] and link_tag:
        data["title"] = link_tag.get_text(strip=True)

    # --- Price ---
    price_tag = row.select_one(
        "span.priceinfo, "
        "span.result-price, "
        "div.price, "
        ".price"
    )
    data["price"] = price_tag.get_text(strip=True) if price_tag else None

    # --- Meta text (contains bedrooms, sqft, neighborhood) ---
    # In the JS-rendered version, the meta info is in the card text
    # Extract all text from the card and look for patterns
    meta_tag = row.select_one(".meta")
    if meta_tag:
        data["meta_text"] = meta_tag.get_text(" ", strip=True)
    else:
        # Fallback: collect all text from the gallery card
        card = row.select_one(".gallery-card")
        if card:
            all_text = card.get_text(" ", strip=True)
            data["meta_text"] = all_text
        else:
            data["meta_text"] = ""

    # --- Posted date from meta text (e.g. "3/20 3br 1644ft...") ---
    meta = data.get("meta_text", "")
    date_match = re.match(r"(\d{1,2})/(\d{1,2})\b", meta)
    data["posted_date_str"] = date_match.group(0) if date_match else None

    # --- Neighborhood ---
    # In the meta text, the neighborhood is usually the last text element
    # after the sqft info. Try to extract it.
    hood_tag = row.select_one(
        "span.result-hood, "
        "span[class*='hood'], "
        ".meta .neighborhood"
    )
    if hood_tag:
        data["neighborhood"] = hood_tag.get_text(strip=True).strip("() ")
    else:
        # Try to extract neighborhood from meta text
        # Pattern: after sqft info, the remaining text is often the neighborhood
        # The meta text looks like: "3/20 3br 1644ft 2 saratoga $5,695"
        # The "2" after "ft" is the superscript ² character, not part of neighborhood
        meta = data.get("meta_text", "")
        # Look for text after "ft" + optional digit(s) + space, before "$"
        hood_match = re.search(
            r"\d+ft\s*\d*\s+([a-zA-Z][\w\s/.-]*?)(?:\s*\$|$)",
            meta,
            re.IGNORECASE,
        )
        if hood_match:
            hood = hood_match.group(1).strip()
            if hood and not hood.startswith("$") and len(hood) > 1:
                data["neighborhood"] = hood

    # --- Thumbnail images ---
    # Craigslist uses lazy-loading with data-src for off-screen gallery images,
    # so we check both src and data-src attributes.
    img_tags = row.select("img")
    image_urls = []
    for img in img_tags:
        url = img.get("src") or img.get("data-src") or ""
        if url.startswith(("http://", "https://")):
            image_urls.append(url)
    # Filter out Craigslist placeholder images (transparent empty PNGs)
    image_urls = [url for url in image_urls if "empty.png" not in url]
    data["image_urls"] = image_urls

    logger.debug(
        "Extracted CL listing: pid=%s, title=%s, price=%s",
        data.get("external_id"),
        data.get("title", "")[:50],
        data.get("price"),
    )

    return data
