# Cross-Source Listing Deduplication System

> **Status**: Proposed  
> **Author**: Architect  
> **Date**: 2026-03-28  
> **Depends on**: [`src/models.py`](../src/models.py), [`src/database.py`](../src/database.py), [`src/orchestrator.py`](../src/orchestrator.py)

---

## 1. Problem Statement

SunnyNest scrapes rental listings from multiple sources (Zillow, Craigslist). The same physical property can appear on both sites with different [`external_id`](../src/models.py:71) values. Currently, deduplication only works **within a single source** via the [`(source, external_id)` unique constraint](../src/models.py:129). There is no mechanism to detect that a Zillow listing and a Craigslist listing refer to the same property.

**Impact**: Users see duplicate cards for the same property, inflating listing counts and cluttering the UI.

---

## 2. Schema Design

### 2.1 Option Analysis

| Option | Pros | Cons | Verdict |
|--------|------|------|---------|
| **A. JSON field on Listing** | No new table, simple migration | Hard to query/index, violates 1NF, can't enforce FK constraints | ❌ Rejected |
| **B. Separate `listing_sources` table** | Normalized, queryable, extensible, supports N sources per listing | Requires JOIN for source display, migration complexity | ✅ **Selected** |
| **C. `canonical_id` FK on Listing** | Minimal schema change, keeps all listings | Ambiguous which is "canonical", complex self-referential queries | ❌ Rejected |

### 2.2 Selected Design: `listing_sources` Table

A new `listing_sources` table stores one row per source-listing association. When a cross-source duplicate is detected, both source records point to the same canonical [`Listing.id`](../src/models.py:68).

```
┌──────────────────────┐       ┌──────────────────────────┐
│      listings         │       │    listing_sources        │
├──────────────────────┤       ├──────────────────────────┤
│ id (PK)              │◄──────│ listing_id (FK)           │
│ title                │       │ source (TEXT)              │
│ address              │       │ external_id (TEXT)         │
│ city                 │       │ url (TEXT)                 │
│ zip_code             │       │ first_seen (DATETIME)      │
│ price                │       │ last_seen (DATETIME)       │
│ bedrooms             │       │ is_active (BOOLEAN)        │
│ bathrooms            │       │                            │
│ sqft                 │       │ UNIQUE(source, external_id)│
│ ...                  │       └──────────────────────────┘
│ source (DEPRECATED)  │
│ external_id (DEPR.)  │
│ url (DEPRECATED)     │
└──────────────────────┘
```

### 2.3 New Model: `ListingSource`

```python
class ListingSource(Base):
    """Maps a listing to one or more external source records.
    
    A single physical property (Listing) can have multiple source
    records — one from Zillow, one from Craigslist, etc.
    """
    __tablename__ = "listing_sources"

    id = Column(Integer, primary_key=True, autoincrement=True)
    listing_id = Column(Integer, ForeignKey("listings.id"), nullable=False, index=True)
    source = Column(Text, nullable=False)        # "zillow" | "craigslist"
    external_id = Column(Text, nullable=False)    # source-specific ID
    url = Column(Text, nullable=False)            # direct link to source listing
    first_seen = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    last_seen = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    is_active = Column(Boolean, nullable=False, default=True)

    listing = relationship("Listing", back_populates="sources")

    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_ls_source_external_id"),
    )
```

### 2.4 Listing Model Changes

Add a relationship and keep legacy fields for backward compatibility during migration:

```python
class Listing(Base):
    # ... existing fields ...
    
    # NEW: relationship to source records
    sources = relationship("ListingSource", back_populates="listing",
                          cascade="all, delete-orphan",
                          order_by="ListingSource.source")
    
    # DEPRECATED but kept for migration period:
    # source, external_id, url — will be removed in a future migration
```

### 2.5 Migration Strategy

Non-destructive, idempotent migration (consistent with the existing [`_ensure_days_on_market_column()`](../src/database.py:71) pattern):

1. **Phase 1**: Create `listing_sources` table via `Base.metadata.create_all()`
2. **Phase 2**: Backfill — for each existing listing, insert a `ListingSource` row copying `source`, `external_id`, `url`, `first_seen`, `last_seen`, `is_active`
3. **Phase 3**: Update all read paths to use `listing.sources` instead of `listing.source`
4. **Phase 4** (future): Drop deprecated columns from `listings` table

