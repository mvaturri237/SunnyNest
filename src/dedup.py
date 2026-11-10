"""Cross-source listing deduplication.

Detects when the same physical property appears on multiple sources
(e.g. Zillow and Craigslist) and merges them into a single canonical
listing with multiple ``ListingSource`` records.

See ``plans/deduplication.md`` for the full architecture design.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import and_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.models import Listing, ListingSource, PriceHistory

logger = logging.getLogger("rental_finder.dedup")

# ---------------------------------------------------------------------------
# Duplicate detection threshold
# ---------------------------------------------------------------------------

DEDUP_THRESHOLD = 75

# ---------------------------------------------------------------------------
# Address normalization
# ---------------------------------------------------------------------------

# Standard USPS abbreviation mappings
_STREET_TYPE_MAP: dict[str, str] = {
    "avenue": "ave", "av": "ave",
    "boulevard": "blvd", "blv": "blvd",
    "circle": "cir",
    "court": "ct",
    "drive": "dr",
    "expressway": "expy",
    "highway": "hwy",
    "lane": "ln",
    "parkway": "pkwy",
    "place": "pl",
    "road": "rd",
    "square": "sq",
    "street": "st",
    "terrace": "ter",
    "trail": "trl",
    "way": "way",
}

_DIRECTIONAL_MAP: dict[str, str] = {
    "north": "n", "south": "s", "east": "e", "west": "w",
    "northeast": "ne", "northwest": "nw",
    "southeast": "se", "southwest": "sw",
}

_UNIT_PATTERN = re.compile(
    r"\b(apt|apartment|unit|suite|ste|#)\s*\.?\s*\w+$", re.IGNORECASE
)


def normalize_address(address: str) -> str:
    """Normalize an address for deduplication matching.

    Applies USPS abbreviation mapping, directional standardization,
    unit/apt removal, whitespace collapse, and strips city/state/zip
    after the first comma.

    Args:
        address: Raw address string.

    Returns:
        A lowercase, stripped, standardized address string.
    """
    if not address:
        return ""

    # Lowercase and strip
    addr = address.lower().strip()

    # Remove trailing city/state/zip (after first comma)
    # e.g., "123 Main St, Sunnyvale, CA 94086" → "123 main st"
    parts = addr.split(",")
    addr = parts[0].strip()

    # Remove periods
    addr = addr.replace(".", "")

    # Collapse whitespace
    addr = re.sub(r"\s+", " ", addr)

    # Normalize directionals and street types
    tokens = addr.split()
    normalized_tokens = []
    for token in tokens:
        token = _DIRECTIONAL_MAP.get(token, token)
        token = _STREET_TYPE_MAP.get(token, token)
        normalized_tokens.append(token)

    addr = " ".join(normalized_tokens)

    # Remove unit/apt designators for matching
    addr = _UNIT_PATTERN.sub("", addr).strip()

    return addr


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def compute_duplicate_score(listing_a: dict[str, Any], listing_b: Listing) -> int:
    """Compute a similarity score between a new listing dict and an existing Listing.

    Scoring signals and weights:
    - Address (normalized): 40 points
    - ZIP code: 10 points
    - Price (within 5%): 15 points
    - Bedrooms: 15 points
    - Bathrooms: 10 points
    - Sqft (within 10%): 10 points

    Args:
        listing_a: Normalized listing data dictionary (the new listing).
        listing_b: Existing ``Listing`` ORM object (candidate).

    Returns:
        A score from 0–100. Score ≥ 75 indicates a likely duplicate.
    """
    score = 0

    # Address (40 points)
    addr_a = normalize_address(listing_a.get("address", ""))
    addr_b = normalize_address(listing_b.address or "")
    if addr_a and addr_b and addr_a == addr_b:
        score += 40

    # ZIP code (10 points)
    if listing_a.get("zip_code") and listing_a["zip_code"] == listing_b.zip_code:
        score += 10

    # Price (15 points) — within 5%
    price_a = listing_a.get("price", 0) or 0
    price_b = listing_b.price or 0
    if price_a > 0 and price_b > 0:
        ratio = min(price_a, price_b) / max(price_a, price_b)
        if ratio >= 0.95:
            score += 15

    # Bedrooms (15 points)
    beds_a = listing_a.get("bedrooms")
    beds_b = listing_b.bedrooms
    if beds_a is not None and beds_b is not None and beds_a == beds_b:
        score += 15

    # Bathrooms (10 points)
    baths_a = listing_a.get("bathrooms")
    baths_b = listing_b.bathrooms
    if baths_a is not None and baths_b is not None and baths_a == baths_b:
        score += 10

    # Sqft (10 points) — within 10%
    sqft_a = listing_a.get("sqft")
    sqft_b = listing_b.sqft
    if sqft_a and sqft_b and sqft_a > 0 and sqft_b > 0:
        ratio = min(sqft_a, sqft_b) / max(sqft_a, sqft_b)
        if ratio >= 0.90:
            score += 10

    return score


# ---------------------------------------------------------------------------
# Candidate selection
# ---------------------------------------------------------------------------


def find_duplicate_candidates(
    session: Session,
    zip_code: str,
    source: str,
    external_id: str,
) -> list[Listing]:
    """Find listings that could be duplicates (different source, same zip).

    Uses a narrowing strategy: filter by zip_code first to avoid O(N²)
    scoring against all listings.  Bedroom comparison is handled by the
    scoring function, not the candidate filter, so cross-source duplicates
    with different bedroom counts are still detected.

    Args:
        session: Active SQLAlchemy session.
        zip_code: ZIP code of the new listing.
        source: Source of the new listing (to exclude same-source matches).
        external_id: External ID of the new listing.

    Returns:
        A list of candidate ``Listing`` objects from different sources.
    """
    if not zip_code:
        return []

    return (
        session.query(Listing)
        .filter(
            Listing.zip_code == zip_code,
            Listing.is_active == True,  # noqa: E712
            # Exclude listings that already have a source record matching
            # the new listing's source+external_id
            ~Listing.sources.any(
                and_(
                    ListingSource.source == source,
                    ListingSource.external_id == external_id,
                )
            ),
        )
        .all()
    )


# ---------------------------------------------------------------------------
# Merge logic
# ---------------------------------------------------------------------------

# Fields to gap-fill from the duplicate into the canonical listing
_GAP_FILL_FIELDS = [
    "sqft", "sqm", "description", "pet_friendly", "parking",
    "laundry", "ac", "furnished", "neighborhood",
]


def _merge_duplicate(
    session: Session,
    canonical: Listing,
    duplicate_data: dict[str, Any],
) -> None:
    """Merge a duplicate listing's data into the canonical listing.

    Adds the duplicate's source record to the canonical listing and
    fills in any missing data fields. Never overwrites user preferences
    (``is_favorite``, ``is_disliked``).

    Args:
        session: Active SQLAlchemy session.
        canonical: The existing canonical ``Listing`` to merge into.
        duplicate_data: Normalized data dict from the duplicate listing.
    """
    # 1. Reassign the duplicate's existing ListingSource row to the canonical
    #    listing instead of inserting a new one. ``upsert_listing()`` (in
    #    ``src/database.py``) already inserted a ``ListingSource(source,
    #    external_id, listing_id=duplicate.id)`` row when the duplicate
    #    listing was first created. Inserting another row with the same
    #    ``(source, external_id)`` pair would violate the
    #    ``uq_ls_source_external_id`` unique constraint and raise
    #    ``IntegrityError`` — the bug this code path used to swallow as a
    #    "possible race condition".
    existing_source = (
        session.query(ListingSource)
        .filter_by(
            source=duplicate_data["source"],
            external_id=duplicate_data["external_id"],
        )
        .first()
    )
    if existing_source is not None:
        # Reassign the existing source row to point at the canonical listing
        existing_source.listing_id = canonical.id
        existing_source.last_seen = datetime.now(timezone.utc)
        existing_source.is_active = True
    else:
        # Defensive fallback: backfill / out-of-band insertion path where
        # no ListingSource row exists yet (e.g. records migrated before the
        # listing_sources table was introduced).
        new_source = ListingSource(
            listing_id=canonical.id,
            source=duplicate_data["source"],
            external_id=duplicate_data["external_id"],
            url=duplicate_data.get("url", ""),
            first_seen=datetime.now(timezone.utc),
            last_seen=datetime.now(timezone.utc),
            is_active=True,
        )
        session.add(new_source)
    # Make the FK reassignment visible to subsequent queries in this txn
    # (in particular the ``dup.sources`` reload in ``find_and_merge_duplicate``).
    session.flush()

    # 2. Fill NULL fields from duplicate (gap-filling)
    for field in _GAP_FILL_FIELDS:
        if getattr(canonical, field, None) is None and duplicate_data.get(field) is not None:
            setattr(canonical, field, duplicate_data[field])

    # 3. Merge image URLs (union, deduplicated, preserve order)
    existing_images: list[str] = []
    try:
        existing_images = json.loads(canonical.image_urls or "[]")
    except (json.JSONDecodeError, TypeError):
        pass

    new_images: list[str] = []
    try:
        new_images = json.loads(duplicate_data.get("image_urls", "[]") or "[]")
    except (json.JSONDecodeError, TypeError):
        pass

    if new_images:
        merged = list(dict.fromkeys(existing_images + new_images))
        canonical.image_urls = json.dumps(merged)

    # 4. Record price snapshot if price differs (inline to avoid nested session)
    dup_price = duplicate_data.get("price")
    if dup_price and dup_price != canonical.price:
        existing_snapshot = session.query(PriceHistory).filter_by(
            listing_id=canonical.id, snapshot_date=date.today()
        ).first()
        if existing_snapshot is None:
            session.add(PriceHistory(
                listing_id=canonical.id,
                snapshot_date=date.today(),
                price=dup_price,
            ))

    # 5. Update last_seen
    canonical.last_seen = datetime.now(timezone.utc)

    logger.info(
        "Merged duplicate: %s/%s → canonical listing #%d (score threshold met)",
        duplicate_data.get("source"),
        duplicate_data.get("external_id"),
        canonical.id,
    )


# ---------------------------------------------------------------------------
# Main dedup entry point
# ---------------------------------------------------------------------------


def find_and_merge_duplicate(
    session: Session,
    listing: Listing,
    listing_data: dict[str, Any],
) -> Listing | None:
    """Check if a newly inserted listing is a cross-source duplicate.

    If a duplicate is found:
    1. Merge the new listing's source into the canonical listing
    2. Transfer price_history records from the duplicate to the canonical
    3. Delete the new listing row (it was just inserted by upsert)
    4. Return the canonical listing

    If no duplicate found, return ``None``.

    Args:
        session: Active SQLAlchemy session.
        listing: The newly inserted ``Listing`` ORM object.
        listing_data: The normalized data dict used to create the listing.

    Returns:
        The canonical ``Listing`` if a duplicate was found and merged,
        or ``None`` if no duplicate was detected.
    """
    # Defensive check: verify the listing still exists (guards against
    # concurrent deletion in a separate session — P1-2 race condition fix)
    dup = session.get(Listing, listing.id)
    if dup is None:
        logger.warning(
            "Listing id=%d no longer exists (concurrent deletion?), skipping dedup",
            listing.id,
        )
        return None

    candidates = find_duplicate_candidates(
        session=session,
        zip_code=listing_data.get("zip_code", ""),
        source=listing_data["source"],
        external_id=listing_data["external_id"],
    )

    best_match: Listing | None = None
    best_score = 0

    for candidate in candidates:
        score = compute_duplicate_score(listing_data, candidate)
        if score >= DEDUP_THRESHOLD and score > best_score:
            best_match = candidate
            best_score = score

    if best_match is None:
        return None

    logger.info(
        "Duplicate detected: %s/%s matches listing #%d (score=%d)",
        listing_data.get("source"),
        listing_data.get("external_id"),
        best_match.id,
        best_score,
    )

    try:
        # Merge into canonical
        _merge_duplicate(session, best_match, listing_data)

        # Transfer price_history from duplicate to canonical (P1-1 fix)
        # Avoids losing historical price data when the duplicate is deleted
        for ph in list(dup.price_history):
            existing_ph = session.query(PriceHistory).filter_by(
                listing_id=best_match.id, snapshot_date=ph.snapshot_date
            ).first()
            if existing_ph is None:
                ph.listing_id = best_match.id
            else:
                # Keep the existing snapshot, remove the duplicate's
                session.delete(ph)

        # Delete the newly-inserted duplicate listing row.
        # After Fix A reassigned the dup's ListingSource row to the canonical
        # listing, ``dup.sources`` should be empty — but the SQLAlchemy
        # session's identity map may still hold a stale reference.  Refresh
        # to reload from the DB, then defensively delete any stragglers
        # (the FK ``listing_sources.listing_id`` has no ``ON DELETE CASCADE``,
        # so an orphan row would block ``session.delete(dup)`` with an
        # IntegrityError on commit).
        session.flush()
        session.refresh(dup)
        for src_record in list(dup.sources):
            # Should be empty after Fix A reassignment, but defensive.
            session.delete(src_record)
        session.delete(dup)

    except IntegrityError:
        # Hard failure — investigate.  The previous "possible race condition"
        # message masked a real bug for ~6 weeks (cross-source dedup never
        # actually merged anything).  Use ``logger.exception`` so the
        # traceback is in the logs and the failure is loud.
        session.rollback()
        logger.exception(
            "IntegrityError during dedup merge for %s/%s — investigate",
            listing_data.get("source"),
            listing_data.get("external_id"),
        )
        return None

    return best_match
