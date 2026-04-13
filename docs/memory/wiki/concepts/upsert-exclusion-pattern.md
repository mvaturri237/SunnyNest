# Upsert Exclusion Pattern

> User-managed flags (`notified`, `is_favorite`, `is_disliked`) and monotonic date fields (`listed_date`, `first_seen`) must be excluded from generic update loops in `upsert_listing()`.

**Applies to:** [Database Schema](../entities/database-schema.md), [Orchestrator](../entities/orchestrator.md), [Notification System](../entities/notification-system.md), [Craigslist Scraper](../entities/craigslist-scraper.md)  
**Learned:** 2026-03-31  
**Source:** `docs/memory/shared/lessonsLearned.md` — User-Managed Flags + Craigslist Renewal Dates + `docs/memory/shared/systemPatterns.md` — Monotonic Dates

## Pattern

The `upsert_listing()` function in `src/database.py` has a generic field update loop: `for key, value in listing_data.items(): setattr(existing, key, value)`. Without exclusions, this loop would overwrite fields that have different lifecycle owners:

1. **User-managed flags** (`notified`, `is_favorite`, `is_disliked`) — owned by user actions, not scraper runs
2. **Monotonic date fields** (`listed_date`, `first_seen`) — should only move to earlier values, never later

### Two Sub-Patterns

**User-Managed Flags:**
Fields representing user state must be excluded from the generic update loop. If a scraper ever included these keys, user-managed state would be silently overwritten.

**Monotonic Dates:**
Date fields representing "earliest known" events must never be overwritten with a later value. Craigslist renewal dates (which show the renewal date, not the original posting date) were overwriting `listed_date` on every re-scrape, making 7-day-old listings appear as "New" and "1d ago".

## Rules

1. **Exclude user-managed flags from `upsert_listing()` update loop:** `"notified"`, `"is_favorite"`, `"is_disliked"`
2. **Exclude monotonic date fields:** `"listed_date"`, `"first_seen"`
3. **Apply min-date logic for `listed_date`:** Keep `min(old, new)` when both exist
4. **Apply exclusions in BOTH paths:** Primary upsert path AND merged-listing gap-fill path
5. **When adding new user-managed boolean flags:** Always add them to the exclusion tuples
6. **Consider extracting exclusion tuples into named constants** (P3 suggestion from review)

## Examples

- **39-listing email incident (2026-03-31):** All previous notification attempts failed (SMTP missing), so `notified=False` on all listings. First successful send picked up everything. Investigation revealed `upsert_listing()` didn't exclude `notified`.
- **Craigslist renewal dates (2026-03-31):** Listings posted 7+ days ago showed as "New" because the scraper parsed the renewal date on every run and overwrote `listed_date`.
- **Fix:** Added exclusion tuples + min-date logic in both upsert paths

## Related

- [Database Schema](../entities/database-schema.md) — `upsert_listing()` implementation
- [Craigslist Scraper](../entities/craigslist-scraper.md) — renewal date issue
- [Notification System](../entities/notification-system.md) — `notified` flag protection
- [Deduplication](../entities/deduplication.md) — merge path also respects exclusions