```python
def _migrate_to_listing_sources() -> None:
    """Backfill listing_sources from existing listings.source/external_id/url."""
    engine = get_engine()
    with engine.connect() as conn:
        # Check if migration already done (listing_sources has rows)
        result = conn.execute(text("SELECT COUNT(*) FROM listing_sources"))
        if result.scalar() > 0:
            return  # Already migrated
        
        conn.execute(text("""
            INSERT INTO listing_sources (listing_id, source, external_id, url, first_seen, last_seen, is_active)
            SELECT id, source, external_id, url, first_seen, last_seen, is_active
            FROM listings
            WHERE source IS NOT NULL AND external_id IS NOT NULL
        """))
        conn.commit()
    logger.info("Backfilled listing_sources from existing listings.")
```

---

## 3. Matching Algorithm

### 3.1 Matching Fields & Weights

Cross-source matching uses a **multi-signal scoring** approach. Each signal contributes a score; if the total exceeds a threshold, the listings are considered duplicates.

| Signal | Weight | Match Condition | Rationale |
|--------|--------|----------------|-----------|
| **Normalized address** | 40 | Exact match after normalization | Strongest signal — same address = same property |
| **ZIP code** | 10 | Exact match | Confirms same area |
| **Price** | 15 | Within 5% of each other | Same property often listed at same/similar price |
| **Bedrooms** | 15 | Exact match | Structural — doesn't change between sources |
| **Bathrooms** | 10 | Exact match | Structural — doesn't change between sources |
| **Sqft** | 10 | Within 10% of each other (if both non-null) | May vary slightly between sources |

**Threshold**: Score ≥ 75 → **duplicate**. This requires at minimum: address match (40) + ZIP (10) + bedrooms (15) + bathrooms (10) = 75.

### 3.2 Address Normalization

Addresses from different sources have formatting differences. The normalizer must handle:

| Variation | Example | Normalized |
|-----------|---------|------------|
| Directional abbreviations | "N", "N.", "North" | "n" |
| Street type abbreviations | "Dr", "Dr.", "Drive" | "dr" |
| Unit/Apt designators | "Apt 2B", "Unit 2B", "#2B" | "apt 2b" |
| Extra whitespace | "123  Main   St" | "123 main st" |
| Trailing city/state | "123 Main St, Sunnyvale, CA" | "123 main st" |
| Periods after abbreviations | "St.", "Ave." | "st", "ave" |

```python
import re

# Standard USPS abbreviation mappings
_STREET_TYPE_MAP = {
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

_DIRECTIONAL_MAP = {
    "north": "n", "south": "s", "east": "e", "west": "w",
    "northeast": "ne", "northwest": "nw",
    "southeast": "se", "southwest": "sw",
}

_UNIT_PATTERN = re.compile(
    r"\b(apt|apartment|unit|suite|ste|#)\s*\.?\s*\w+$", re.IGNORECASE
)


def normalize_address(address: str) -> str:
    """Normalize an address for deduplication matching.
    
    Returns a lowercase, stripped, standardized address string.
    """
    if not address:
        return ""
    
    # Lowercase and strip
    addr = address.lower().strip()
    
    # Remove trailing city/state/zip (after last comma)
    # e.g., "123 Main St, Sunnyvale, CA 94086" → "123 Main St"
    parts = addr.split(",")
    addr = parts[0].strip()
    
    # Remove periods
    addr = addr.replace(".", "")
    
    # Collapse whitespace
    addr = re.sub(r"\s+", " ", addr)
    
    # Normalize directionals
    tokens = addr.split()
    normalized_tokens = []
    for token in tokens:
        token = _DIRECTIONAL_MAP.get(token, token)
        token = _STREET_TYPE_MAP.get(token, token)
        normalized_tokens.append(token)
    
    addr = " ".join(normalized_tokens)
    
    # Remove unit/apt designators for matching
    # (two listings for same property may omit or include unit)
    addr = _UNIT_PATTERN.sub("", addr).strip()
    
    return addr
```

### 3.3 Candidate Selection (Performance Optimization)

Running the matching algorithm against **all** existing listings for every new listing would be O(N²). Instead, we use a **candidate narrowing** strategy:

