#!/usr/bin/env python3
"""Backfill school assignments for existing listings.

Queries all listings that have lat/lng coordinates but are missing school
assignment data, performs point-in-polygon lookups against the attendance
zone boundaries, and updates the database in batches.

Usage:
    python scripts/backfill_schools.py              # Run backfill
    python scripts/backfill_schools.py --dry-run     # Preview without writing

Requirements:
    - shapely>=2.0.0
    - GeoJSON boundary files in data/school-boundaries/
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Ensure the project root is on sys.path so we can import src.*
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from src.database import get_session, init_db  # noqa: E402
from src.models import Listing  # noqa: E402
from src.school_districts import get_assigned_schools  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("backfill_schools")

BATCH_SIZE = 50


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill school assignments for existing listings.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing to the database.",
    )
    args = parser.parse_args()

    # Ensure DB schema is up to date
    init_db()

    # Query listings that have coordinates but missing school assignments
    with get_session() as session:
        candidates = (
            session.query(Listing)
            .filter(
                Listing.latitude.isnot(None),
                Listing.longitude.isnot(None),
                Listing.is_active == True,  # noqa: E712
            )
            .filter(
                # At least one school column is NULL
                (Listing.school_elementary.is_(None))
                | (Listing.school_middle.is_(None))
                | (Listing.school_high.is_(None))
            )
            .all()
        )
        # Detach so we can use them outside the session
        listing_data = [
            {
                "id": l.id,
                "lat": l.latitude,
                "lng": l.longitude,
                "address": l.address,
                "school_elementary": l.school_elementary,
                "school_middle": l.school_middle,
                "school_high": l.school_high,
            }
            for l in candidates
        ]

    total = len(listing_data)
    logger.info("Found %d listings to backfill.", total)

    if total == 0:
        logger.info("Nothing to do — all listings already have school assignments.")
        return

    updated_count = 0
    skipped_count = 0
    error_count = 0

    # Process in batches
    for batch_start in range(0, total, BATCH_SIZE):
        batch = listing_data[batch_start : batch_start + BATCH_SIZE]
        updates: list[dict] = []

        for item in batch:
            try:
                schools = get_assigned_schools(item["lat"], item["lng"])

                # Only update columns that are currently NULL and have a new value
                changes: dict[str, str] = {}
                for level in ("elementary", "middle", "high"):
                    col_key = f"school_{level}"
                    if item[col_key] is None and schools[level] is not None:
                        changes[col_key] = schools[level]

                if changes:
                    updates.append({"id": item["id"], **changes})
                    if args.dry_run:
                        school_str = " · ".join(
                            f"{k.replace('school_', '').title()}: {v}"
                            for k, v in changes.items()
                        )
                        logger.info(
                            "[DRY RUN] #%d %s → %s",
                            item["id"],
                            item["address"],
                            school_str,
                        )
                else:
                    skipped_count += 1

            except Exception:
                error_count += 1
                logger.exception(
                    "Failed to look up schools for listing #%d (%s)",
                    item["id"],
                    item["address"],
                )

        # Write batch to database
        if updates and not args.dry_run:
            with get_session() as session:
                for upd in updates:
                    listing = session.get(Listing, upd["id"])
                    if listing is not None:
                        for key, value in upd.items():
                            if key != "id":
                                setattr(listing, key, value)
                        updated_count += 1

            logger.info(
                "Batch %d–%d: updated %d listings.",
                batch_start + 1,
                min(batch_start + BATCH_SIZE, total),
                len(updates),
            )
        elif updates and args.dry_run:
            updated_count += len(updates)

    # Summary
    logger.info("=" * 50)
    logger.info("Backfill complete%s.", " (DRY RUN)" if args.dry_run else "")
    logger.info("  Total candidates: %d", total)
    logger.info("  Updated:          %d", updated_count)
    logger.info("  Skipped (no match): %d", skipped_count)
    logger.info("  Errors:           %d", error_count)


if __name__ == "__main__":
    main()
