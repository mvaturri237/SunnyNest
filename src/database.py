"""Database connection, session management, and query helpers."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from statistics import median
from typing import Any, Generator

from sqlalchemy import Integer as SAInteger, and_, case, create_engine, func, text
from sqlalchemy.orm import Session, selectinload, sessionmaker

from src.models import ApiCallLog, Base, Listing, ListingSource, NotificationLog, PriceHistory
from src.utils import load_config

logger = logging.getLogger("rental_finder.database")

# Maximum number of days to gap-fill in price history.
# Prevents inserting thousands of rows if the scraper hasn't run for a long time.
MAX_GAP_DAYS = 30

# ---------------------------------------------------------------------------
# Engine & session factory
# ---------------------------------------------------------------------------

_engine = None
_SessionFactory: sessionmaker[Session] | None = None


def _get_db_path() -> str:
    """Resolve the SQLite database path from config or use the default."""
    try:
        config = load_config()
        db_path = config.get("database", {}).get("path", "data/listings.db")
    except FileNotFoundError:
        db_path = "data/listings.db"
    return db_path


def get_engine():
    """Return the global SQLAlchemy engine, creating it on first call."""
    global _engine
    if _engine is None:
        db_path = _get_db_path()
        # Ensure the parent directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(
            f"sqlite:///{db_path}",
            echo=False,
            connect_args={"check_same_thread": False},
        )
        logger.info("Database engine created: %s", db_path)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """Return the global session factory, creating it on first call."""
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(bind=get_engine())
    return _SessionFactory


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def _ensure_days_on_market_column() -> None:
    """Add the ``days_on_market`` column to the listings table if it doesn't exist.

    Uses raw SQL ``ALTER TABLE`` so the migration is non-destructive — existing
    data is preserved.  The try/except silently handles the case where the
    column already exists (SQLite raises ``OperationalError: duplicate column``).
    """
    engine = get_engine()
    try:
        with engine.connect() as conn:
            conn.execute(
                text("ALTER TABLE listings ADD COLUMN days_on_market INTEGER")
            )
            conn.commit()
        logger.info("Added days_on_market column to listings table.")
    except Exception:
        # Column already exists — nothing to do.
        pass


def _migrate_to_listing_sources() -> None:
    """Backfill ``listing_sources`` from existing ``listings.source/external_id/url``.

    Non-destructive, idempotent migration using ``INSERT OR IGNORE`` to
    safely handle re-runs without duplicating rows.  The unique constraint
    on ``(source, external_id)`` prevents duplicate entries.
    """
    engine = get_engine()
    try:
        with engine.connect() as conn:
            conn.execute(text("""
                INSERT OR IGNORE INTO listing_sources
                    (listing_id, source, external_id, url, first_seen, last_seen, is_active)
                SELECT id, source, external_id, url, first_seen, last_seen, is_active
                FROM listings
                WHERE source IS NOT NULL AND external_id IS NOT NULL
            """))
            conn.commit()
        logger.info("Backfill listing_sources migration completed (INSERT OR IGNORE).")
    except Exception:
        # Table may not exist yet on first run — create_all handles it
        logger.debug("listing_sources migration skipped (table may not exist yet).")


def _ensure_school_columns() -> None:
    """Add school_elementary, school_middle, school_high columns if missing.

    Uses raw SQL ``ALTER TABLE`` so the migration is non-destructive.
    The try/except silently handles the case where the column already exists.
    """
    engine = get_engine()
    for col in ("school_elementary", "school_middle", "school_high"):
        try:
            with engine.connect() as conn:
                conn.execute(text(f"ALTER TABLE listings ADD COLUMN {col} TEXT"))
                conn.commit()
            logger.info("Added %s column to listings table.", col)
        except Exception:
            pass  # Column already exists


def _ensure_deactivated_at_column() -> None:
    """Add the ``deactivated_at`` column to the listings table if missing."""
    engine = get_engine()
    try:
        with engine.connect() as conn:
            conn.execute(
                text("ALTER TABLE listings ADD COLUMN deactivated_at DATETIME")
            )
            conn.commit()
        logger.info("Added deactivated_at column to listings table.")
    except Exception:
        pass  # Column already exists


def _ensure_notification_error_columns() -> None:
    """Add ``error_category`` and ``error_message`` columns to ``notification_log``.

    Non-destructive ``ALTER TABLE ADD COLUMN`` migration.  Both columns
    are nullable so existing rows keep their NULL defaults.
    """
    engine = get_engine()
    for col, ddl in (
        ("error_category", "ALTER TABLE notification_log ADD COLUMN error_category TEXT"),
        ("error_message", "ALTER TABLE notification_log ADD COLUMN error_message TEXT"),
    ):
        try:
            with engine.connect() as conn:
                conn.execute(text(ddl))
                conn.commit()
            logger.info("Added %s column to notification_log table.", col)
        except Exception:
            pass  # Column already exists


def _ensure_consecutive_misses_column() -> None:
    """Add the ``consecutive_misses`` column to ``listings`` (Bug B, 2026-06-04).

    Non-destructive ``ALTER TABLE ADD COLUMN`` with ``DEFAULT 0`` so all
    pre-existing rows start the hysteresis counter at zero (which means
    "seen this scrape" — equivalent to the previous always-on behavior
    until the first scrape that doesn't return them).

    See ``mark_inactive()`` for the consumer logic and
    ``MARK_INACTIVE_MISS_THRESHOLD`` for the cutoff.
    """
    engine = get_engine()
    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    "ALTER TABLE listings ADD COLUMN consecutive_misses "
                    "INTEGER NOT NULL DEFAULT 0"
                )
            )
            conn.commit()
        logger.info("Added consecutive_misses column to listings table.")
    except Exception:
        pass  # Column already exists


def init_db() -> None:
    """Create all tables defined in the ORM metadata.

    Safe to call multiple times — existing tables are not recreated.
    Also runs idempotent migrations for schema evolution.
    """
    engine = get_engine()
    Base.metadata.create_all(engine)
    _ensure_days_on_market_column()
    _migrate_to_listing_sources()
    _ensure_school_columns()
    _ensure_deactivated_at_column()
    _ensure_notification_error_columns()
    _ensure_consecutive_misses_column()
    logger.info("Database tables initialised.")


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Provide a transactional database session via a context manager.

    Usage::

        with get_session() as session:
            session.query(Listing).all()

    The session is automatically committed on success and rolled back on
    exception.
    """
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------


def _apply_listing_filters(query, filters: dict[str, Any]):
    """Apply common listing filter criteria to a SQLAlchemy query.

    This is a private helper used by :func:`get_filtered_listings`,
    :func:`get_source_counts`, and :func:`get_unnotified_listings` to
    avoid duplicating filter logic.

    Supported filter keys (all optional):

    - ``min_price`` / ``max_price`` — price range
    - ``min_bedrooms`` / ``max_bedrooms`` — bedroom count range
    - ``min_bathrooms`` / ``max_bathrooms`` — bathroom count range
    - ``property_type`` — single value or list of property types
    - ``source`` — ``"zillow"`` or ``"craigslist"``
    - ``min_sqft`` / ``max_sqft`` — square-footage range
    - ``pet_friendly`` — boolean
    - ``parking`` — string or list of parking types
    - ``laundry`` — string or list of laundry types
    - ``ac`` — boolean
    - ``furnished`` — boolean
    - ``school_district`` — string
    - ``neighborhood`` — string
    - ``is_favorite`` — boolean
    - ``exclude_disliked`` — boolean
    - ``max_days_listed`` — int, max days on market

    Note: ``is_active`` and ``source`` are intentionally **not** applied
    here because callers handle them differently (e.g.
    :func:`get_source_counts` skips ``source``).

    Args:
        query: An existing SQLAlchemy query to augment.
        filters: Dictionary of filter criteria.

    Returns:
        The augmented query with filter conditions applied.
    """
    # --- Price ---
    if "min_price" in filters:
        query = query.filter(Listing.price >= filters["min_price"])
    if "max_price" in filters:
        query = query.filter(Listing.price <= filters["max_price"])

    # --- Bedrooms ---
    if "min_bedrooms" in filters:
        query = query.filter(Listing.bedrooms >= filters["min_bedrooms"])
    if "max_bedrooms" in filters:
        query = query.filter(Listing.bedrooms <= filters["max_bedrooms"])

    # --- Bathrooms ---
    if "min_bathrooms" in filters:
        query = query.filter(Listing.bathrooms >= filters["min_bathrooms"])
    if "max_bathrooms" in filters:
        query = query.filter(Listing.bathrooms <= filters["max_bathrooms"])

    # --- Property type ---
    if "property_type" in filters:
        pt = filters["property_type"]
        if isinstance(pt, list):
            query = query.filter(Listing.property_type.in_(pt))
        else:
            query = query.filter(Listing.property_type == pt)

    # --- Square footage ---
    if "min_sqft" in filters:
        query = query.filter(Listing.sqft >= filters["min_sqft"])
    if "max_sqft" in filters:
        query = query.filter(Listing.sqft <= filters["max_sqft"])

    # --- Boolean amenities ---
    if "pet_friendly" in filters:
        query = query.filter(Listing.pet_friendly == filters["pet_friendly"])
    if "ac" in filters:
        query = query.filter(Listing.ac == filters["ac"])
    if "furnished" in filters:
        query = query.filter(Listing.furnished == filters["furnished"])

    # --- Text amenities ---
    if "parking" in filters:
        pk = filters["parking"]
        if isinstance(pk, list):
            query = query.filter(Listing.parking.in_(pk))
        else:
            query = query.filter(Listing.parking == pk)

    if "laundry" in filters:
        la = filters["laundry"]
        if isinstance(la, list):
            query = query.filter(Listing.laundry.in_(la))
        else:
            query = query.filter(Listing.laundry == la)

    # --- Location / classification ---
    if "school_district" in filters:
        query = query.filter(
            Listing.school_district == filters["school_district"]
        )
    if "neighborhood" in filters:
        query = query.filter(Listing.neighborhood == filters["neighborhood"])

    # --- User preferences ---
    if "is_favorite" in filters:
        query = query.filter(Listing.is_favorite == filters["is_favorite"])
    if filters.get("exclude_disliked"):
        query = query.filter(Listing.is_disliked == False)  # noqa: E712

    # --- Days on market ---
    if "max_days_listed" in filters:
        query = query.filter(
            Listing.days_on_market.isnot(None),
            Listing.days_on_market <= filters["max_days_listed"],
        )

    return query


def get_filtered_listings(filters: dict[str, Any]) -> list[Listing]:
    """Return listings matching the supplied filter criteria.

    Supported filter keys (all optional):

    - ``min_price`` / ``max_price`` — price range
    - ``min_bedrooms`` / ``max_bedrooms`` — bedroom count range
    - ``min_bathrooms`` / ``max_bathrooms`` — bathroom count range
    - ``property_type`` — single value or list of property types
    - ``source`` — single string or list of source names (e.g. ``["zillow", "craigslist"]``)
    - ``min_sqft`` / ``max_sqft`` — square-footage range
    - ``pet_friendly`` — boolean
    - ``parking`` — string or list of parking types
    - ``laundry`` — string or list of laundry types
    - ``ac`` — boolean
    - ``furnished`` — boolean
    - ``school_district`` — string
    - ``neighborhood`` — string
    - ``is_active`` — boolean (defaults to ``True``)

    Args:
        filters: Dictionary of filter criteria.

    Returns:
        A list of :class:`~src.models.Listing` instances.
    """
    with get_session() as session:
        query = session.query(Listing).options(selectinload(Listing.sources))

        # Apply shared filter logic
        query = _apply_listing_filters(query, filters)

        # --- Source (query via ListingSource join for multi-source support) ---
        if "source" in filters:
            source_val = filters["source"]
            if isinstance(source_val, list):
                query = query.filter(
                    Listing.sources.any(ListingSource.source.in_(source_val))
                )
            else:
                query = query.filter(
                    Listing.sources.any(ListingSource.source == source_val)
                )

        # --- Active flag (default True) ---
        is_active = filters.get("is_active", True)
        query = query.filter(Listing.is_active == is_active)

        # Order by most recently seen first
        query = query.order_by(Listing.last_seen.desc())

        listings = query.all()
        # Detach from session so callers can use objects after session closes
        session.expunge_all()
        return listings


def upsert_listing(listing_data: dict[str, Any]) -> tuple[Listing, bool]:
    """Insert a new listing or update an existing one.

    Matching is performed on the ``(source, external_id)`` unique
    constraint.  Also checks the ``listing_sources`` table for previously
    merged listings to avoid re-inserting duplicates that were already
    merged into a canonical listing.

    Args:
        listing_data: Dictionary whose keys correspond to
            :class:`~src.models.Listing` column names.

    Returns:
        A tuple of ``(listing, is_new)`` where *is_new* is ``True`` when
        the listing was freshly inserted.
    """
    with get_session() as session:
        # First check legacy listings table
        existing: Listing | None = (
            session.query(Listing)
            .filter_by(
                source=listing_data["source"],
                external_id=listing_data["external_id"],
            )
            .first()
        )

        if existing is not None:
            # Update mutable fields (exclude user-managed flags that scrapers must not overwrite,
            # plus consecutive_misses which is owned exclusively by mark_inactive — Bug B)
            for key, value in listing_data.items():
                if key not in ("id", "first_seen", "listed_date", "notified", "is_favorite", "is_disliked", "deactivated_at", "consecutive_misses") and hasattr(existing, key):
                    setattr(existing, key, value)

            # Protect listed_date: never overwrite with a later date.
            # Renewed/reposted listings on Craigslist update the date in
            # search results, but we want to keep the earliest known date.
            new_listed = listing_data.get("listed_date")
            old_listed = existing.listed_date
            if old_listed is None:
                existing.listed_date = new_listed
            elif new_listed is not None:
                existing.listed_date = min(old_listed, new_listed)
            # else: new is None, keep old — no change needed
            existing.last_seen = datetime.now(timezone.utc)
            existing.is_active = True
            existing.deactivated_at = None  # Clear stale deactivation timestamp

            # Update the corresponding ListingSource.last_seen
            source_record = (
                session.query(ListingSource)
                .filter_by(
                    source=listing_data["source"],
                    external_id=listing_data["external_id"],
                )
                .first()
            )
            if source_record is not None:
                source_record.last_seen = datetime.now(timezone.utc)
                source_record.is_active = True

            session.flush()
            session.expunge(existing)
            return existing, False

        # Check listing_sources table for previously merged listings (P2-1 fix)
        # After a merge, the duplicate listing row is deleted but its
        # ListingSource record is transferred to the canonical listing.
        # Without this check, the same external_id would be re-inserted
        # as a new listing on every scrape, triggering another dedup cycle.
        existing_source = (
            session.query(ListingSource)
            .filter_by(
                source=listing_data["source"],
                external_id=listing_data["external_id"],
            )
            .first()
        )

        if existing_source is not None:
            # This listing was previously merged — update the canonical listing
            canonical = session.get(Listing, existing_source.listing_id)
            if canonical is not None:
                # Update last_seen on the source record
                existing_source.last_seen = datetime.now(timezone.utc)
                existing_source.is_active = True
                # Update mutable fields on canonical listing (gap-fill only;
                # exclude user-managed flags that scrapers must not overwrite,
                # plus consecutive_misses owned by mark_inactive — Bug B)
                for key, value in listing_data.items():
                    if key not in ("id", "first_seen", "source", "external_id", "url", "listed_date", "notified", "is_favorite", "is_disliked", "deactivated_at", "consecutive_misses") and hasattr(canonical, key):
                        if getattr(canonical, key) is None and value is not None:
                            setattr(canonical, key, value)

                # Protect listed_date with min-date logic (same as primary path)
                new_listed = listing_data.get("listed_date")
                old_listed = canonical.listed_date
                if old_listed is None:
                    canonical.listed_date = new_listed
                elif new_listed is not None:
                    canonical.listed_date = min(old_listed, new_listed)
                canonical.last_seen = datetime.now(timezone.utc)
                canonical.is_active = True
                canonical.deactivated_at = None  # Clear stale deactivation timestamp
                session.flush()
                session.expunge(canonical)
                return canonical, False

        # New listing
        listing = Listing(**listing_data)
        listing.first_seen = datetime.now(timezone.utc)
        listing.last_seen = datetime.now(timezone.utc)
        listing.is_active = True
        listing.notified = False
        session.add(listing)
        session.flush()

        # Create a ListingSource record for the new listing
        new_source = ListingSource(
            listing_id=listing.id,
            source=listing_data["source"],
            external_id=listing_data["external_id"],
            url=listing_data.get("url", ""),
            first_seen=listing.first_seen,
            last_seen=listing.last_seen,
            is_active=True,
        )
        session.add(new_source)
        session.flush()

        session.expunge(listing)
        return listing, True


def record_price_snapshot(listing_id: int, price: float, snapshot_date: date | None = None) -> None:
    """Record a daily price snapshot for a listing.

    If a snapshot already exists for the given listing and date, the price
    is updated. Otherwise a new row is inserted.

    Args:
        listing_id: Primary key of the listing.
        price: The listing price to record.
        snapshot_date: The date for this snapshot. Defaults to today.
    """
    if snapshot_date is None:
        snapshot_date = date.today()

    with get_session() as session:
        existing = (
            session.query(PriceHistory)
            .filter_by(listing_id=listing_id, snapshot_date=snapshot_date)
            .first()
        )
        if existing is not None:
            existing.price = price
        else:
            snapshot = PriceHistory(
                listing_id=listing_id,
                snapshot_date=snapshot_date,
                price=price,
            )
            session.add(snapshot)


def record_price_snapshots_batch(snapshots: list[tuple[int, float]], snapshot_date: date | None = None) -> None:
    """Record daily price snapshots for multiple listings in a single transaction.

    Much more efficient than calling :func:`record_price_snapshot` in a loop,
    as it uses a single database session for all operations.

    Gap-filling: if the most recent existing snapshot for a listing is more
    than 1 day before *snapshot_date*, intermediate rows are inserted using
    the previous snapshot's price (carry-forward) to ensure continuous daily
    price data even when the scraper doesn't run every day.

    Args:
        snapshots: List of ``(listing_id, price)`` tuples.
        snapshot_date: The date for all snapshots. Defaults to today.
    """
    if not snapshots:
        return

    if snapshot_date is None:
        snapshot_date = date.today()

    with get_session() as session:
        listing_ids = [lid for lid, _ in snapshots]

        # --- Gap-filling: find the most recent snapshot per listing ---
        # Sub-query: most recent snapshot before today for each listing
        latest_subq = (
            session.query(
                PriceHistory.listing_id,
                func.max(PriceHistory.snapshot_date).label("max_date"),
            )
            .filter(
                PriceHistory.listing_id.in_(listing_ids),
                PriceHistory.snapshot_date < snapshot_date,
            )
            .group_by(PriceHistory.listing_id)
            .subquery()
        )

        latest_rows = (
            session.query(PriceHistory)
            .join(
                latest_subq,
                and_(
                    PriceHistory.listing_id == latest_subq.c.listing_id,
                    PriceHistory.snapshot_date == latest_subq.c.max_date,
                ),
            )
            .all()
        )
        latest_map: dict[int, tuple[date, float]] = {
            row.listing_id: (row.snapshot_date, row.price) for row in latest_rows
        }

        # Also load existing snapshots for today to avoid duplicates
        existing_today_rows = (
            session.query(PriceHistory)
            .filter(
                PriceHistory.listing_id.in_(listing_ids),
                PriceHistory.snapshot_date == snapshot_date,
            )
            .all()
        )
        existing_today_map = {row.listing_id: row for row in existing_today_rows}

        # Collect all dates that already have snapshots (for gap-fill dedup)
        # We query once for all listings in the gap range
        gap_fill_count = 0

        for listing_id, price in snapshots:
            # --- Fill gaps with carry-forward price ---
            if listing_id in latest_map:
                last_date, last_price = latest_map[listing_id]
                gap_days = (snapshot_date - last_date).days
                if gap_days > 1:
                    # Cap gap-filling to MAX_GAP_DAYS to avoid inserting
                    # thousands of rows after a long scraper outage.
                    fill_start = last_date
                    if gap_days > MAX_GAP_DAYS:
                        logger.warning(
                            "Gap of %d days for listing %d exceeds MAX_GAP_DAYS=%d; "
                            "only filling the last %d days.",
                            gap_days, listing_id, MAX_GAP_DAYS, MAX_GAP_DAYS,
                        )
                        fill_start = snapshot_date - timedelta(days=MAX_GAP_DAYS)
                        gap_days = MAX_GAP_DAYS

                    # Query existing snapshots in the gap range to avoid
                    # violating the unique constraint
                    existing_gap = set(
                        row.snapshot_date
                        for row in session.query(PriceHistory.snapshot_date)
                        .filter(
                            PriceHistory.listing_id == listing_id,
                            PriceHistory.snapshot_date > fill_start,
                            PriceHistory.snapshot_date < snapshot_date,
                        )
                        .all()
                    )
                    for offset in range(1, gap_days):
                        fill_date = fill_start + timedelta(days=offset)
                        if fill_date not in existing_gap:
                            session.add(PriceHistory(
                                listing_id=listing_id,
                                snapshot_date=fill_date,
                                price=last_price,
                            ))
                            gap_fill_count += 1

            # --- Insert/update today's snapshot ---
            if listing_id in existing_today_map:
                existing_today_map[listing_id].price = price
            else:
                session.add(PriceHistory(
                    listing_id=listing_id,
                    snapshot_date=snapshot_date,
                    price=price,
                ))

        # Log inside the session block so the message only prints if the
        # transaction actually commits (not on rollback).
        if gap_fill_count:
            logger.info("Gap-filled %d missing price history days.", gap_fill_count)
        logger.info("Batch recorded %d price snapshots for %s.", len(snapshots), snapshot_date)


def get_price_history(listing_id: int) -> list[PriceHistory]:
    """Return all price snapshots for a listing, ordered by date ascending.

    Args:
        listing_id: Primary key of the listing.

    Returns:
        A list of :class:`~src.models.PriceHistory` instances.
    """
    with get_session() as session:
        snapshots = (
            session.query(PriceHistory)
            .filter_by(listing_id=listing_id)
            .order_by(PriceHistory.snapshot_date.asc())
            .all()
        )
        session.expunge_all()
        return snapshots


def get_batch_price_changes(listing_ids: list[int]) -> dict[int, dict]:
    """Return price change info for multiple listings in a single query.

    For each listing, computes:
    - ``first_price``: the earliest recorded price
    - ``current_price``: the most recent recorded price
    - ``price_change``: current_price - first_price (positive = went up)

    Args:
        listing_ids: List of listing primary keys.

    Returns:
        A dict mapping listing_id to a dict with keys
        ``first_price``, ``current_price``, ``price_change``.
        Listings with no price history are omitted.
    """
    if not listing_ids:
        return {}

    with get_session() as session:
        # Get all snapshots for the requested listings
        snapshots = (
            session.query(PriceHistory)
            .filter(PriceHistory.listing_id.in_(listing_ids))
            .order_by(PriceHistory.listing_id, PriceHistory.snapshot_date.asc())
            .all()
        )

        result: dict[int, dict] = {}
        # Group by listing_id
        from itertools import groupby
        for lid, group in groupby(snapshots, key=lambda s: s.listing_id):
            records = list(group)
            if records:
                first_price = records[0].price
                current_price = records[-1].price
                result[lid] = {
                    "first_price": first_price,
                    "current_price": current_price,
                    "price_change": round(current_price - first_price, 2),
                }

        return result


def get_avg_price_by_period(
    bedroom_counts: list[int],
    period: str = "monthly",
) -> list[dict]:
    """Return average listing price grouped by time period and bedroom count.

    Args:
        bedroom_counts: List of bedroom counts to include (e.g. ``[3, 4]``).
        period: ``"monthly"`` or ``"weekly"``.

    Returns:
        A list of dicts with keys ``period_label``, ``bedrooms``, ``avg_price``.
        Sorted by period ascending.
    """
    with get_session() as session:
        snapshots = (
            session.query(PriceHistory, Listing.bedrooms)
            .join(Listing, PriceHistory.listing_id == Listing.id)
            .filter(Listing.bedrooms.in_(bedroom_counts))
            .all()
        )

        from collections import defaultdict

        # Group: (period_label, bedrooms) -> list of prices
        groups: dict[tuple[str, int], list[float]] = defaultdict(list)

        for snapshot, bedrooms in snapshots:
            sd = snapshot.snapshot_date
            if period == "weekly":
                # ISO year and week number
                iso_year, iso_week, _ = sd.isocalendar()
                period_label = f"{iso_year}-W{iso_week:02d}"
            else:
                # Monthly
                period_label = sd.strftime("%Y-%m")

            groups[(period_label, bedrooms)].append(snapshot.price)

        result = []
        for (period_label, bedrooms), prices in sorted(groups.items()):
            result.append({
                "period_label": period_label,
                "bedrooms": bedrooms,
                "avg_price": round(sum(prices) / len(prices), 2),
            })

        return result


# Number of consecutive scrapes a listing must be missing before
# ``mark_inactive()`` flips ``is_active=False``. With the daily-scrape
# launchd schedule, N=3 ≈ 3 days of consecutive misses — enough to
# absorb the non-deterministic RapidAPI Zillow index (Bug B, 2026-06-04).
MARK_INACTIVE_MISS_THRESHOLD = 3


def mark_inactive(source: str, active_ids: list[str]) -> None:
    """Update lifecycle counters and deactivate stale listings (Bug B fix).

    Previously this function flipped ``is_active=False`` on every listing
    absent from *active_ids* the very first time it went missing. The
    upstream RapidAPI Zillow provider's index is non-deterministic, so a
    single missed scrape was a false signal — and any subsequent hit
    re-activated the row via :func:`upsert_listing`, producing a
    "ratchet" where stale rows could stay active forever (e.g. zpid
    19615280 / 1525 Bittern Dr in 2026-06-04 incident).

    The new contract adds hysteresis via the ``consecutive_misses``
    column on ``listings``:

      - For each listing of *source* whose ``external_id`` is in
        *active_ids* (currently active): reset ``consecutive_misses``
        to 0. ``is_active`` is left as-is here — :func:`upsert_listing`
        is responsible for re-activating and clearing
        ``deactivated_at`` when the listing comes back.
      - For each listing of *source* whose ``external_id`` is NOT in
        *active_ids*: increment ``consecutive_misses`` by 1.
      - Then, for every listing whose post-increment counter is
        ``>= MARK_INACTIVE_MISS_THRESHOLD``: flip ``is_active=False``
        and set ``deactivated_at=now``.

    The same logic is mirrored onto ``listing_sources.is_active`` so
    multi-source counts stay in sync.

    Args:
        source: The listing source (e.g. ``"zillow"``).
        active_ids: List of ``external_id`` values that were seen in
            the latest scrape.
    """
    now_utc = datetime.now(timezone.utc)

    with get_session() as session:
        # --- Step 1: Reset counter on listings that ARE in this scrape ---
        if active_ids:
            session.query(Listing).filter(
                Listing.source == source,
                Listing.external_id.in_(active_ids),
                Listing.consecutive_misses != 0,
            ).update(
                {Listing.consecutive_misses: 0},
                synchronize_session="fetch",
            )

        # --- Step 2: Increment counter on listings that are MISSING ---
        # Note: we increment the counter on ALL listings of this source
        # that aren't in active_ids, regardless of current is_active —
        # this preserves the counter for already-inactive listings (in
        # case a future re-activation needs the audit trail) but the
        # threshold check below only flips active→inactive, so already
        # inactive rows are unaffected. Use a SQL-side increment so we
        # don't have to load every row.
        missed_q = session.query(Listing).filter(
            Listing.source == source,
            ~Listing.external_id.in_(active_ids) if active_ids else True,  # noqa: E712
        )
        missed_q.update(
            {Listing.consecutive_misses: Listing.consecutive_misses + 1},
            synchronize_session="fetch",
        )

        # --- Step 3: Deactivate listings that just crossed the threshold ---
        # Only flip currently-active rows (no-op on rows already inactive).
        # The threshold compare uses the post-increment value.
        threshold_q = session.query(Listing).filter(
            Listing.source == source,
            Listing.is_active == True,  # noqa: E712
            Listing.consecutive_misses >= MARK_INACTIVE_MISS_THRESHOLD,
        )
        crossed_listings = threshold_q.all()
        crossed_external_ids = [l.external_id for l in crossed_listings]
        if crossed_listings:
            threshold_q.update(
                {
                    Listing.is_active: False,
                    Listing.deactivated_at: now_utc,
                },
                synchronize_session="fetch",
            )

        # --- Step 4: Mirror onto ListingSource.is_active ---
        # Only the rows whose Listing just crossed the threshold should
        # flip their ListingSource.is_active. We DO NOT touch
        # ListingSource for sub-threshold misses (otherwise multi-source
        # counts would briefly drop and bounce).
        if crossed_external_ids:
            session.query(ListingSource).filter(
                ListingSource.source == source,
                ListingSource.is_active == True,  # noqa: E712
                ListingSource.external_id.in_(crossed_external_ids),
            ).update(
                {ListingSource.is_active: False},
                synchronize_session="fetch",
            )

        logger.info(
            "mark_inactive(source=%s): seen=%d, deactivated_this_call=%d "
            "(threshold=%d consecutive misses)",
            source,
            len(active_ids),
            len(crossed_external_ids),
            MARK_INACTIVE_MISS_THRESHOLD,
        )


def toggle_favorite(listing_id: int) -> bool:
    """Toggle the favorite status of a listing.

    Args:
        listing_id: Primary key of the listing.

    Returns:
        The new ``is_favorite`` value after toggling.
    """
    with get_session() as session:
        listing = session.get(Listing, listing_id)
        if listing is None:
            raise ValueError(f"Listing {listing_id} not found")
        listing.is_favorite = not listing.is_favorite
        new_state = listing.is_favorite
        return new_state


def toggle_dislike(listing_id: int) -> bool:
    """Toggle the dislike status of a listing.

    If a listing is being disliked and it was previously favorited,
    the favorite flag is cleared automatically.

    Args:
        listing_id: Primary key of the listing.

    Returns:
        The new ``is_disliked`` value after toggling.
    """
    with get_session() as session:
        listing = session.get(Listing, listing_id)
        if listing is None:
            raise ValueError(f"Listing {listing_id} not found")
        listing.is_disliked = not listing.is_disliked
        # If disliking, also clear favorite
        if listing.is_disliked and listing.is_favorite:
            listing.is_favorite = False
        new_state = listing.is_disliked
        return new_state


def get_source_counts(filters: dict[str, Any]) -> dict[str, int]:
    """Return the count of active listings per source, applying all filters
    except the source filter itself.

    Uses a SQL ``GROUP BY`` query via ``ListingSource`` join for accurate
    multi-source counting. A listing with both Zillow and Craigslist
    sources is counted under both.

    Args:
        filters: The same filter dict used by :func:`get_filtered_listings`,
            but the ``source`` key is ignored.

    Returns:
        A dict mapping source names to their listing counts,
        e.g. ``{"zillow": 11, "craigslist": 1}``.
    """
    with get_session() as session:
        query = session.query(
            func.coalesce(func.lower(ListingSource.source), "unknown"),
            func.count(func.distinct(Listing.id)),
        ).join(ListingSource, Listing.id == ListingSource.listing_id)

        # Apply shared filter logic (source is intentionally skipped)
        query = _apply_listing_filters(query, filters)

        is_active = filters.get("is_active", True)
        query = query.filter(Listing.is_active == is_active)

        query = query.group_by(
            func.coalesce(func.lower(ListingSource.source), "unknown")
        )
        rows = query.all()

        return {source: count for source, count in rows}


# ---------------------------------------------------------------------------
# API call logging & tracking
# ---------------------------------------------------------------------------


def log_api_call(service: str, endpoint: str | None = None, status_code: int | None = None) -> None:
    """Log a single API call."""
    with get_session() as session:
        session.add(ApiCallLog(
            service=service,
            endpoint=endpoint,
            status_code=status_code,
        ))


def get_api_call_count(service: str, month: date | None = None) -> int:
    """Return the number of API calls for a service in a given month.

    Args:
        service: The API service name (e.g. "zillow").
        month: Any date in the target month. Defaults to current month.

    Returns:
        The count of API calls in that month.
    """
    if month is None:
        month = date.today()

    # First day of the month
    first_day = month.replace(day=1)
    # First day of next month
    if month.month == 12:
        next_month = first_day.replace(year=month.year + 1, month=1)
    else:
        next_month = first_day.replace(month=month.month + 1)

    with get_session() as session:
        count = (
            session.query(func.count(ApiCallLog.id))
            .filter(
                ApiCallLog.service == service,
                ApiCallLog.called_at >= first_day,
                ApiCallLog.called_at < next_month,
            )
            .scalar()
        ) or 0
        return count


# The 3 configured scrape sources for activity monitoring.
_CONFIGURED_SOURCES = ("zillow", "craigslist", "realtor")


def get_scrape_activity_grid(days: int = 30) -> list[dict]:
    """Return per-day, per-source API call summary for the last *days* days.

    Queries the ``api_call_log`` table grouped by ``date(called_at)`` and
    ``service``, then fills in missing dates with zero counts so the
    calendar grid has no holes.

    Returns:
        List of dicts, one per day (most recent first)::

            [
                {
                    "date": "2026-04-06",
                    "sources": {
                        "zillow":     {"calls": 3, "success": 3, "errors": 0},
                        "craigslist": {"calls": 0, "success": 0, "errors": 0},
                        "realtor":    {"calls": 2, "success": 2, "errors": 0},
                    },
                    "status": "partial",   # "ok" | "partial" | "gap"
                },
                ...
            ]
    """
    today = date.today()
    start_date = today - timedelta(days=days - 1)

    with get_session() as session:
        rows = (
            session.query(
                func.date(ApiCallLog.called_at).label("day"),
                ApiCallLog.service,
                func.count(ApiCallLog.id).label("calls"),
                func.count(
                    case(
                        (ApiCallLog.status_code.between(200, 299), 1),
                    )
                ).label("success"),
                func.count(
                    case(
                        (
                            and_(
                                ApiCallLog.status_code.isnot(None),
                                ~ApiCallLog.status_code.between(200, 299),
                            ),
                            1,
                        ),
                    )
                ).label("errors"),
            )
            .filter(func.date(ApiCallLog.called_at) >= start_date)
            .group_by(func.date(ApiCallLog.called_at), ApiCallLog.service)
            .all()
        )

    # Build a lookup: {date_str: {service: {calls, success, errors}}}
    lookup: dict[str, dict[str, dict[str, int]]] = {}
    for row in rows:
        day_str = str(row.day)
        if day_str not in lookup:
            lookup[day_str] = {}
        lookup[day_str][row.service] = {
            "calls": row.calls,
            "success": row.success,
            "errors": row.errors,
        }

    # Fill in every date in the range, most recent first
    result: list[dict] = []
    zero = {"calls": 0, "success": 0, "errors": 0}

    for offset in range(days):
        d = today - timedelta(days=offset)
        d_str = d.isoformat()
        day_data = lookup.get(d_str, {})

        sources = {
            src: day_data.get(src, dict(zero))
            for src in _CONFIGURED_SOURCES
        }

        # Determine status
        active_sources = sum(1 for s in sources.values() if s["calls"] > 0)
        if active_sources == len(_CONFIGURED_SOURCES):
            status = "ok"
        elif active_sources > 0:
            status = "partial"
        else:
            status = "gap"

        result.append({
            "date": d_str,
            "sources": sources,
            "status": status,
        })

    return result


def get_data_freshness() -> datetime | None:
    """Return the most recent ``last_seen`` timestamp across all active listings.

    Useful for the backoffice dashboard to show how fresh the data is.

    Returns:
        The most recent ``last_seen`` datetime, or ``None`` if no active
        listings exist.
    """
    with get_session() as session:
        result = (
            session.query(func.max(Listing.last_seen))
            .filter(Listing.is_active == True)  # noqa: E712
            .scalar()
        )
        return result


def get_api_calls_by_day(service: str, month: date | None = None) -> list[dict[str, Any]]:
    """Return daily API call counts for a service in a given month.

    Args:
        service: The API service name (e.g. ``"zillow"``).
        month: Any date in the target month. Defaults to current month.

    Returns:
        A list of dicts with keys ``date`` (:class:`str` in ``YYYY-MM-DD``
        format) and ``count`` (:class:`int`), one entry per day that had
        at least one call.
    """
    if month is None:
        month = date.today()

    first_day = month.replace(day=1)
    if month.month == 12:
        next_month = first_day.replace(year=month.year + 1, month=1)
    else:
        next_month = first_day.replace(month=month.month + 1)

    with get_session() as session:
        rows = (
            session.query(
                func.date(ApiCallLog.called_at).label("day"),
                func.count(ApiCallLog.id).label("count"),
            )
            .filter(
                ApiCallLog.service == service,
                ApiCallLog.called_at >= first_day,
                ApiCallLog.called_at < next_month,
            )
            .group_by(func.date(ApiCallLog.called_at))
            .order_by(func.date(ApiCallLog.called_at))
            .all()
        )
        return [{"date": row.day, "count": row.count} for row in rows]


def get_recent_api_calls(service: str, limit: int = 50) -> list[dict[str, Any]]:
    """Return recent API call records as plain dicts.

    Designed for easy display in Streamlit ``st.dataframe()``.

    Args:
        service: The API service name (e.g. ``"zillow"``).
        limit: Maximum number of records to return.

    Returns:
        A list of dicts with keys ``called_at``, ``endpoint``, and
        ``status_code``, ordered by most recent first.
    """
    with get_session() as session:
        rows = (
            session.query(
                ApiCallLog.called_at,
                ApiCallLog.endpoint,
                ApiCallLog.status_code,
            )
            .filter(ApiCallLog.service == service)
            .order_by(ApiCallLog.called_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "called_at": row.called_at,
                "endpoint": row.endpoint,
                "status_code": row.status_code,
            }
            for row in rows
        ]


def get_api_success_rate_by_day(days: int = 7) -> list[dict[str, Any]]:
    """Return daily success rate for ALL sources combined over the last N days.

    A call is considered successful if its ``status_code`` is 200.

    Args:
        days: Number of days to look back (default 7).

    Returns:
        A list of dicts with keys ``date`` (:class:`str` in ``YYYY-MM-DD``
        format), ``total`` (:class:`int`), ``success`` (:class:`int`), and
        ``rate`` (:class:`float` — percentage 0–100), ordered chronologically.
    """
    cutoff = date.today() - timedelta(days=days - 1)

    with get_session() as session:
        rows = (
            session.query(
                func.date(ApiCallLog.called_at).label("day"),
                func.count(ApiCallLog.id).label("total"),
                func.sum(
                    case(
                        (ApiCallLog.status_code == 200, 1),
                        else_=0,
                    )
                ).label("success"),
            )
            .filter(ApiCallLog.called_at >= cutoff)
            .group_by(func.date(ApiCallLog.called_at))
            .order_by(func.date(ApiCallLog.called_at))
            .all()
        )
        return [
            {
                "date": row.day,
                "total": row.total,
                "success": row.success,
                "rate": round(row.success / row.total * 100, 1) if row.total > 0 else 0,
            }
            for row in rows
        ]


def get_api_call_count_for_period(service: str, start_date: date, end_date: date) -> int:
    """Return the count of API calls for a service between two dates.

    Used for the "Monthly Comparison" chart (this month vs last month
    at the same point).

    Args:
        service: The API service name (e.g. ``"zillow"``).
        start_date: Start of the period (inclusive).
        end_date: End of the period (exclusive).

    Returns:
        The count of API calls in the specified period.
    """
    with get_session() as session:
        count = (
            session.query(func.count(ApiCallLog.id))
            .filter(
                ApiCallLog.service == service,
                ApiCallLog.called_at >= start_date,
                ApiCallLog.called_at < end_date,
            )
            .scalar()
        ) or 0
        return count


def seed_historical_api_calls(count: int, service: str = "zillow") -> None:
    """Seed the api_call_log with estimated historical calls.

    Only runs if the table is empty (first-time setup).
    """
    with get_session() as session:
        existing = session.query(func.count(ApiCallLog.id)).scalar() or 0
        if existing > 0:
            return  # Already seeded

        # Insert placeholder records spread across the current month
        from datetime import timedelta
        today = date.today()
        first_of_month = today.replace(day=1)
        days_elapsed = (today - first_of_month).days or 1

        for i in range(count):
            day_offset = int(i * days_elapsed / count)
            call_date = first_of_month + timedelta(days=day_offset)
            session.add(ApiCallLog(
                service=service,
                called_at=datetime(call_date.year, call_date.month, call_date.day, 12, 0, 0, tzinfo=timezone.utc),
                endpoint="historical_estimate",
            ))

        logger.info("Seeded %d historical API call records for %s.", count, service)


def get_listing_stats() -> dict[str, Any]:
    """Return aggregate statistics about stored listings.

    Uses SQL aggregate functions for total and average price to avoid
    loading all ORM objects into memory.  Median is computed from a
    lightweight column-only query.

    Returns:
        A dictionary with keys:

        - ``total`` — total number of active listings
        - ``avg_price`` — average monthly rent (or 0.0)
        - ``median_price`` — median monthly rent (or 0.0)
        - ``new_today`` — number of listings first seen today
    """
    with get_session() as session:
        # Total count and average price via SQL aggregates
        agg_row = (
            session.query(
                func.count(Listing.id),
                func.avg(Listing.price),
            )
            .filter(Listing.is_active == True)  # noqa: E712
            .one()
        )
        total = agg_row[0] or 0
        avg_price = round(float(agg_row[1]), 2) if agg_row[1] is not None else 0.0

        # Median price — load only the price column (not full ORM objects)
        price_rows = (
            session.query(Listing.price)
            .filter(
                Listing.is_active == True,  # noqa: E712
                Listing.price.isnot(None),
            )
            .all()
        )
        prices = [row[0] for row in price_rows]
        median_price = round(median(prices), 2) if prices else 0.0

        today = date.today()
        new_today = (
            session.query(func.count(Listing.id))
            .filter(
                Listing.is_active == True,  # noqa: E712
                func.date(Listing.first_seen) == today,
            )
            .scalar()
        ) or 0

        return {
            "total": total,
            "avg_price": avg_price,
            "median_price": median_price,
            "new_today": new_today,
        }


# ---------------------------------------------------------------------------
# Notification helpers
# ---------------------------------------------------------------------------


def get_unnotified_listings(
    filters: dict[str, Any] | None = None,
) -> list[Listing]:
    """Return active, unnotified listings, optionally filtered by criteria.

    Queries the local SQLite DB only — no external API calls.

    Args:
        filters: Optional dictionary of filter criteria (same keys as
            :func:`get_filtered_listings`).  When provided, only
            listings matching these criteria are returned — e.g. the
            notification pipeline passes the user's ``config.yaml``
            search preferences so emails only contain relevant listings.

    Returns:
        A list of :class:`~src.models.Listing` instances with
        ``notified=False`` and ``is_active=True``, optionally narrowed
        by *filters*.
    """
    with get_session() as session:
        query = session.query(Listing).filter(
            Listing.notified == False,  # noqa: E712
            Listing.is_active == True,  # noqa: E712
        )

        # Apply optional filters (same logic as get_filtered_listings)
        if filters:
            query = _apply_listing_filters(query, filters)

        listings = query.order_by(Listing.first_seen.desc()).all()
        session.expunge_all()
        return listings


def mark_listings_notified(listing_ids: list[int]) -> None:
    """Bulk-update listings to ``notified=True``.

    Args:
        listing_ids: Primary keys of listings to mark as notified.
    """
    if not listing_ids:
        return

    with get_session() as session:
        session.query(Listing).filter(
            Listing.id.in_(listing_ids),
        ).update(
            {Listing.notified: True},
            synchronize_session="fetch",
        )
        logger.info("Marked %d listing(s) as notified.", len(listing_ids))


def log_notification(
    channel: str,
    listing_count: int,
    recipient: str,
    success: bool,
    error_category: str | None = None,
    error_message: str | None = None,
) -> None:
    """Insert a row into the ``notification_log`` table.

    Args:
        channel: Channel name (e.g. ``"email"``).
        listing_count: Number of listings included in the notification.
        recipient: Recipient identifier (email address, phone, etc.).
        success: Whether the send succeeded.
        error_category: Short machine-readable failure tag for failed
            sends (e.g. ``"token_expired"``, ``"auth"``,
            ``"missing_credentials"``).  Ignored when ``success`` is True.
        error_message: Human-readable failure description for failed sends.
            Truncated to 1000 chars to keep log rows compact.
    """
    # Defensive: never persist error data on a successful row.
    if success:
        error_category = None
        error_message = None
    elif error_message and len(error_message) > 1000:
        error_message = error_message[:997] + "..."

    with get_session() as session:
        session.add(
            NotificationLog(
                channel=channel,
                listing_count=listing_count,
                recipient=recipient,
                success=success,
                error_category=error_category,
                error_message=error_message,
            )
        )
    logger.info(
        "Logged notification: channel=%s, count=%d, recipient=%s, success=%s%s",
        channel,
        listing_count,
        recipient,
        success,
        f", error={error_category}" if (not success and error_category) else "",
    )


def get_last_channel_failure(
    channel: str,
    within_hours: int = 48,
) -> dict | None:
    """Return the most recent failed notification for a given channel.

    Used by the admin Notifications page to surface diagnostics (e.g.
    token-expired warnings) when the latest send for a channel failed.

    Only returns a row if the **most recent** notification for that
    channel within the lookback window was a failure — i.e. a later
    successful send clears the warning automatically.

    Args:
        channel: Channel name (e.g. ``"whatsapp"``, ``"email"``).
        within_hours: Lookback window in hours (default 48).

    Returns:
        A dict with keys ``sent_at``, ``recipient``, ``error_category``,
        ``error_message`` if the most recent attempt failed; otherwise
        ``None``.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=within_hours)
    with get_session() as session:
        latest = (
            session.query(
                NotificationLog.sent_at,
                NotificationLog.recipient,
                NotificationLog.success,
                NotificationLog.error_category,
                NotificationLog.error_message,
            )
            .filter(NotificationLog.channel == channel)
            .filter(NotificationLog.sent_at >= cutoff)
            .order_by(NotificationLog.sent_at.desc())
            .first()
        )
        if latest is None or latest.success:
            return None
        return {
            "sent_at": latest.sent_at,
            "recipient": latest.recipient,
            "error_category": latest.error_category,
            "error_message": latest.error_message,
        }


def get_today_notification_count() -> int:
    """Return the number of **successful** notification sends today (Asia/Jerusalem).

    Counts only rows with ``success=True``.  Failed attempts (network
    errors, expired tokens, refused recipients, etc.) are excluded so a
    morning network blip cannot consume the daily cap and silently
    suppress the evening send.

    The original implementation counted *all* attempts to "prevent
    unlimited failure spam" from misconfigured channels.  In practice
    every documented failure mode short-circuits BEFORE any message is
    actually delivered (network, auth, token_expired, recipient_refused,
    missing_credentials, disabled) — so counting them only protects
    against a hypothetical "send raised AFTER delivering" race that has
    never occurred.  See [`silent-failure-pattern.md`](docs/memory/wiki/concepts/silent-failure-pattern.md)
    for the 2026-06-03 incident that motivated this change (7-day
    Telegram silence after two morning network failures consumed the cap).

    Uses an IST-day window translated to UTC bounds for the SQL comparison.
    ``NotificationLog.sent_at`` is stored as a **naive UTC** datetime on
    SQLite (the column drops ``tzinfo`` on persist — see
    [`src/models.py`](src/models.py)).  Comparing ``func.date(sent_at)``
    directly against an IST date would therefore evaluate in UTC and
    silently undercount near IST midnight (00:00–03:00 IST ≈ 21:00–00:00
    UTC the previous day).  Translating today's IST window to a
    ``[start_utc, end_utc)`` range and filtering on the raw datetime
    closes that gap so the daily cap honours the operator's local day.

    Returns:
        Count of successful notification log entries whose ``sent_at``
        falls on today's date in the Asia/Jerusalem timezone.
    """
    _IST = timezone(timedelta(hours=3))
    today = datetime.now(_IST).date()
    # Today expressed as an IST window → translate to UTC bounds because
    # NotificationLog.sent_at is stored as naive UTC on SQLite.
    ist_midnight = datetime.combine(today, time(0), tzinfo=_IST)
    start_utc = ist_midnight.astimezone(timezone.utc).replace(tzinfo=None)
    end_utc = (ist_midnight + timedelta(days=1)).astimezone(timezone.utc).replace(tzinfo=None)
    with get_session() as session:
        count = (
            session.query(func.count(NotificationLog.id))
            .filter(
                NotificationLog.sent_at >= start_utc,
                NotificationLog.sent_at < end_utc,
                NotificationLog.success == True,  # noqa: E712
            )
            .scalar()
        ) or 0
        return count


def get_last_successful_notification_at() -> datetime | None:
    """Return the timestamp of the most recent successful notification.

    Used by the dashboard silence-detector banner to determine whether
    notifications have stopped working.  Considers ALL channels — only
    one channel needs to succeed to count as "the system is working".

    Returns:
        The ``sent_at`` of the most recent ``success=True`` row in
        ``notification_log``, or ``None`` if no successful send has ever
        been recorded.  Timestamps are returned as naive ``datetime``
        objects in UTC (matching the stored column).
    """
    with get_session() as session:
        latest = (
            session.query(NotificationLog.sent_at)
            .filter(NotificationLog.success == True)  # noqa: E712
            .order_by(NotificationLog.sent_at.desc())
            .first()
        )
        return latest.sent_at if latest is not None else None


# ---------------------------------------------------------------------------
# Analytics helpers
# ---------------------------------------------------------------------------


def get_price_distribution(include_inactive: bool = False) -> list[float]:
    """Return all listing prices for histogram display.

    Uses a column-only query to avoid loading full ORM objects — much
    more efficient for histogram data.

    Args:
        include_inactive: If ``True``, include inactive listings too.

    Returns:
        A list of prices (floats).
    """
    with get_session() as session:
        query = session.query(Listing.price).filter(Listing.price.isnot(None))
        if not include_inactive:
            query = query.filter(Listing.is_active == True)  # noqa: E712
        rows = query.all()
        return [row[0] for row in rows]


def get_listing_inventory_timeline() -> list[dict]:
    """Return cumulative active listing count over time.

    Groups listings by ``date(first_seen)`` and computes a running total
    to show how inventory has grown.

    Returns:
        A list of dicts with keys ``date`` (str, ``YYYY-MM-DD``) and
        ``count`` (int, cumulative total).
    """
    with get_session() as session:
        rows = (
            session.query(
                func.date(Listing.first_seen).label("day"),
                func.count(Listing.id).label("daily_count"),
            )
            .filter(Listing.is_active == True)  # noqa: E712
            .group_by(func.date(Listing.first_seen))
            .order_by(func.date(Listing.first_seen))
            .all()
        )

        result = []
        cumulative = 0
        for row in rows:
            cumulative += row.daily_count
            result.append({"date": row.day, "count": cumulative})

        return result


def get_source_counts_with_inactive() -> dict[str, dict[str, int]]:
    """Return listing counts per source, split by active/inactive status.

    Uses ``ListingSource`` join with ``GROUP BY source, is_active``.

    Returns:
        A nested dict, e.g.::

            {
                "zillow": {"active": 20, "inactive": 3},
                "craigslist": {"active": 5, "inactive": 1},
            }
    """
    with get_session() as session:
        rows = (
            session.query(
                func.coalesce(func.lower(ListingSource.source), "unknown"),
                Listing.is_active,
                func.count(func.distinct(Listing.id)),
            )
            .join(ListingSource, Listing.id == ListingSource.listing_id)
            .group_by(func.coalesce(func.lower(ListingSource.source), "unknown"), Listing.is_active)
            .all()
        )

        result: dict[str, dict[str, int]] = {}
        for source, is_active, count in rows:
            if source not in result:
                result[source] = {"active": 0, "inactive": 0}
            key = "active" if is_active else "inactive"
            result[source][key] = count

        return result


# ---------------------------------------------------------------------------
# Notification analytics helpers
# ---------------------------------------------------------------------------


def get_notification_history(limit: int = 100) -> list[dict]:
    """Return recent notification records as plain dicts.

    Args:
        limit: Maximum number of records to return.

    Returns:
        A list of dicts with keys ``sent_at``, ``channel``, ``recipient``,
        ``listing_count``, ``success``, ``error_category``, ``error_message``,
        ordered by most recent first.
    """
    with get_session() as session:
        rows = (
            session.query(
                NotificationLog.sent_at,
                NotificationLog.channel,
                NotificationLog.recipient,
                NotificationLog.listing_count,
                NotificationLog.success,
                NotificationLog.error_category,
                NotificationLog.error_message,
            )
            .order_by(NotificationLog.sent_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "sent_at": row.sent_at,
                "channel": row.channel,
                "recipient": row.recipient,
                "listing_count": row.listing_count,
                "success": row.success,
                "error_category": row.error_category,
                "error_message": row.error_message,
            }
            for row in rows
        ]


def get_notifications_by_day(days: int = 30) -> list[dict]:
    """Return daily notification counts for the last N days.

    Args:
        days: Number of days to look back.

    Returns:
        A list of dicts with keys ``date`` (str), ``count`` (int),
        and ``success_count`` (int).
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    with get_session() as session:
        rows = (
            session.query(
                func.date(NotificationLog.sent_at).label("day"),
                func.count(NotificationLog.id).label("total"),
                func.sum(
                    func.cast(NotificationLog.success, SAInteger)
                ).label("success_total"),
            )
            .filter(NotificationLog.sent_at >= cutoff)
            .group_by(func.date(NotificationLog.sent_at))
            .order_by(func.date(NotificationLog.sent_at))
            .all()
        )
        return [
            {
                "date": row.day,
                "count": row.total,
                "success_count": row.success_total or 0,
            }
            for row in rows
        ]


def get_notification_stats() -> dict:
    """Return aggregate notification statistics.

    Uses a single query with conditional aggregation instead of 3 separate
    COUNT queries for better performance.

    ``today_count`` deliberately counts **all** notification log rows for
    today (success + failure) because this stat powers the admin dashboard
    *Notifications Today* counter — operators want visibility into every
    dispatch attempt, not just successes.  This is intentionally
    **decoupled from** :func:`get_today_notification_count`, which counts
    only successes because it gates the anti-spam ceiling (see that
    function's docstring for the 2026-06-03 rationale).
    ``success_rate`` is still based on successful sends only.

    Returns:
        A dict with keys ``total`` (int), ``success_rate`` (float, 0–100),
        and ``today_count`` (int — all notification attempts today).
    """
    _IST = timezone(timedelta(hours=3))
    today = datetime.now(_IST).date()

    with get_session() as session:
        row = session.query(
            func.count(NotificationLog.id),
            func.count(case((NotificationLog.success == True, 1))),  # noqa: E712
            func.count(case((
                func.date(NotificationLog.sent_at) == today, 1
            ))),
        ).one()

        total = row[0] or 0
        success_count = row[1] or 0
        today_count = row[2] or 0
        success_rate = round((success_count / total) * 100, 1) if total > 0 else 100.0

        return {
            "total": total,
            "success_rate": success_rate,
            "today_count": today_count,
        }


# ---------------------------------------------------------------------------
# Lifecycle analytics
# ---------------------------------------------------------------------------


def get_lifecycle_stats() -> dict:
    """Return lifecycle statistics for inactive listings.

    Uses ``deactivated_at - first_seen`` when available, falls back to
    ``last_seen - first_seen`` for legacy data (via ``COALESCE``).

    Returns:
        Dict with keys: ``avg_lifespan_days``, ``median_lifespan_days``,
        ``min_lifespan_days``, ``max_lifespan_days``, ``total_removed``.
    """
    with get_session() as session:
        # Aggregate stats via SQLite julianday()
        row = session.execute(text("""
            SELECT
                COUNT(*) as total_removed,
                AVG(julianday(COALESCE(deactivated_at, last_seen)) - julianday(first_seen)) as avg_days,
                MIN(julianday(COALESCE(deactivated_at, last_seen)) - julianday(first_seen)) as min_days,
                MAX(julianday(COALESCE(deactivated_at, last_seen)) - julianday(first_seen)) as max_days
            FROM listings
            WHERE is_active = 0
        """)).one()

        total_removed = row.total_removed or 0
        avg_days = round(row.avg_days, 1) if row.avg_days is not None else 0.0
        min_days = round(row.min_days, 1) if row.min_days is not None else 0.0
        max_days = round(row.max_days, 1) if row.max_days is not None else 0.0

        # Compute median in Python (SQLite lacks MEDIAN)
        lifespan_rows = session.execute(text("""
            SELECT julianday(COALESCE(deactivated_at, last_seen)) - julianday(first_seen) as lifespan
            FROM listings
            WHERE is_active = 0
            ORDER BY lifespan
        """)).all()

        lifespans = [r.lifespan for r in lifespan_rows if r.lifespan is not None]
        median_days = round(median(lifespans), 1) if lifespans else 0.0

        return {
            "avg_lifespan_days": avg_days,
            "median_lifespan_days": median_days,
            "min_lifespan_days": min_days,
            "max_lifespan_days": max_days,
            "total_removed": total_removed,
        }


def get_lifecycle_by_bedrooms() -> list[dict]:
    """Return average lifespan breakdown by bedroom count.

    Returns:
        List of dicts: ``[{"bedrooms": 3, "avg_days": 12.5, "count": 8}, ...]``
    """
    with get_session() as session:
        rows = session.execute(text("""
            SELECT
                bedrooms,
                COUNT(*) as count,
                AVG(julianday(COALESCE(deactivated_at, last_seen)) - julianday(first_seen)) as avg_days
            FROM listings
            WHERE is_active = 0
            GROUP BY bedrooms
            ORDER BY bedrooms
        """)).all()

        return [
            {
                "bedrooms": row.bedrooms,
                "avg_days": round(row.avg_days, 1) if row.avg_days is not None else 0.0,
                "count": row.count,
            }
            for row in rows
        ]


def get_lifecycle_by_price_range() -> list[dict]:
    """Return average lifespan breakdown by price bucket.

    Price buckets: Under $2k, $2k–$3k, $3k–$4k, $4k–$5k, $5k+.

    Returns:
        List of dicts: ``[{"range": "$3k–$4k", "avg_days": 10.2, "count": 5}, ...]``
    """
    with get_session() as session:
        rows = session.execute(text("""
            SELECT
                CASE
                    WHEN price < 2000 THEN 'Under $2k'
                    WHEN price < 3000 THEN '$2k–$3k'
                    WHEN price < 4000 THEN '$3k–$4k'
                    WHEN price < 5000 THEN '$4k–$5k'
                    ELSE '$5k+'
                END as price_range,
                COUNT(*) as count,
                AVG(julianday(COALESCE(deactivated_at, last_seen)) - julianday(first_seen)) as avg_days
            FROM listings
            WHERE is_active = 0
            GROUP BY price_range
            ORDER BY MIN(price)
        """)).all()

        return [
            {
                "range": row.price_range,
                "avg_days": round(row.avg_days, 1) if row.avg_days is not None else 0.0,
                "count": row.count,
            }
            for row in rows
        ]