```
Step 1: Filter by zip_code (exact match) — narrows to ~20-50 listings
Step 2: Filter by bedrooms (exact match) — narrows to ~5-15 listings  
Step 3: Score remaining candidates with full algorithm
```

This is implemented as a SQL query:

```python
def find_duplicate_candidates(
    session: Session,
    zip_code: str,
    bedrooms: int,
    source: str,
    external_id: str,
) -> list[Listing]:
    """Find listings that could be duplicates (different source, same zip+beds)."""
    return (
        session.query(Listing)
        .join(ListingSource)
        .filter(
            Listing.zip_code == zip_code,
            Listing.bedrooms == bedrooms,
            Listing.is_active == True,  # noqa: E712
            # Exclude the listing's own source record
            ~Listing.sources.any(
                and_(
                    ListingSource.source == source,
                    ListingSource.external_id == external_id,
                )
            ),
        )
        .all()
    )
```

### 3.4 Scoring Function

```python
def compute_duplicate_score(listing_a: dict, listing_b: Listing) -> int:
    """Compute a similarity score between a new listing dict and an existing Listing.
    
    Returns a score from 0-100. Score >= 75 indicates a likely duplicate.
    """
    score = 0
    
    # Address (40 points)
    addr_a = normalize_address(listing_a.get("address", ""))
    addr_b = normalize_address(listing_b.address or "")
    if addr_a and addr_b and addr_a == addr_b:
        score += 40
    
    # ZIP code (10 points)
    if listing_a.get("zip_code") == listing_b.zip_code:
        score += 10
    
    # Price (15 points) — within 5%
    price_a = listing_a.get("price", 0)
    price_b = listing_b.price or 0
    if price_a > 0 and price_b > 0:
        ratio = min(price_a, price_b) / max(price_a, price_b)
        if ratio >= 0.95:
            score += 15
    
    # Bedrooms (15 points)
    if listing_a.get("bedrooms") == listing_b.bedrooms:
        score += 15
    
    # Bathrooms (10 points)
    if listing_a.get("bathrooms") == listing_b.bathrooms:
        score += 10
    
    # Sqft (10 points) — within 10%
    sqft_a = listing_a.get("sqft")
    sqft_b = listing_b.sqft
    if sqft_a and sqft_b and sqft_a > 0 and sqft_b > 0:
        ratio = min(sqft_a, sqft_b) / max(sqft_a, sqft_b)
        if ratio >= 0.90:
            score += 10
    
    return score
```

---

## 4. Merge Strategy

### 4.1 Canonical Listing Selection

When a duplicate is detected, we must decide which listing to keep as the **canonical** record. The other listing's source record is merged into the canonical listing.

**Rule**: The **existing** listing in the database is always canonical. The newly-scraped duplicate adds its source record to the existing listing.

Rationale:
- The existing listing already has `first_seen`, `price_history`, `is_favorite`, `is_disliked` state
- Avoids moving price history records between listings
- Simpler — no need to decide "which source is better"

### 4.2 Merge Behavior

When listing B (new) is detected as a duplicate of listing A (existing):

| Field | Action | Rationale |
|-------|--------|-----------|
| **Source records** | Add B's source/external_id/url to A's `listing_sources` | Preserves both source links |
| **Price** | Keep A's price; record B's price in `price_history` if different | A is canonical; price diff is tracked |
| **Title** | Keep A's title | Arbitrary — both are valid |
| **Address** | Keep A's address | Already normalized and geocoded |
| **Sqft** | Use B's if A's is NULL | Fill gaps from richer source |
| **Description** | Use B's if A's is NULL | Fill gaps from richer source |
| **Image URLs** | Merge (union of both, deduplicated) | More images = better |
| **Amenities** | Use B's values for any NULL fields in A | Fill gaps |
| **Lat/Lng** | Keep A's (already geocoded) | Avoid re-geocoding |
| **is_favorite / is_disliked** | Keep A's | User preferences must not be lost |
| **Notification** | Do NOT re-notify | User already saw this property |

### 4.3 Merge Function Pseudocode

