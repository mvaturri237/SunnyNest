#!/usr/bin/env python3
"""One-shot backfill: merge cross-source duplicate clusters that exist in the
production database but were never merged because of the IntegrityError bug
in :mod:`src.dedup` (silently swallowed for ~6 weeks — see commit history).

The fix in :mod:`src.dedup` only triggers on **new** INSERTs.  Listings that
were inserted while the bug was live are sitting in the DB as un-merged
duplicate clusters.  This script finds those clusters and merges them by
calling the now-fixed :func:`find_and_merge_duplicate` once per non-canonical
listing in each cluster.

Usage
-----
Dry run (default — no DB writes, just prints the plan)::

    .venv/bin/python scripts/backfill_dedup.py
    .venv/bin/python scripts/backfill_dedup.py --dry-run        # explicit

Real merge (commits one transaction per cluster — failures are isolated)::

    .venv/bin/python scripts/backfill_dedup.py --apply
    .venv/bin/python scripts/backfill_dedup.py --no-dry-run     # alias

Idempotent: re-running after a successful merge finds nothing to do.
"""

from __future__ import annotations

import argparse
import logging
import sys
import traceback
from collections import defaultdict
from pathlib import Path
from typing import Any

# Ensure project root is importable when run as ``python scripts/backfill_dedup.py``.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.database import get_session
from src.dedup import (
    DEDUP_THRESHOLD,
    compute_duplicate_score,
    find_and_merge_duplicate,
    normalize_address,
)
from src.models import Listing, ListingSource

logger = logging.getLogger("backfill_dedup")


# ---------------------------------------------------------------------------
# Cluster discovery
# ---------------------------------------------------------------------------


def _listing_to_data(listing: Listing) -> dict[str, Any]:
    """Reconstruct the ``listing_data`` dict that ``find_and_merge_duplicate``
    expects, sourced from the listing's primary :class:`ListingSource` row.

    For a backfill, ``source`` and ``external_id`` MUST come from the
    ``listing_sources`` table (not ``Listing.source`` / ``Listing.external_id``
    which are the deprecated columns) — this is what makes the downstream
    "find existing source row by (source, external_id)" reassignment in
    :func:`src.dedup._merge_duplicate` work.
    """
    # Pick the listing's source row matching its own deprecated source/external_id
    primary_source = next(
        (
            s for s in listing.sources
            if s.source == listing.source and s.external_id == listing.external_id
        ),
        None,
    )
    if primary_source is None and listing.sources:
        # Fallback: take the first source row (shouldn't happen post-migration)
        primary_source = listing.sources[0]

    if primary_source is None:
        # Truly orphaned listing with no source rows — fall back to the
        # deprecated columns.  ``_merge_duplicate``'s defensive fallback
        # branch will handle this.
        source = listing.source
        external_id = listing.external_id
        url = listing.url or ""
    else:
        source = primary_source.source
        external_id = primary_source.external_id
        url = primary_source.url or listing.url or ""

    return {
        "source": source,
        "external_id": external_id,
        "url": url,
        "title": listing.title,
        "address": listing.address,
        "city": listing.city,
        "zip_code": listing.zip_code,
        "price": listing.price,
        "bedrooms": listing.bedrooms,
        "bathrooms": listing.bathrooms,
        "sqft": listing.sqft,
        "property_type": listing.property_type,
        "listed_date": listing.listed_date,
        # Optional gap-fill fields
        "description": listing.description,
        "image_urls": listing.image_urls,
        "pet_friendly": listing.pet_friendly,
        "parking": listing.parking,
        "laundry": listing.laundry,
        "ac": listing.ac,
        "furnished": listing.furnished,
        "neighborhood": listing.neighborhood,
    }


