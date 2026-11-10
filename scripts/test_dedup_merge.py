"""Self-contained reproducer/regression test for the cross-source dedup bug.

Background
----------
The cross-source deduplication system was a silent no-op: it correctly *detected*
duplicates but every merge attempt crashed with ``IntegrityError`` on
``uq_ls_source_external_id`` because:

1. ``upsert_listing()`` for the duplicate listing INSERTs a fresh
   ``ListingSource(source, external_id, listing_id=NEW_ID)`` row before the
   orchestrator opens the dedup session.
2. ``_merge_duplicate()`` then tried to INSERT *another* ``ListingSource`` with
   the **same** ``(source, external_id)`` but ``listing_id=CANONICAL_ID`` — which
   the unique constraint correctly rejected.

The bug was masked by an over-broad ``except IntegrityError`` block in
``find_and_merge_duplicate()`` that swallowed the error as a "possible race
condition".

This test reproduces the exact scenario from the live trace
(zillow ``19623492`` + craigslist ``7930664370`` at 1426 Ormsby Dr, 94087)
and asserts the post-merge invariants. Before the fix it FAILS with the
``IntegrityError`` (or, depending on whether the fix to the IntegrityError
handler is also in place, with the canonical listing being unmodified).
After the fix it PASSES.

Run::

    python -m scripts.test_dedup_merge

Exit code 0 = pass, 1 = fail.
"""

from __future__ import annotations

import sys
import traceback
from datetime import date, datetime, timezone
from pathlib import Path

# Ensure project root is importable when run as ``python scripts/test_dedup_merge.py``
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# IMPORTANT: import the database module so we can override its globals
import src.database as database_module
from src.database import upsert_listing
from src.dedup import find_and_merge_duplicate
from src.models import Base, Listing, ListingSource


# ---------------------------------------------------------------------------
# Test infrastructure: in-memory SQLite, override globals
# ---------------------------------------------------------------------------


def _setup_in_memory_db() -> None:
    """Replace the module-level engine + session factory with an in-memory SQLite.

    SQLite ``:memory:`` databases are per-connection by default, so we use the
    SQLAlchemy ``StaticPool`` to reuse the single connection across sessions
    within the test process.
    """
    from sqlalchemy.pool import StaticPool

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    Base.metadata.create_all(engine)

    # Override the module-level globals used by get_session() etc.
    database_module._engine = engine
    database_module._SessionFactory = sessionmaker(bind=engine)


def _make_listing_data(
    source: str,
    external_id: str,
    *,
    address: str = "1426 Ormsby Dr",
    city: str = "Sunnyvale",
    zip_code: str = "94087",
    price: float = 6500.0,
    bedrooms: int = 4,
    bathrooms: float = 3.0,
    sqft: int = 2000,
    property_type: str = "house",
    title: str | None = None,
    url: str | None = None,
    listed_date: date | None = None,
) -> dict:
    """Build a minimal-but-valid listing_data dict matching ``Listing`` columns."""
    return {
        "source": source,
        "external_id": external_id,
        "url": url or f"https://example.com/{source}/{external_id}",
        "title": title or f"{bedrooms}BR house at {address}",
        "address": address,
        "city": city,
        "zip_code": zip_code,
        "price": price,
        "bedrooms": bedrooms,
        "bathrooms": bathrooms,
        "sqft": sqft,
        "property_type": property_type,
        "listed_date": listed_date,
    }


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