```python
def merge_duplicate(
    session: Session,
    canonical: Listing,
    duplicate_data: dict[str, Any],
) -> None:
    """Merge a duplicate listing's data into the canonical listing.
    
    Adds the duplicate's source record to the canonical listing and
    fills in any missing data fields.
    """
    # 1. Add source record
    new_source = ListingSource(
        listing_id=canonical.id,
        source=duplicate_data["source"],
        external_id=duplicate_data["external_id"],
        url=duplicate_data["url"],
    )
    session.add(new_source)
    
    # 2. Fill NULL fields from duplicate (gap-filling)
    _GAP_FILL_FIELDS = [
        "sqft", "sqm", "description", "pet_friendly", "parking",
        "laundry", "ac", "furnished", "neighborhood",
    ]
    for field in _GAP_FILL_FIELDS:
        if getattr(canonical, field) is None and duplicate_data.get(field) is not None:
            setattr(canonical, field, duplicate_data[field])
    
    # 3. Merge image URLs (union)
    existing_images = json.loads(canonical.image_urls or "[]")
    new_images = json.loads(duplicate_data.get("image_urls", "[]") or "[]")
    merged = list(dict.fromkeys(existing_images + new_images))  # deduplicate, preserve order
    canonical.image_urls = json.dumps(merged)
    
    # 4. Record price snapshot if price differs
    if duplicate_data.get("price") and duplicate_data["price"] != canonical.price:
        record_price_snapshot(canonical.id, duplicate_data["price"])
    
    # 5. Update last_seen
    canonical.last_seen = datetime.now(timezone.utc)
    
    logger.info(
        "Merged duplicate: %s/%s → canonical listing #%d",
        duplicate_data["source"],
        duplicate_data["external_id"],
        canonical.id,
    )
```

---

## 5. Integration Design

### 5.1 Pipeline Position

Deduplication runs **after** the existing [`upsert_listing()`](../src/database.py:244) call in the orchestrator's processing loop. This preserves the existing same-source dedup behavior and adds cross-source dedup as a second pass.

```
┌─────────────────────────────────────────────────────────┐
│                  Orchestrator Pipeline                    │
│                                                          │
│  1. Scrape (concurrent)                                  │
│  2. Normalize (per-source adapter)                       │
│  3. Filter ($0 prices, non-house types)                  │
│  4. Enrich (geocode, school district, sqm)               │
│  5. Upsert (same-source dedup via source+external_id)    │
│  6. ★ Cross-source dedup (NEW) ★                         │
│  7. Price snapshot recording                             │
│  8. Mark inactive                                        │
│  9. Notification (via scheduled service)                 │
└─────────────────────────────────────────────────────────┘
```

### 5.2 Integration into [`ScraperOrchestrator.run_sync()`](../src/orchestrator.py:39)

The dedup check runs **only for newly inserted listings** (`is_new == True`). Updated listings already exist in the DB and were either already deduped or are same-source updates.

```python
# In the orchestrator's per-listing processing loop, after step 5 (upsert):

if is_new:
    # Step 6: Cross-source dedup check
    duplicate_of = find_and_merge_duplicate(
        normalized_data=normalized,
        new_listing=listing,
    )
    if duplicate_of is not None:
        # This listing was merged into an existing one
        # Don't count it as "new" for notification purposes
        new_count -= 1
        updated_count += 1
        # Use the canonical listing for price snapshot
        listing = duplicate_of
    else:
        new_count += 1
        all_new_listings.append(normalized)
```

### 5.3 The `find_and_merge_duplicate()` Function

```python
def find_and_merge_duplicate(
    normalized_data: dict[str, Any],
    new_listing: Listing,
) -> Listing | None:
    """Check if a newly inserted listing is a cross-source duplicate.
    
    If a duplicate is found:
    1. Merge the new listing's source into the canonical listing
    2. Delete the new listing row (it was just inserted by upsert)
    3. Return the canonical listing
    
    If no duplicate found, return None.
    """
    DEDUP_THRESHOLD = 75
    
    with get_session() as session:
        candidates = find_duplicate_candidates(
            session=session,
            zip_code=normalized_data.get("zip_code", ""),
            bedrooms=normalized_data.get("bedrooms", 0),
            source=normalized_data["source"],
            external_id=normalized_data["external_id"],
        )
        
        best_match: Listing | None = None
        best_score = 0
        
        for candidate in candidates:
            score = compute_duplicate_score(normalized_data, candidate)
            if score >= DEDUP_THRESHOLD and score > best_score:
                best_match = candidate
                best_score = score
        
        if best_match is None:
            # No duplicate — create a ListingSource for the new listing
            source_record = ListingSource(
                listing_id=new_listing.id,
                source=normalized_data["source"],
                external_id=normalized_data["external_id"],
                url=normalized_data["url"],
            )
            session.add(source_record)
            return None
        
        # Duplicate found — merge into canonical
        merge_duplicate(session, best_match, normalized_data)
        
        # Delete the newly-inserted duplicate listing row
        dup = session.query(Listing).get(new_listing.id)
        if dup:
            session.delete(dup)
        
        session.expunge(best_match)
        return best_match
```

