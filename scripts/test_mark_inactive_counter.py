"""Unit tests for the new ``consecutive_misses`` semantics in ``mark_inactive`` (Bug B).

Background
----------
On 2026-06-04 a stale Zillow listing (zpid 19615280, 1525 Bittern Dr) was
still ``is_active=True`` in our DB long after it went off-market. Debug
verified the upstream RapidAPI provider's *index* is non-deterministic
— the same query returned the zpid at 04:20 UTC but NOT in three
10:50 UTC retries. The previous ``mark_inactive`` logic deactivated a
listing the very first scrape it went missing — but a single random hit
on any subsequent scrape un-deactivates it (via ``upsert_listing``),
yielding a row that's ALWAYS active even when stale.

Fix (this test asserts): ``mark_inactive`` must add hysteresis via a
``consecutive_misses`` counter:

  - Listings present in ``active_ids`` → counter reset to 0.
  - Listings absent from ``active_ids`` → counter += 1.
  - Listings with counter ≥ 3 → flip ``is_active=False`` AND set
    ``deactivated_at``. Below the threshold they stay active.

N=3 ≈ 3 daily scrapes (≈3 days of consecutive misses) because the
scraper now runs once per day via launchd.

Run::

    .venv/bin/python scripts/test_mark_inactive_counter.py

Exit code 0 = pass, 1 = fail.
"""

from __future__ import annotations

import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

# Ensure project root is importable
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import src.database as database_module
from src.database import mark_inactive
from src.models import Base, Listing, ListingSource


# ---------------------------------------------------------------------------
# Test infrastructure
# ---------------------------------------------------------------------------


