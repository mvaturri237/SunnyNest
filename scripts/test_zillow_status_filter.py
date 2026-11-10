"""Unit tests for the Zillow scraper status-validation filter (Bug A).

Background
----------
On 2026-06-04 a stale Zillow listing (zpid 19615280, 1525 Bittern Dr) was
discovered in the dashboard as a $6,200/mo "rental" — but the property
is actually off-market / for sale at $2.98M on Zillow.com.

Root cause (verified by Debug mode): we send ``listingStatus=For_Rent``
as a *request parameter* but never re-check the *response* status fields.
The RapidAPI provider's filter is flaky and occasionally returns
off-market / for-sale rows.

Fix (this test asserts): :func:`ZillowScraper.normalize` must defensively
inspect ``property.listing.listingStatus`` (expect ``"forRent"``,
case-insensitive) and ``property.listing.marketingStatus`` (expect
``"active"``). When either fails the check, ``normalize()`` returns
``None`` so the orchestrator skips the listing entirely.

Run::

    .venv/bin/python scripts/test_zillow_status_filter.py

Exit code 0 = pass, 1 = fail.
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

# Ensure project root is importable when run as ``python scripts/test_zillow_status_filter.py``
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.scrapers.zillow_scraper import ZillowScraper


# ---------------------------------------------------------------------------
# Fixtures — minimal-but-valid raw RapidAPI item shape
# ---------------------------------------------------------------------------


def _make_raw_item(
    *,
    listing_status: str | None = "forRent",
    marketing_status: str | None = "active",
    include_listing_subdict: bool = True,
    zpid: int = 19537447,
) -> dict:
    """Build a minimal raw item matching the ZLLW Working API shape.

    Mirrors the structure captured at /tmp/sample_raw.json (Debug, 2026-06-04).
    """
    listing_sub: dict = {}
    if listing_status is not None:
        listing_sub["listingStatus"] = listing_status
    if marketing_status is not None:
        listing_sub["marketingStatus"] = marketing_status

    prop: dict = {
        "zpid": zpid,
        "address": {
            "streetAddress": "1070 Morningside Dr",
            "city": "Sunnyvale",
            "state": "CA",
            "zipcode": "94087",
        },
        "location": {"latitude": 37.36576, "longitude": -122.0545},
        "bedrooms": 3,
        "bathrooms": 3.0,
        "livingArea": 1496,
        "propertyType": "singleFamily",
        "price": {"value": 6000, "pricePerSquareFoot": 4},
        "daysOnZillow": 0,
    }
    if include_listing_subdict:
        prop["listing"] = listing_sub

    return {"property": prop, "resultType": "property"}


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


def test_valid_for_rent_active_returns_dict() -> None:
    """forRent + active → normalize returns a normalized dict (not None)."""
    scraper = ZillowScraper()
    raw = _make_raw_item(listing_status="forRent", marketing_status="active")
    result = scraper.normalize(raw)
    assert result is not None, "Valid forRent+active item should NOT be skipped"
    assert isinstance(result, dict), f"Expected dict, got {type(result).__name__}"
    assert result["external_id"] == "19537447"
    assert result["source"] == "zillow"
    assert result["price"] == 6000
    print("✓ test_valid_for_rent_active_returns_dict")


def test_valid_for_rent_active_case_insensitive() -> None:
    """Status comparison must be case-insensitive (defensive)."""
    scraper = ZillowScraper()
    raw = _make_raw_item(listing_status="FORRENT", marketing_status="ACTIVE")
    result = scraper.normalize(raw)
    assert result is not None, "Case-insensitive 'FORRENT'/'ACTIVE' should be accepted"
    print("✓ test_valid_for_rent_active_case_insensitive")


def test_for_sale_status_returns_none() -> None:
    """listingStatus='forSale' → normalize returns None (the live 1525 Bittern Dr bug)."""
    scraper = ZillowScraper()
    raw = _make_raw_item(listing_status="forSale", marketing_status="active")
    result = scraper.normalize(raw)
    assert result is None, (
        f"forSale item must be skipped (returned {type(result).__name__})"
    )
    print("✓ test_for_sale_status_returns_none")


def test_inactive_marketing_status_returns_none() -> None:
    """marketingStatus='inactive' → normalize returns None (off-market guard)."""
    scraper = ZillowScraper()
    raw = _make_raw_item(listing_status="forRent", marketing_status="inactive")
    result = scraper.normalize(raw)
    assert result is None, (
        f"marketingStatus=inactive item must be skipped (returned {type(result).__name__})"
    )
    print("✓ test_inactive_marketing_status_returns_none")


def test_missing_listing_subdict_returns_none() -> None:
    """Missing property.listing → normalize returns None (defensive)."""
    scraper = ZillowScraper()
    raw = _make_raw_item(include_listing_subdict=False)
    result = scraper.normalize(raw)
    assert result is None, (
        f"Missing property.listing must be skipped (returned {type(result).__name__})"
    )
    print("✓ test_missing_listing_subdict_returns_none")


def test_missing_listing_status_field_returns_none() -> None:
    """property.listing present but listingStatus missing → normalize returns None."""
    scraper = ZillowScraper()
    raw = _make_raw_item(listing_status=None, marketing_status="active")
    result = scraper.normalize(raw)
    assert result is None, (
        f"Missing listingStatus must be skipped (returned {type(result).__name__})"
    )
    print("✓ test_missing_listing_status_field_returns_none")


def test_missing_marketing_status_field_returns_none() -> None:
    """property.listing present but marketingStatus missing → normalize returns None."""
    scraper = ZillowScraper()
    raw = _make_raw_item(listing_status="forRent", marketing_status=None)
    result = scraper.normalize(raw)
    assert result is None, (
        f"Missing marketingStatus must be skipped (returned {type(result).__name__})"
    )
    print("✓ test_missing_marketing_status_field_returns_none")


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------


def _run_all_tests() -> tuple[int, int]:
    """Run every ``test_*`` callable in this module. Return (passed, failed)."""
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