### 5.4 Performance Analysis

| Operation | Cost | Frequency | Impact |
|-----------|------|-----------|--------|
| Candidate query | O(1) — indexed on `zip_code` | Once per new listing | Negligible |
| Scoring | O(K) where K = candidates (~5-15) | Once per new listing | Negligible |
| Address normalization | O(1) — string ops | Once per new listing | Negligible |
| Total per scrape run | ~20-50 new listings × ~10 candidates each | Per run | **< 100ms total** |

**Index recommendation**: Add a composite index on `(zip_code, bedrooms, is_active)` to speed up candidate queries:

```python
# In Listing model __table_args__:
Index("ix_listings_dedup_candidates", "zip_code", "bedrooms", "is_active"),
```

### 5.5 Edge Cases

| Scenario | Handling |
|----------|----------|
| Listing exists on Zillow first, then appears on Craigslist | Craigslist listing is merged into existing Zillow listing |
| Listing exists on Craigslist first, then appears on Zillow | Zillow listing is merged into existing Craigslist listing |
| Same listing appears on both sources in the same scrape run | First-processed source creates the listing; second source merges into it |
| Price differs between sources | Both prices recorded in `price_history`; canonical keeps its own price |
| Address normalization fails (unusual format) | Score won't reach threshold → treated as separate listings (safe default) |
| User favorited a listing that gets merged | Favorites are on the canonical listing — preserved |
| Three+ sources for same property (future) | Works naturally — each source adds a `ListingSource` row |

---

## 6. UI Impact

### 6.1 Multi-Source Badge Display

Currently, each card shows a single source pill via [`_SOURCE_LOGOS`](../app.py:999) and the [`zillow-pill-link`](../app.py:1214) CSS class. With multi-source listings, the card should show **all source pills**.

**Before** (single source):
```
[🏷 New] [3d ago]  [Zillow ↗]
```

**After** (multi-source):
```
[🏷 New] [3d ago]  [Zillow ↗] [Craigslist ↗]
```

### 6.2 Card HTML Changes

Replace the current single-source pill logic at [lines 1204–1224](../app.py:1204) with a loop over `listing.sources`:

```python
# Build source pill links for ALL sources
_source_pills_html = ""
for src_record in listing.sources:
    _src_url = src_record.url or ""
    if _src_url and _src_url.startswith(("http://", "https://")):
        _safe_url = html.escape(_src_url, quote=True)
        _src_name_lower = (src_record.source or "").lower()
        _logo_url = _SOURCE_LOGOS.get(_src_name_lower)
        _src_label = html.escape((src_record.source or "Link").capitalize())
        if _logo_url:
            _source_pills_html += (
                f'<a href="{_safe_url}" target="_blank" class="zillow-pill-link">'
                f'<img src="{html.escape(_logo_url, quote=True)}"> {_src_label}</a> '
            )
        else:
            _source_pills_html += (
                f'<a href="{_safe_url}" target="_blank" class="zillow-pill-link">'
                f'↗ {_src_label}</a> '
            )
```

### 6.3 Source Filter Update

The existing source filter in [`get_filtered_listings()`](../src/database.py:131) currently filters on `Listing.source`. After migration, it should filter via `ListingSource`:

```python
# Before:
if "source" in filters:
    query = query.filter(Listing.source == filters["source"])

# After:
if "source" in filters:
    query = query.filter(
        Listing.sources.any(ListingSource.source == filters["source"])
    )
```

### 6.4 Map Popup Changes

Map popups (Folium markers) should show all source links, similar to the card pills. The popup HTML template needs the same multi-source loop.

### 6.5 Email Notification Changes

The [`EmailChannel._build_html_body()`](../src/notifier.py:171) method renders listing source info. It should iterate over `listing.sources` to show all source links in the email.

