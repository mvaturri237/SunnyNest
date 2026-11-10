"""Scraper orchestrator — coordinates scrapers, enriches data, and triggers notifications.

The orchestrator is the central coordination layer that:
1. Runs all scrapers concurrently
2. Normalizes and enriches each listing (geocoding, school district, sqm)
3. Upserts listings into the database
4. Marks stale listings as inactive
5. Triggers email notifications for new listings matching filters
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import date
from typing import Any

from src.database import get_session, init_db, mark_inactive, record_price_snapshots_batch, upsert_listing
from src.dedup import find_and_merge_duplicate
from src.models import Listing
from src.geocoder import geocode_address
from src.school_districts import get_assigned_schools, get_school_district
from src.scrapers.craigslist_scraper import CraigslistScraper
from src.scrapers.realtor_scraper import RealtorScraper
from src.scrapers.zillow_scraper import ZillowScraper
from src.utils import load_config, sqft_to_sqm

logger = logging.getLogger("rental_finder.orchestrator")


class ScraperOrchestrator:
    """Coordinates all scrapers, enriches data, and manages the scrape lifecycle."""

    def __init__(self) -> None:
        self._scrapers = [
            ("zillow", ZillowScraper()),
            ("craigslist", CraigslistScraper()),
            ("realtor", RealtorScraper()),
        ]

    async def run_sync(self) -> dict[str, Any]:
        """Run all scrapers concurrently, enrich and persist results.

        Returns:
            A summary dictionary with keys:
            - ``total_scraped``: total raw listings collected across all sources
            - ``new_listings``: count of newly inserted listings
            - ``updated_listings``: count of existing listings that were updated
            - ``errors``: count of processing errors
        """
        # --- Load config ---
        try:
            config = load_config()
        except FileNotFoundError:
            logger.warning("config.yaml not found — using empty config.")
            config = {}

        # --- Ensure database tables exist ---
        init_db()

        # --- Run all scrapers concurrently ---
        t_scrape_start = time.perf_counter()
        scrape_tasks = []
        for source_name, scraper in self._scrapers:
            scrape_tasks.append(self._safe_scrape(source_name, scraper))

        scrape_results: list[tuple[str, list[dict]]] = await asyncio.gather(*scrape_tasks)
        t_scrape_end = time.perf_counter()
        logger.info("⏱ Scraping phase took %.2f s", t_scrape_end - t_scrape_start)

        # --- Process results ---
        t_process_start = time.perf_counter()
        total_scraped = 0
        new_count = 0
        updated_count = 0
        error_count = 0
        all_new_listings: list[dict[str, Any]] = []
        # Collect price snapshots for batch recording
        price_snapshots: list[tuple[int, float]] = []

        for source_name, raw_listings in scrape_results:
            # Find the matching scraper instance
            scraper = next(s for name, s in self._scrapers if name == source_name)

            seen_external_ids: list[str] = []
            # Per-source counter of items filtered by normalize() returning None
            # (e.g. Zillow status validation — Bug A, 2026-06-04). Logged after
            # the per-source loop completes so we can verify the filter is
            # working without spamming per-item logs.
            normalize_filtered = 0
            logger.info(
                "Processing %d raw listings from %s …",
                len(raw_listings),
                source_name,
            )
            total_scraped += len(raw_listings)

            for raw in raw_listings:
                try:
                    # 1. Normalize (may return None to signal "skip this item",
                    #    e.g. Zillow Bug A status guard rejects for-sale rows)
                    normalized = scraper.normalize(raw)
                    if normalized is None:
                        normalize_filtered += 1
                        continue

                    # 1b. Filter out $0 / None price listings (bad data)
                    norm_price = normalized.get("price")
                    if norm_price is None or norm_price == 0 or norm_price == 0.0:
                        logger.warning(
                            "Skipping listing with invalid price (%s) from %s: %s",
                            norm_price,
                            source_name,
                            normalized.get("external_id", "unknown"),
                        )
                        continue

                    # 1c. Filter out non-house property types
                    norm_property_type = normalized.get("property_type", "").lower()
                    if norm_property_type and norm_property_type != "house":
                        logger.debug(
                            "Skipping non-house listing (type=%s) from %s: %s",
                            norm_property_type,
                            source_name,
                            normalized.get("external_id", "unknown"),
                        )
                        continue

                    # 2. Enrich with geocoding
                    address = normalized.get("address", "")
                    city = normalized.get("city", "Sunnyvale")
                    if address:
                        coords = geocode_address(address, city=city)
                        if coords is not None:
                            normalized["latitude"] = coords[0]
                            normalized["longitude"] = coords[1]

                    # 3. Enrich with school district
                    zip_code = normalized.get("zip_code", "")
                    if zip_code:
                        district = get_school_district(zip_code)
                        if district is not None:
                            normalized["school_district"] = district

                    # 3b. Enrich with specific school assignments
                    lat = normalized.get("latitude")
                    lng = normalized.get("longitude")
                    if lat is not None and lng is not None:
                        try:
                            schools = get_assigned_schools(lat, lng)
                            for level in ("elementary", "middle", "high"):
                                if schools[level]:
                                    normalized[f"school_{level}"] = schools[level]
                        except Exception:
                            logger.exception(
                                "School assignment lookup failed for %s",
                                address,
                            )

                    # 4. Auto-calculate sqm from sqft
                    sqft = normalized.get("sqft")
                    if sqft is not None:
                        normalized["sqm"] = sqft_to_sqm(sqft)

                    # 5. Upsert into database
                    listing, is_new = upsert_listing(normalized)

                    # 5b. Compute days_on_market from the DB record
                    # (first_seen is only set inside upsert_listing at insert time,
                    # so we must compute this AFTER the upsert)
                    if listing.listed_date is not None:
                        dom = (date.today() - listing.listed_date).days
                    elif listing.first_seen is not None:
                        dom = (date.today() - listing.first_seen.date()).days
                    else:
                        dom = None

                    if dom != listing.days_on_market:
                        with get_session() as dom_session:
                            dom_listing = dom_session.get(Listing, listing.id)
                            if dom_listing is not None:
                                dom_listing.days_on_market = dom
                        listing.days_on_market = dom

                    # 6. Collect price snapshot for batch recording
                    if listing.price is not None:
                        price_snapshots.append((listing.id, listing.price))

                    if is_new:
                        # Step 6: Cross-source dedup check for new listings
                        try:
                            with get_session() as dedup_session:
                                canonical = find_and_merge_duplicate(
                                    session=dedup_session,
                                    listing=listing,
                                    listing_data=normalized,
                                )
                            if canonical is not None:
                                # This listing was merged into an existing one
                                # Don't count as "new" for notification purposes
                                updated_count += 1
                                # Use the canonical listing for price snapshot
                                listing = canonical
                            else:
                                new_count += 1
                                # Store the normalized dict (with enrichments) for notifications
                                all_new_listings.append(normalized)
                        except Exception:
                            logger.exception(
                                "Dedup check failed for %s/%s — treating as new listing.",
                                source_name,
                                normalized.get("external_id", "unknown"),
                            )
                            new_count += 1
                            all_new_listings.append(normalized)
                    else:
                        updated_count += 1

                    # Track seen external IDs for inactive marking
                    external_id = normalized.get("external_id", "")
                    if external_id:
                        seen_external_ids.append(external_id)

                except Exception:
                    error_count += 1
                    logger.exception(
                        "Error processing listing from %s: %s",
                        source_name,
                        raw.get("external_id", "unknown"),
                    )

            # Log the normalize() skip-counter once per source (debug level —
            # turn on logging.DEBUG to see the Bug A status-filter throughput).
            if normalize_filtered:
                logger.debug(
                    "Source=%s: normalize() filtered %d / %d raw items "
                    "(status/shape validation)",
                    source_name,
                    normalize_filtered,
                    len(raw_listings),
                )

            # 7. Mark listings not seen in this scrape as inactive (with safety threshold)
            if seen_external_ids:
                try:
                    # P2-8: Safety check — only mark inactive if we saw at least
                    # 30% of active listings (guards against partial scrape failures)
                    with get_session() as _session:
                        active_count = (
                            _session.query(Listing)
                            .filter(
                                Listing.source == source_name,
                                Listing.is_active == True,  # noqa: E712
                            )
                            .count()
                        )
                    threshold = max(2, int(active_count * 0.3))
                    if len(seen_external_ids) >= threshold:
                        mark_inactive(source_name, seen_external_ids)
                    else:
                        logger.warning(
                            "Skipping mark_inactive for source=%s: only saw %d IDs "
                            "(threshold=%d, active=%d). Possible partial scrape failure.",
                            source_name,
                            len(seen_external_ids),
                            threshold,
                            active_count,
                        )
                except Exception:
                    logger.exception(
                        "Error marking inactive listings for source=%s",
                        source_name,
                    )

        # 8. Batch record all price snapshots in a single transaction
        if price_snapshots:
            try:
                record_price_snapshots_batch(price_snapshots)
            except Exception:
                logger.exception("Failed to batch record %d price snapshots.", len(price_snapshots))

        t_process_end = time.perf_counter()
        logger.info("⏱ Processing phase took %.2f s", t_process_end - t_process_start)
        logger.info(
            "⏱ Total sync time: %.2f s (scrape=%.2f s, process=%.2f s)",
            t_process_end - t_scrape_start,
            t_scrape_end - t_scrape_start,
            t_process_end - t_process_start,
        )

        # --- Trigger email notification for new listings ---
        # REMOVED: Notifications are now handled by the scheduled NotificationService.
        # Legacy _notify_new_listings() did not mark listings as notified=True,
        # causing duplicate sends when the scheduled service ran afterwards.

        summary = {
            "total_scraped": total_scraped,
            "new_listings": new_count,
            "updated_listings": updated_count,
            "errors": error_count,
        }
        logger.info("Scrape run complete: %s", summary)
        return summary

    def run_sync_blocking(self) -> dict[str, Any]:
        """Synchronous wrapper around :meth:`run_sync`.

        Uses :func:`asyncio.run` to execute the async orchestration.
        This is the entry point for the scheduler and dashboard.

        Returns:
            The same summary dictionary as :meth:`run_sync`.
        """
        return asyncio.run(self.run_sync())

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    async def _safe_scrape(
        source_name: str,
        scraper: Any,
    ) -> tuple[str, list[dict]]:
        """Run a single scraper with error isolation.

        If the scraper raises an exception, an empty list is returned so
        that other scrapers are not affected.

        Args:
            source_name: Human-readable source identifier.
            scraper: A :class:`~src.scrapers.base.BaseScraper` instance.

        Returns:
            A tuple of ``(source_name, raw_listings)``.
        """
        try:
            logger.info("Starting scrape for %s …", source_name)
            raw_listings = await scraper.scrape()
            logger.info(
                "Scrape for %s returned %d raw listings.",
                source_name,
                len(raw_listings),
            )
            return source_name, raw_listings
        except Exception:
            logger.exception("Scraper %s failed — skipping.", source_name)
            return source_name, []