def test_cross_source_merge_does_not_raise_integrity_error() -> None:
    """Reproducer for the silent-IntegrityError bug.

    Steps:
      1. Insert canonical zillow listing 19623492 at 1426 Ormsby Dr.
      2. Insert craigslist listing 7930664370 at the same address (this creates
         the ListingSource row that the buggy ``_merge_duplicate()`` collides
         with).
      3. Call ``find_and_merge_duplicate()`` for the new craigslist listing.

    Assertions:
      * No IntegrityError is raised or silently swallowed (verified by checking
        post-state: canonical now has 2 source rows AND duplicate listing is
        gone).
      * Canonical listing has 2 ``ListingSource`` rows
        (``source IN {zillow, craigslist}``).
      * Duplicate listing row is deleted from ``listings``.
      * ``ListingSource`` row for craigslist still exists with
        ``listing_id == canonical.id``.
    """
    _setup_in_memory_db()

    # Step 1: insert canonical (zillow)
    zillow_data = _make_listing_data("zillow", "19623492")
    canonical, is_new_z = upsert_listing(zillow_data)
    assert is_new_z, "Zillow listing should be newly inserted"
    canonical_id = canonical.id

    # Step 2: insert duplicate (craigslist) — upsert_listing creates a
    # ListingSource(source='craigslist', external_id='7930664370',
    # listing_id=<dup.id>) at this point. This is the row the bug collides with.
    cl_data = _make_listing_data("craigslist", "7930664370")
    duplicate, is_new_c = upsert_listing(cl_data)
    assert is_new_c, "Craigslist listing should be newly inserted"
    duplicate_id = duplicate.id
    assert duplicate_id != canonical_id, "Different external_ids → different IDs"

    # Sanity: before dedup, there are 2 listings + 2 source rows
    with database_module.get_session() as s:
        assert s.query(Listing).count() == 2
        assert s.query(ListingSource).count() == 2

    # Step 3: run dedup
    with database_module.get_session() as s:
        dup_in_session = s.get(Listing, duplicate_id)
        assert dup_in_session is not None
        result = find_and_merge_duplicate(
            session=s,
            listing=dup_in_session,
            listing_data=cl_data,
        )
        # Must return the canonical (not None — None means dedup didn't run)
        assert result is not None, (
            "find_and_merge_duplicate returned None — either no duplicate was "
            "detected (scoring bug) OR the IntegrityError was silently swallowed."
        )
        assert result.id == canonical_id, (
            f"Expected canonical id={canonical_id}, got {result.id}"
        )

    # Step 4: verify post-state
    with database_module.get_session() as s:
        # Duplicate listing row must be gone
        assert s.get(Listing, duplicate_id) is None, (
            f"Duplicate listing #{duplicate_id} should have been deleted"
        )
        # Canonical still exists
        canon_after = s.get(Listing, canonical_id)
        assert canon_after is not None, "Canonical listing must still exist"

        # Canonical now has 2 ListingSource rows (zillow + craigslist)
        sources_for_canon = (
            s.query(ListingSource)
            .filter_by(listing_id=canonical_id)
            .order_by(ListingSource.source)
            .all()
        )
        source_names = sorted(src.source for src in sources_for_canon)
        assert source_names == ["craigslist", "zillow"], (
            f"Expected canonical to have sources [craigslist, zillow], got "
            f"{source_names!r} (count={len(sources_for_canon)})"
        )

        # The craigslist source row must still exist by its (source, external_id)
        # AND point to the canonical
        cl_source = (
            s.query(ListingSource)
            .filter_by(source="craigslist", external_id="7930664370")
            .first()
        )
        assert cl_source is not None, (
            "Craigslist ListingSource row vanished — should have been reassigned, "
            "not deleted."
        )
        assert cl_source.listing_id == canonical_id, (
            f"Craigslist source row points to listing_id={cl_source.listing_id}, "
            f"expected {canonical_id}"
        )

        # Total ListingSource rows: still 2 (no orphans, no duplicates)
        total_sources = s.query(ListingSource).count()
        assert total_sources == 2, (
            f"Expected exactly 2 ListingSource rows, got {total_sources}"
        )


def test_no_duplicate_returns_none() -> None:
    """Sanity test: when no duplicate exists, find_and_merge_duplicate returns None."""
    _setup_in_memory_db()

    # One zillow listing in zip 94087
    z_data = _make_listing_data("zillow", "11111", address="1 Different St")
    z_listing, _ = upsert_listing(z_data)

    # Craigslist listing in a totally different zip — should not match
    cl_data = _make_listing_data(
        "craigslist", "22222",
        address="999 Other Way",
        zip_code="99999",
        price=1000,
        bedrooms=1,
    )
    cl_listing, _ = upsert_listing(cl_data)

    with database_module.get_session() as s:
        dup = s.get(Listing, cl_listing.id)
        result = find_and_merge_duplicate(
            session=s,
            listing=dup,
            listing_data=cl_data,
        )
        assert result is None, "No duplicate expected, but merge happened"

    # Both listings still present
    with database_module.get_session() as s:
        assert s.query(Listing).count() == 2
        assert s.query(ListingSource).count() == 2


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


TESTS = [
    ("test_cross_source_merge_does_not_raise_integrity_error",
     test_cross_source_merge_does_not_raise_integrity_error),
    ("test_no_duplicate_returns_none", test_no_duplicate_returns_none),
]


def main() -> int:
    passed = 0
    failed = 0
    for name, fn in TESTS:
        try:
            fn()
        except AssertionError as exc:
            failed += 1
            print(f"FAIL: {name}")
            print(f"  AssertionError: {exc}")
        except Exception:
            failed += 1
            print(f"FAIL: {name} (unexpected exception)")
            traceback.print_exc()
        else:
            passed += 1
            print(f"PASS: {name}")

    print()
    print(f"Results: {passed} passed, {failed} failed (total {len(TESTS)})")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
