"""One-shot stop-the-bleed: deactivate the known-stale zpid 19615280 row.

Background
----------
On 2026-06-04 Debug mode identified listing id=327 (zpid 19615280,
1525 Bittern Dr, Sunnyvale) as a stale "rental" row — actually
off-market / for sale at $2.98M on Zillow.com today. The Bug A
``normalize()`` status guard and the Bug B ``mark_inactive`` hysteresis
counter both ship in the same diff as this script, but neither is
retroactive: the row stays ``is_active=1`` in the production DB until
either (a) 3 more daily scrapes pass without seeing it OR (b) we run
this script.

This script does (b). It is idempotent and dry-run by default — pass
``--apply`` to commit. Pair with the Bug A/B fix so it never has to be
run again.

Run::

    .venv/bin/python scripts/deactivate_stale_zillow.py           # dry-run
    .venv/bin/python scripts/deactivate_stale_zillow.py --apply   # commit

Exit code 0 on success (including no-op), 1 on error.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure project root is importable
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.database import get_session
from src.models import Listing, ListingSource


# ---------------------------------------------------------------------------
# Target — keep the data tiny and obvious so a future grep finds it.
# ---------------------------------------------------------------------------

STALE_LISTING_ID = 327
STALE_ZPID = "19615280"
STALE_SOURCE = "zillow"


def _summarize(prefix: str) -> dict[str, object]:
    """Snapshot the current state of the target row + counts. Read-only."""
    with get_session() as session:
        listing = session.get(Listing, STALE_LISTING_ID)
        if listing is None:
            return {
                "prefix": prefix,
                "found": False,
                "active_zillow_total": (
                    session.query(Listing)
                    .filter(Listing.source == STALE_SOURCE, Listing.is_active == True)  # noqa: E712
                    .count()
                ),
            }

        # Pull all fields we care about before the session closes
        return {
            "prefix": prefix,
            "found": True,
            "id": listing.id,
            "external_id": listing.external_id,
            "address": listing.address,
            "price": listing.price,
            "is_active": listing.is_active,
            "deactivated_at": listing.deactivated_at,
            "consecutive_misses": getattr(listing, "consecutive_misses", None),
            "active_zillow_total": (
                session.query(Listing)
                .filter(Listing.source == STALE_SOURCE, Listing.is_active == True)  # noqa: E712
                .count()
            ),
        }


def _print_snapshot(snap: dict[str, object]) -> None:
    print(f"--- {snap['prefix']} ---")
    if not snap["found"]:
        print(
            f"  Listing id={STALE_LISTING_ID} NOT FOUND — nothing to do "
            "(idempotent: previous run already deleted/migrated this row)."
        )
        print(
            f"  Total active zillow listings: {snap['active_zillow_total']}"
        )
        return
    print(f"  id                 : {snap['id']}")
    print(f"  external_id (zpid) : {snap['external_id']}")
    print(f"  address            : {snap['address']}")
    print(f"  price              : {snap['price']}")
    print(f"  is_active          : {snap['is_active']}")
    print(f"  deactivated_at     : {snap['deactivated_at']}")
    print(f"  consecutive_misses : {snap['consecutive_misses']}")
    print(f"  Total active zillow listings: {snap['active_zillow_total']}")


def deactivate(apply: bool) -> int:
    """Run the deactivation. Return process exit code."""
    print(
        f"Target: listings.id={STALE_LISTING_ID} "
        f"(zpid {STALE_ZPID}, source={STALE_SOURCE})\n"
        f"Mode  : {'APPLY (will commit)' if apply else 'DRY-RUN (no commit)'}\n"
    )

    before = _summarize("BEFORE")
    _print_snapshot(before)

    if not before["found"]:
        return 0

    if before.get("is_active") is False:
        print(
            "\nListing is already is_active=False — nothing to do (idempotent)."
        )
        return 0

    if not apply:
        print(
            "\nDRY-RUN: would set is_active=False, deactivated_at=<now UTC>, "
            "and mirror is_active=False onto matching ListingSource rows.\n"
            "Re-run with --apply to commit."
        )
        return 0

    # --- APPLY ---
    now_utc = datetime.now(timezone.utc)
    with get_session() as session:
        listing = session.get(Listing, STALE_LISTING_ID)
        if listing is None:
            # Disappeared between snapshots — treat as no-op success
            print("Listing disappeared between snapshots — no-op.")
            return 0

        # Sanity guard: confirm we're touching the right row before flipping
        if listing.external_id != STALE_ZPID or listing.source != STALE_SOURCE:
            print(
                f"\nABORT: id={STALE_LISTING_ID} has source={listing.source!r}, "
                f"external_id={listing.external_id!r} — does NOT match "
                f"expected ({STALE_SOURCE!r}, {STALE_ZPID!r}). Not touching."
            )
            return 1

        listing.is_active = False
        listing.deactivated_at = now_utc

        # Mirror onto ListingSource(s) for the same (source, external_id)
        matching_sources = (
            session.query(ListingSource)
            .filter(
                ListingSource.source == STALE_SOURCE,
                ListingSource.external_id == STALE_ZPID,
            )
            .all()
        )
        for ls in matching_sources:
            ls.is_active = False
        print(
            f"\nMirrored is_active=False onto {len(matching_sources)} "
            f"matching listing_sources row(s)."
        )

    print("Commit successful.\n")
    after = _summarize("AFTER")
    _print_snapshot(after)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Deactivate the known-stale Zillow listing id=327 / zpid 19615280 "
            "(1525 Bittern Dr, Sunnyvale) — off-market on Zillow.com but still "
            "active in our DB. Dry-run by default; pass --apply to commit."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Commit changes. Without this flag the script is read-only.",
    )
    args = parser.parse_args()

    try:
        return deactivate(apply=args.apply)
    except Exception as exc:
        print(f"ERROR: {exc!r}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