### 6.6 Design Bible Alignment

Per the [design bible](../docs/design/design-bible.md:140):
- Source link + logo is a **required card element** (item 6 in the required card content list)
- Max 3 badges per card — source pills are **separate** from badges (they sit in the same row but don't count toward the 3-badge limit)
- Each source pill links to the original listing on that source's website

---

## 7. File Change Summary

| File | Changes |
|------|---------|
| [`src/models.py`](../src/models.py) | Add `ListingSource` model, add `sources` relationship to `Listing` |
| [`src/database.py`](../src/database.py) | Add `_migrate_to_listing_sources()`, `find_duplicate_candidates()`, `compute_duplicate_score()`, `merge_duplicate()`, `find_and_merge_duplicate()`, `normalize_address()`. Update `init_db()`, `get_filtered_listings()` |
| [`src/orchestrator.py`](../src/orchestrator.py) | Add dedup step after upsert (step 6). Update `mark_inactive()` call to use `ListingSource` |
| [`app.py`](../app.py) | Update card HTML to loop over `listing.sources`. Update source filter logic. Update map popup HTML |
| [`src/notifier.py`](../src/notifier.py) | Update email template to show multiple source links |

### New file (recommended)

| File | Purpose |
|------|---------|
| `src/dedup.py` | Contains `normalize_address()`, `compute_duplicate_score()`, `find_duplicate_candidates()`, `merge_duplicate()`, `find_and_merge_duplicate()` — keeps dedup logic isolated from [`src/database.py`](../src/database.py) |

---

## 8. Testing Strategy

### 8.1 Unit Tests

| Test | What it validates |
|------|-------------------|
| `test_normalize_address_abbreviations` | "123 North Main Drive" → "123 n main dr" |
| `test_normalize_address_extra_spaces` | "123  Main   St" → "123 main st" |
| `test_normalize_address_trailing_city` | "123 Main St, Sunnyvale, CA" → "123 main st" |
| `test_normalize_address_unit_removal` | "123 Main St Apt 2B" → "123 main st" |
| `test_score_exact_match` | Same property → score 100 |
| `test_score_different_property` | Different address → score < 75 |
| `test_score_price_within_threshold` | 5% price diff → still matches |
| `test_score_price_outside_threshold` | 10% price diff → doesn't match on price |
| `test_merge_fills_null_fields` | Canonical has NULL sqft, duplicate has sqft → filled |
| `test_merge_preserves_favorites` | Canonical is_favorite=True → stays True after merge |
| `test_merge_combines_images` | Both have images → merged, deduplicated |

### 8.2 Integration Tests

| Test | What it validates |
|------|-------------------|
| `test_zillow_then_craigslist` | Zillow listing ingested first, then same property from Craigslist → merged |
| `test_craigslist_then_zillow` | Reverse order → same result |
| `test_same_scrape_run` | Both sources return same property in one run → merged |
| `test_no_false_positive` | Similar but different properties → kept separate |
| `test_migration_backfill` | Existing listings get `ListingSource` records |

---

## 9. Rollout Plan

| Phase | Scope | Risk |
|-------|-------|------|
| **Phase 1** | Schema migration: create `listing_sources` table, backfill from existing data | Low — additive only |
| **Phase 2** | Implement `src/dedup.py` with address normalization and scoring | Low — new code, no existing changes |
| **Phase 3** | Integrate dedup into orchestrator pipeline | Medium — modifies ingestion flow |
| **Phase 4** | Update UI to display multi-source pills | Low — display-only change |
| **Phase 5** | Deprecate `Listing.source`, `Listing.external_id`, `Listing.url` columns | Low — cleanup |

---

## 10. Future Enhancements

- **Lat/Lng proximity matching**: When geocoded coordinates are available, use Haversine distance (< 50m) as an additional matching signal (per [`.roo/skill-data-scraping.md`](../.roo/skill-data-scraping.md:30))
- **Manual merge/split UI**: Allow users to manually merge or split listings the algorithm got wrong
- **Confidence display**: Show a "matched from 2 sources" indicator with confidence percentage
- **Cross-source price comparison**: Show price from each source side-by-side when they differ
- **Fuzzy address matching**: Use Levenshtein distance for addresses that are close but not exact after normalization (e.g., typos)