def _setup_in_memory_db() -> None:
    """Replace the module-level engine + session factory with in-memory SQLite."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    Base.metadata.create_all(engine)
    database_module._engine = engine
    database_module._SessionFactory = sessionmaker(bind=engine)


def _insert_listing(
    *,
    source: str,
    external_id: str,
    is_active: bool = True,
    consecutive_misses: int = 0,
    deactivated_at: datetime | None = None,
) -> int:
    """Insert a minimal listing row + matching listing_source. Return listing id."""
    with database_module.get_session() as session:
        listing = Listing(
            source=source,
            external_id=external_id,
            url=f"https://example.com/{external_id}",
            title=f"Test listing {external_id}",
            address="100 Test Ave",
            city="Sunnyvale",
            zip_code="94087",
            price=5000.0,
            bedrooms=3,
            bathrooms=2.0,
            property_type="house",
            is_active=is_active,
            deactivated_at=deactivated_at,
        )
        # Set consecutive_misses via setattr so the test still works
        # if the attribute exists only on the Column (pre-refresh).
        try:
            setattr(listing, "consecutive_misses", consecutive_misses)
        except Exception:
            pass
        session.add(listing)
        session.flush()
        listing_id = listing.id

        session.add(
            ListingSource(
                listing_id=listing_id,
                source=source,
                external_id=external_id,
                url=f"https://example.com/{external_id}",
                is_active=is_active,
            )
        )
    return listing_id


def _get_listing(listing_id: int) -> Listing:
    """Fetch a listing by id (detached snapshot — read attributes only)."""
    with database_module.get_session() as session:
        listing = session.get(Listing, listing_id)
        assert listing is not None, f"Listing {listing_id} disappeared"
        # Force-load all attributes before the session closes
        _ = (
            listing.is_active,
            listing.deactivated_at,
            getattr(listing, "consecutive_misses", None),
        )
        session.expunge(listing)
        return listing


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


def test_present_listing_resets_counter_to_zero() -> None:
    """A listing in active_ids → consecutive_misses reset to 0, stays active."""
    _setup_in_memory_db()
    lid = _insert_listing(
        source="zillow", external_id="111", consecutive_misses=2
    )
    # zpid 111 IS in this scrape's active set
    mark_inactive("zillow", ["111"])
    listing = _get_listing(lid)
    assert listing.is_active is True, "Present listing must stay active"
    assert getattr(listing, "consecutive_misses", None) == 0, (
        f"Counter must reset to 0 for present listing "
        f"(got {getattr(listing, 'consecutive_misses', None)})"
    )
    assert listing.deactivated_at is None, "deactivated_at must remain NULL"
    print("✓ test_present_listing_resets_counter_to_zero")


def test_absent_once_increments_counter_but_stays_active() -> None:
    """A listing absent for the 1st time → counter=1, still active."""
    _setup_in_memory_db()
    lid = _insert_listing(
        source="zillow", external_id="222", consecutive_misses=0
    )
    # zpid 222 is NOT in this scrape's active set (some OTHER zpid is)
    mark_inactive("zillow", ["999"])
    listing = _get_listing(lid)
    assert listing.is_active is True, (
        "Listing absent only once must stay active (below N=3 threshold)"
    )
    assert getattr(listing, "consecutive_misses", None) == 1, (
        f"Counter must increment to 1 "
        f"(got {getattr(listing, 'consecutive_misses', None)})"
    )
    assert listing.deactivated_at is None, "deactivated_at must remain NULL below threshold"
    print("✓ test_absent_once_increments_counter_but_stays_active")


def test_absent_twice_increments_to_two_still_active() -> None:
    """A listing absent 2× in a row → counter=2, still active (below N=3)."""
    _setup_in_memory_db()
    lid = _insert_listing(
        source="zillow", external_id="333", consecutive_misses=1
    )
    mark_inactive("zillow", ["999"])
    listing = _get_listing(lid)
    assert listing.is_active is True, "Counter=2 is still below threshold N=3"
    assert getattr(listing, "consecutive_misses", None) == 2
    assert listing.deactivated_at is None
    print("✓ test_absent_twice_increments_to_two_still_active")


def test_absent_third_time_deactivates_at_threshold() -> None:
    """A listing absent 3× in a row → counter=3, is_active=False, deactivated_at set."""
    _setup_in_memory_db()
    lid = _insert_listing(
        source="zillow", external_id="444", consecutive_misses=2
    )
    before = datetime.now(timezone.utc).replace(tzinfo=None)
    mark_inactive("zillow", ["999"])
    after = datetime.now(timezone.utc).replace(tzinfo=None)

    listing = _get_listing(lid)
    assert getattr(listing, "consecutive_misses", None) == 3, (
        f"Counter must reach 3 (got {getattr(listing, 'consecutive_misses', None)})"
    )
    assert listing.is_active is False, (
        "Listing absent 3× in a row must be flipped to is_active=False"
    )
    assert listing.deactivated_at is not None, (
        "deactivated_at must be set at threshold crossing"
    )
    # Normalize possible tz-awareness coming out of SQLite
    da = listing.deactivated_at
    if da.tzinfo is not None:
        da = da.replace(tzinfo=None)
    assert before <= da <= after, (
        f"deactivated_at ({da}) should be within the call window [{before}, {after}]"
    )
    print("✓ test_absent_third_time_deactivates_at_threshold")


def test_re_appearance_resets_counter_and_clears_deactivation() -> None:
    """A listing that was deactivated (counter=3) and re-appears → reset to 0.

    NOTE: ``mark_inactive()`` itself only RESETS the counter and the
    ``deactivated_at``/``is_active`` clearing is handled by
    ``upsert_listing()`` when the listing comes back. This test asserts
    only the counter-reset half of the contract for mark_inactive.
    """
    _setup_in_memory_db()
    lid = _insert_listing(
        source="zillow",
        external_id="555",
        is_active=False,
        consecutive_misses=5,
        deactivated_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    # The listing is back in the scrape results this time
    mark_inactive("zillow", ["555"])
    listing = _get_listing(lid)
    assert getattr(listing, "consecutive_misses", None) == 0, (
        f"Counter must reset to 0 when listing is seen again "
        f"(got {getattr(listing, 'consecutive_misses', None)})"
    )
    print("✓ test_re_appearance_resets_counter_and_clears_deactivation")


def test_other_source_unaffected() -> None:
    """``mark_inactive('zillow', …)`` must NOT touch craigslist listings."""
    _setup_in_memory_db()
    z_id = _insert_listing(source="zillow", external_id="zz1", consecutive_misses=0)
    c_id = _insert_listing(source="craigslist", external_id="cc1", consecutive_misses=0)
    # Run zillow mark_inactive with an empty active set → zz1 increments
    mark_inactive("zillow", ["999"])
    z_listing = _get_listing(z_id)
    c_listing = _get_listing(c_id)
    assert getattr(z_listing, "consecutive_misses", None) == 1
    assert getattr(c_listing, "consecutive_misses", None) == 0, (
        "Craigslist listings must NOT be touched by a zillow mark_inactive call"
    )
    assert c_listing.is_active is True
    print("✓ test_other_source_unaffected")


def test_listing_source_is_active_flipped_at_threshold() -> None:
    """ListingSource.is_active must also flip when the Listing crosses the threshold."""
    _setup_in_memory_db()
    lid = _insert_listing(
        source="zillow", external_id="777", consecutive_misses=2
    )
    mark_inactive("zillow", ["999"])  # 3rd miss → cross threshold
    with database_module.get_session() as session:
        ls = (
            session.query(ListingSource)
            .filter_by(source="zillow", external_id="777")
            .one()
        )
        assert ls.is_active is False, (
            "ListingSource.is_active must follow Listing.is_active at threshold"
        )
    print("✓ test_listing_source_is_active_flipped_at_threshold")


def test_listing_source_stays_active_below_threshold() -> None:
    """ListingSource.is_active must STAY active while below threshold."""
    _setup_in_memory_db()
    lid = _insert_listing(
        source="zillow", external_id="888", consecutive_misses=0
    )
    mark_inactive("zillow", ["999"])  # 1st miss → counter=1, no deactivation
    with database_module.get_session() as session:
        ls = (
            session.query(ListingSource)
            .filter_by(source="zillow", external_id="888")
            .one()
        )
        assert ls.is_active is True, (
            "ListingSource must stay active while Listing is still active"
        )
    print("✓ test_listing_source_stays_active_below_threshold")


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------


def _run_all_tests() -> tuple[int, int]:
    tests = [
        fn for name, fn in globals().items()
        if name.startswith("test_") and callable(fn)
    ]
    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as exc:
            failed += 1
            print(f"✗ {test.__name__}: {exc}")
        except Exception:
            failed += 1
            print(f"✗ {test.__name__} (unexpected exception):")
            traceback.print_exc()
    return passed, failed


def main() -> int:
    passed, failed = _run_all_tests()
    total = passed + failed
    print(f"\n{passed}/{total} passed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