def _build_clusters(listings: list[Listing]) -> list[list[Listing]]:
    """Group listings into duplicate clusters.

    Strategy:
      1. Bucket by ``(normalize_address(address), zip_code)`` to bound the
         pairwise scoring work.  Listings with no address or no zip are
         skipped (they can never be confidently matched).
      2. Within each bucket of size > 1, build clusters with a Union-Find
         pass: any two listings whose ``compute_duplicate_score`` ≥
         :data:`DEDUP_THRESHOLD` get unified.
      3. Return clusters of size > 1.

    This mirrors how the production dedup runs — same scoring function,
    same threshold — so the backfill output is consistent with what
    happens for new listings going forward.
    """
    buckets: dict[tuple[str, str], list[Listing]] = defaultdict(list)
    for listing in listings:
        addr_norm = normalize_address(listing.address or "")
        zip_code = listing.zip_code or ""
        if not addr_norm or not zip_code:
            continue
        buckets[(addr_norm, zip_code)].append(listing)

    clusters: list[list[Listing]] = []

    for bucket_listings in buckets.values():
        if len(bucket_listings) < 2:
            continue

        # Union-Find over the bucket
        n = len(bucket_listings)
        parent = list(range(n))

        def find(i: int) -> int:
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        def union(i: int, j: int) -> None:
            ri, rj = find(i), find(j)
            if ri != rj:
                parent[ri] = rj

        for i in range(n):
            data_i = _listing_to_data(bucket_listings[i])
            for j in range(i + 1, n):
                # Skip same-source pairs — dedup is cross-source only
                if bucket_listings[i].source == bucket_listings[j].source:
                    continue
                score = compute_duplicate_score(data_i, bucket_listings[j])
                if score >= DEDUP_THRESHOLD:
                    union(i, j)

        groups: dict[int, list[Listing]] = defaultdict(list)
        for i in range(n):
            groups[find(i)].append(bucket_listings[i])

        for group in groups.values():
            if len(group) > 1:
                clusters.append(group)

    return clusters


def _pick_canonical(cluster: list[Listing]) -> Listing:
    """Pick the listing with the earliest ``first_seen`` as the canonical.

    The production DB contains a mix of timezone-naive (legacy migrated rows)
    and timezone-aware (post-migration rows) ``first_seen`` values, so we
    normalize to a comparable POSIX timestamp before sorting.  ``None`` is
    treated as "very late" so it loses tie-breaks; final tie-break is the
    listing ``id`` (lower id wins → earlier insert).
    """
    from datetime import timezone as _tz

    def sort_key(lst: Listing) -> tuple[bool, float, int]:
        fs = lst.first_seen
        if fs is None:
            return (True, 0.0, lst.id)
        if fs.tzinfo is None:
            fs = fs.replace(tzinfo=_tz.utc)
        return (False, fs.timestamp(), lst.id)

    return min(cluster, key=sort_key)


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def _format_listing_brief(lst: Listing) -> str:
    fs = lst.first_seen.strftime("%Y-%m-%d %H:%M:%S") if lst.first_seen else "?"
    return f"id={lst.id} {lst.source} (first_seen={fs})"


def _print_cluster_plan(idx: int, cluster: list[Listing], canonical: Listing) -> None:
    addr = cluster[0].address
    zip_code = cluster[0].zip_code
    print(f"\nCluster {idx}: {addr}, {zip_code} — {len(cluster)} listings")
    print(f"  canonical: {_format_listing_brief(canonical)}")
    for lst in cluster:
        if lst.id == canonical.id:
            continue
        print(f"  merge:     id={lst.id} {lst.source:<11} → {canonical.id}")


# ---------------------------------------------------------------------------
# Apply / dry-run
# ---------------------------------------------------------------------------


def _apply_cluster(cluster: list[Listing], canonical: Listing) -> tuple[int, list[str]]:
    """Apply merges for a single cluster.

    Transaction granularity: **one transaction per merge** (not per cluster).
    Each merge runs in its own ``get_session()`` context — so within a 3-listing
    cluster, if merging the 2nd listing succeeds and the 3rd raises, the 2nd
    merge stays committed and only the 3rd is rolled back. The cluster ends up
    partially merged.

    This is intentional: a single bad row should not roll back successful
    merges in the same cluster, and the script is **idempotent** — re-running
    ``backfill_dedup.py --apply`` will pick up any stranded listings that were
    skipped due to per-row failures (the per-merge session also keeps
    SQLAlchemy state clean for ``find_and_merge_duplicate``'s
    ``session.refresh`` / ``session.delete`` calls on the dup).

    Returns ``(merged_count, skip_reasons)``.
    """
    merged = 0
    skipped: list[str] = []

    for stale_lst in cluster:
        if stale_lst.id == canonical.id:
            continue

        # Per-merge isolation (see docstring): one fresh session per merge,
        # so a failure on this row does not roll back previously-merged rows
        # in the same cluster. Re-run the script to pick up stragglers.
        try:
            with get_session() as session:
                dup = session.get(Listing, stale_lst.id)
                if dup is None:
                    skipped.append(
                        f"id={stale_lst.id}: listing already gone (concurrent merge?)"
                    )
                    continue

                listing_data = _listing_to_data(dup)
                result = find_and_merge_duplicate(
                    session=session,
                    listing=dup,
                    listing_data=listing_data,
                )
                if result is None:
                    skipped.append(
                        f"id={stale_lst.id}: find_and_merge_duplicate returned None "
                        f"(no duplicate detected by production scoring — score < "
                        f"{DEDUP_THRESHOLD}, despite same address bucket)"
                    )
                    continue
                if result.id != canonical.id:
                    skipped.append(
                        f"id={stale_lst.id}: merged into id={result.id} "
                        f"(not the planned canonical id={canonical.id})"
                    )
                    # Still counts as merged
                merged += 1
                print(
                    f"  Merged listing #{stale_lst.id} ({stale_lst.source}) → "
                    f"canonical #{result.id} ({result.source})"
                )
        except Exception as exc:  # noqa: BLE001 — backfill must keep going
            skipped.append(f"id={stale_lst.id}: {type(exc).__name__}: {exc}")
            traceback.print_exc()

    return merged, skipped


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Backfill cross-source duplicate merges in the production DB.",
    )
    apply_group = parser.add_mutually_exclusive_group()
    apply_group.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        default=True,
        help="Plan-only — print clusters and planned merges, no DB writes (default).",
    )
    apply_group.add_argument(
        "--apply",
        dest="dry_run",
        action="store_false",
        help="Actually perform the merges (one transaction per cluster).",
    )
    apply_group.add_argument(
        "--no-dry-run",
        dest="dry_run",
        action="store_false",
        help="Alias for --apply.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Verbose logging (sets src.dedup logger to INFO).",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    mode_label = "DRY RUN" if args.dry_run else "APPLY"
    print(f"=== Backfill Dedup ({mode_label}) ===")
    print(f"Threshold: score ≥ {DEDUP_THRESHOLD}")

    # 1. Fetch all active listings + their sources
    with get_session() as session:
        listings = (
            session.query(Listing)
            .filter(Listing.is_active == True)  # noqa: E712
            .all()
        )
        # Force-load each listing's sources while still inside the session
        # context (otherwise lazy attribute access raises DetachedInstanceError).
        for lst in listings:
            _ = list(lst.sources)
            session.expunge(lst)

    print(f"Active listings scanned: {len(listings)}")

    # 2. Build clusters
    clusters = _build_clusters(listings)
    # Sort clusters by canonical id for stable output
    clusters_with_canonical = [(c, _pick_canonical(c)) for c in clusters]
    clusters_with_canonical.sort(key=lambda pair: pair[1].id)

    if not clusters_with_canonical:
        print("\nNo cross-source duplicate clusters found. Nothing to do.")
        return 0

    # 3. Print the plan
    total_to_merge = 0
    for idx, (cluster, canonical) in enumerate(clusters_with_canonical, start=1):
        _print_cluster_plan(idx, cluster, canonical)
        total_to_merge += len(cluster) - 1

    print(
        f"\n{len(clusters_with_canonical)} clusters, "
        f"{total_to_merge} rows would be merged."
    )

    if args.dry_run:
        print("\n[DRY RUN] No changes written.  Re-run with --apply to perform merges.")
        return 0

    # 4. Apply
    print("\n--- Applying merges ---")
    total_merged = 0
    total_skipped: list[str] = []

    for idx, (cluster, canonical) in enumerate(clusters_with_canonical, start=1):
        print(f"\nCluster {idx} (canonical id={canonical.id}):")
        merged, skipped = _apply_cluster(cluster, canonical)
        total_merged += merged
        total_skipped.extend(skipped)

    # 5. Summary
    print("\n=== Summary ===")
    print(f"Clusters found:    {len(clusters_with_canonical)}")
    print(f"Rows merged:       {total_merged}")
    print(f"Rows skipped:      {len(total_skipped)}")
    if total_skipped:
        print("\nSkip reasons:")
        for reason in total_skipped:
            print(f"  - {reason}")

    return 0 if not total_skipped else 1


if __name__ == "__main__":
    sys.exit(main())
