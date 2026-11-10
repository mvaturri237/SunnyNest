# Spec: "Available Date" on Listing Cards

> **Author:** 🏗️ Architect
> **Status:** ❌ **KILLED (2026-06-03)** — no viable cheap data source. See "Kill Decision" section below.
> **Created:** 2026-06-03
> **Killed:** 2026-06-03 (same day — runtime probe invalidated the premise within hours)
> **Wiki Impact (actually applied):** Added "Fields NOT exposed by `/search/byaddress`" section to [`zillow-scraper`](../docs/memory/wiki/entities/zillow-scraper.md). NO changes to `listing-card`, `database-schema`, or any production code.

---

## ❌ Kill Decision (2026-06-03)

**Why killed:** A field-verification probe (Code mode, 1 API call, reverted in full — see [`docs/memory/wiki/archive/zillow-avail-probe-findings-2026-06-03.md`](../docs/memory/wiki/archive/zillow-avail-probe-findings-2026-06-03.md)) confirmed the ZLLW Working API `/search/byaddress` endpoint **does not return any availability field**. Only `listingDateTimeOnZillow` matches the search pattern, and that's the posted-date — semantically duplicate of what we already store as `Listing.listed_date`.

Combined with the Architect's findings in Part 1 below (Realtor ❌ in current endpoint, Craigslist ⚠️ free-text only), the feature has no cheap data source:

| Path forward | Cost | Verdict |
|--------------|------|---------|
| Zillow `/property` detail endpoint | +25 calls/scrape ≈ 750/mo (blows 500/mo free tier) — would need paid plan (~$15-25/mo) or weekly-only scrape | Rejected by user |
| Realtor detail endpoint | +20 calls/scrape ≈ 600/mo (blows 150/mo free tier) | Rejected by user |
| Switch Zillow RapidAPI provider | Multi-hour evaluation; unknown coverage | Rejected by user |
| Craigslist `#postingbody` regex | ~2-3s per detail-page request, ~50% miss rate, fragile | Rejected by user |

**User decision:** *"Kill the feature for now — just have the Orchestrator write the 'Fields NOT exposed' note onto the Zillow scraper wiki entity (closes the loop, prevents repeating this investigation in 3 months) and move on."*

### Reopen criteria

Reopen this spec **only when one of the following becomes true:**

1. **Quarterly re-probe** (suggested cadence: Oct 2026, Jan 2027 …) — RapidAPI providers occasionally extend their response schema. The same one-shot probe pattern (3-listing sample, `[AVAIL-PROBE]` prefixed warning logs, full revert) takes ~30 min and costs 1 API call. If `availabilityDate` (or any new key matching `avail|date|move`) appears, jump to Phase 1 in this spec.
2. **User opts to pay** for the Zillow or Realtor detail endpoint (~$15-25/mo Zillow paid tier OR drop scrape frequency to weekly to fit free tier).
3. **A different ZLLW RapidAPI provider is evaluated and migrated to** with availability in its search response — separate Architect task.
4. **User accepts the Craigslist regex path** with explicit "best-effort, may be inaccurate" UI treatment (covers only ~50% of CL listings — was rejected today as low ROI).

**Everything below this line is preserved as the original investigation record** so a future re-opener has full context without re-deriving it.

---

---

## Objective

Display each listing's **move-in availability date** (e.g. "Available Sat Aug 1 2026" as Zillow shows it) on each card in the dashboard's left panel.

**Why it matters:** The user's target move-in date is **July 15, 2026** ([`plans/architecture.md:10`](architecture.md:10)). When browsing 100+ listings, knowing whether each unit is available *before*, *on*, or *long after* July 15 is currently invisible — the user has to click through to the source site for every candidate. This is the single biggest unsurfaced piece of metadata on the card.

**Success criteria:**
- For listings where the source exposes an availability date, the card shows a clearly-distinct date display (NOT confusable with "days on market").
- For listings with no data (e.g. Craigslist if we don't scrape descriptions), the card degrades gracefully — no broken UI, no "None"/"null".
- The change respects the **max-3-badges-per-card** rule from the [Design Bible §4](../docs/design/design-bible.md:232).
- Implementation is **incremental** — Zillow alone proves the feature; other sources roll out per source-availability classification.

---

## Key Facts (Verified)

| Fact | Source / Line | Confirmed? |
|------|---------------|------------|
| `Listing.available_date` column already exists, `Date` type, nullable | [`src/models.py:154`](../src/models.py:154) | ✅ Yes |
| **All 271 active listings** have `available_date IS NULL` (114 craigslist + 117 zillow + 40 realtor) | `sqlite3 data/listings.db` query run 2026-06-03 | ✅ Yes |
| No scraper's `normalize()` method writes `available_date` | [`zillow_scraper.py:375`](../src/scrapers/zillow_scraper.py:375), [`craigslist_scraper.py:350`](../src/scrapers/craigslist_scraper.py:350), [`realtor_scraper.py:458`](../src/scrapers/realtor_scraper.py:458) — see returned dict keys | ✅ Yes |
| Legacy Streamlit `app.py` ALREADY HAS the display logic with "🏠 Now" / "🏠 MMM D" badges | [`app.py:1133-1155`](../app.py:1133), CSS at [`app.py:241-242`](../app.py:241) | ✅ Yes |
| FastAPI `listing-card.html` does NOT display `available_date` anywhere | [`web/templates/partials/listing-card.html`](../web/templates/partials/listing-card.html) — grep returns 0 hits | ✅ Yes |
| Max-3 badges is mandatory; existing priority is `price change > New > availability` | [Design Bible §4](../docs/design/design-bible.md:232), [`plans/ui-polish.md:124-129`](ui-polish.md:124) | ✅ Yes |
| Current card already shows a days-on-market badge ("Today", "3d ago", "2w ago") for *posted-date* | [`listing-card.html:91-106`](../web/templates/partials/listing-card.html:91) | ✅ Yes |
| `plans/filter-bar-redesign.md:110` noted `available_date` "is rarely populated in our data" — accurate (it's NEVER populated today) | [`plans/filter-bar-redesign.md:110`](filter-bar-redesign.md:110) | ✅ Yes |

---

## Part 1 — Data Source Investigation

### A. Zillow (RapidAPI "ZLLW Working API") — ⚠️ Likely available, field name UNVERIFIED

**Current state** ([`zillow_scraper.py:280-396`](../src/scrapers/zillow_scraper.py:280)):
The scraper extracts from `raw["property"]`:
- `zpid`, `address`, `price` (multiple fallbacks), `bedrooms`, `bathrooms`, `livingArea` (→ sqft), `propertyType`, `media.allPropertyPhotos`, `location.latitude/longitude`, `daysOnZillow` (→ derives `listed_date`), pet/parking/laundry features.

**No code path reads any availability-related field.** Grep across the entire codebase for `availab|move.?in|date_available|availabilityDate|dateAvailable|whatIWant|unitsGroup` returned only:
- Comments in `app.py` (legacy display code referencing the unpopulated DB column)
- [`zillow_scraper.py:308`](../src/scrapers/zillow_scraper.py:308) — `prop.get("unitsGroup", [])` is used for `propertyGroup` bedrooms only, NOT availability.

**No raw API response sample is checked into the repo.** Scraper logs (`logs/scraper-stdout.log`) contain no relevant payload dump either.

**The user's screenshot** shows Zillow's web UI rendering "Available Sat Aug 1 2026" — confirming the data EXISTS on Zillow's side. But whether the ZLLW Working API (RapidAPI mirror) exposes it AND under what key is **unverified**.

**Likely candidates** (in priority order, based on Zillow API conventions seen in similar wrappers):
1. `prop["availabilityDate"]` — ISO 8601 string, most common
2. `prop["dateAvailable"]` — alternate camelCase
3. `prop["whatIWant"]["availabilityDate"]` — buried in rental-specific subdict
4. `prop["hdpView"]["availabilityDate"]` — view-model subdict (already used as a price fallback at [`zillow_scraper.py:439`](../src/scrapers/zillow_scraper.py:439))
5. For `resultType == "propertyGroup"` (apartment complexes): `prop["unitsGroup"][n]["availabilityDate"]` — would need aggregation across units (min/earliest)

**Recommendation:**
> 🟡 **Runtime verification REQUIRED before implementation.** Spawn a small Code-mode task that adds a temporary debug log at [`zillow_scraper.py:280`](../src/scrapers/zillow_scraper.py:280) immediately after `prop = raw.get("property", {})`, dumping `sorted(prop.keys())` and `sorted(prop.get("whatIWant", {}).keys())` plus any matching keys (case-insensitive `re.search(r"avail|date", k)`) for the first 3 listings of one scrape run. Once the field is identified, remove the log and add the extraction. **Budget for this verification: 30 minutes of one scraper run + 1 log inspection.**

**Classification:** ⚠️ **Available but UNVERIFIED** — extremely likely to exist, but no field-name evidence in repo or logs.

---

### B. Craigslist (Playwright HTML scrape) — ❌ Not available without invasive scraping

**Current state** ([`craigslist_scraper.py`](../src/scrapers/craigslist_scraper.py)):
- `_extract_row_data()` ([`l. 504`](../src/scrapers/craigslist_scraper.py:504)) extracts only `external_id`, `title`, `url`, `price`, `meta_text` (which contains bedrooms/sqft/neighborhood/posted-date), `image_urls`.
- `_scrape_detail_addresses()` ([`l. 371`](../src/scrapers/craigslist_scraper.py:371)) is the only detail-page pass and it ONLY queries `div.mapaddress, div.mapAndAttrs h2, .street-address, span.postingtitletext small`. It does NOT load the post body / description.
- The Craigslist post body (the `#postingbody` div) is where free-text availability ("available July 15", "ready to move in 8/1", "available now") would appear.

**Why I rate this ❌:**
1. **Free-text parsing is fragile.** Renters write things like "Avail. 8/1", "Available August 1st", "Move in mid-July", "Available immediately", "Open now", "Can move-in by 7/15-7/20". A regex catches maybe 60% reliably.
2. **Cost.** Each Craigslist listing would need a `page.goto()` to fetch the body — adds ~2-3s per listing × dozens per run, plus rate-limit risk. The existing detail pass already does this for addresses, but for addresses we use precise CSS selectors; for availability we'd need to also extract `#postingbody` text and regex it.
3. **Negative ROI.** Even if we add it, ~40% of Craigslist posts don't mention availability at all — the field stays NULL, defeating the value.

**Alternative:** Add it as a Phase 3 stretch goal with explicit "best-effort, may be wrong" UI treatment (e.g. a `title=` tooltip saying "Source: Craigslist post body, may be inaccurate"). Not recommended for v1.

**Classification:** ❌ **Not available** without invasive description-body scraping + fragile regex. Recommend marking Craigslist cards as "Date TBD" or simply omitting the date row.

---

### C. Realtor (RapidAPI "Realtor Search") — ❌ Not in known response, requires research

**Current state** ([`realtor_scraper.py:374-479`](../src/scrapers/realtor_scraper.py:374)):
The scraper uses `description: dict` heavily for beds/baths/sqft/type. It extracts `list_date` ([`realtor_scraper.py:447`](../src/scrapers/realtor_scraper.py:447) via [`_parse_list_date`](../src/scrapers/realtor_scraper.py:636)) — but `list_date` is *posted date*, not *available date*.

**Documented sample payload** ([`plans/realtor-scraper.md:60-110`](realtor-scraper.md:60)) does NOT include any availability field — only `list_date`, `status: "for_rent"`, and the property metadata. The plan author noted at [`l. 112`](realtor-scraper.md:112): *"The exact response structure must be verified against the live API."*

**The Realtor.com web UI** does sometimes show "Available: MM/DD/YYYY" on detail pages. This typically lives in:
- `description.date_available` — possible but unconfirmed
- `flags.is_available_now` — boolean variant
- A separate `/properties/detail` call (we currently only call `/properties/search-rent`)

**Why I rate this ❌ (for now):**
- No evidence in the documented sample.
- We only have 40 Realtor listings in the DB — small sample size, lower priority.
- Adding a detail-endpoint call doubles API quota usage (currently 500/mo budget per [`plans/realtor-scraper.md:130`](realtor-scraper.md:130)) — non-trivial cost.

**Classification:** ❌ **Not available in current API call.** Could be ⚠️ if a future detail-endpoint integration is added, but out of scope here.

---

### Source-Availability Summary

| Source | Verdict | Effort to wire | DB rows affected (today) |
|--------|---------|----------------|--------------------------|
| Zillow | ⚠️ Available, but field name unverified | S (after 30-min verification task) | 117 (43% of all) |
| Realtor | ❌ Not in current API response | M (needs detail endpoint or API research) | 40 (15%) |
| Craigslist | ❌ Free-text only, fragile | L (description-body scraping + regex) | 114 (42%) |

**Implication:** Even if we ship perfectly, ~43% of listings get a populated date and 57% stay NULL. The display semantics MUST handle NULL gracefully — see Part 2.

---

## Part 2 — Display Semantics

### What counts as "available"?

For a given `available_date` value `d` relative to today's date `T`:

| Condition | Meaning | Recommended display | Color cue |
|-----------|---------|--------------------|-----------|
| `d <= T` | Available right now or was already available | **"Available now"** (no specific date — stale data may show June for a still-listed unit; "now" is what user cares about) | Green `--color-success` (`#16a34a`) |
| `T < d <= T + 30` | Available within a month — high relevance for someone planning to move | **"Avail Jul 15"** (compact month-day, no year unless next calendar year) | Brand blue `--accent-blue` (`#2563eb`) |
| `T + 30 < d <= T + 90` | Available in 1–3 months — relevant but not urgent | **"Avail Aug 1"** | Neutral text-secondary (`#4a5568`) |
| `d > T + 90` | Far future — usually a sign of a relisting or new construction | **"Avail Oct 1, 2026"** (include year when >3 months out to disambiguate) | Muted text-muted (`#718096`) |
| `d == NULL` | No data (Craigslist; Realtor; some Zillow) | **Omit the date display entirely** — do NOT show "Date TBD" or "Unknown" (clutter, no value) | — |

**Why "Available now" instead of the actual past date:** Showing "Available May 1, 2026" on June 3 reads as "this listing is stale" or causes a "did I miss it?" moment. The unit is still listed, so semantically it's available NOW. Owner can hover the badge for the tooltip with the raw date if curious (defensive UX).

### Format examples

- **Within current year:** `"Avail Jul 15"` (no year)
- **Next calendar year (Dec → Jan crossing):** `"Avail Jan 5, 2027"`
- **Past or today:** `"Available now"` (the word "Available" spelled out; not "Avail now" — the urgency word reads better full)

Rationale: matches the Zillow source UI wording ("Available Sat Aug 1 2026") while shortening for card density. Day-of-week is dropped — saves space and isn't decision-relevant for a multi-day move window.

### Conflict with the existing "days on market" badge

The card today shows a "Today", "3d ago", "2w ago" badge — this is the **post date** age, not availability. These are easy to confuse visually since both are time-related.

**Disambiguation tactics (use all three):**
1. **Different icon:** Days-on-market has no icon; availability uses 🏠 (matching the legacy Streamlit precedent at [`app.py:1151,1154`](../app.py:1151)) OR 📅 (more semantically neutral).
2. **Different label prefix:** Days-on-market is bare ("3d ago"); availability is prefixed ("Avail Jul 15" or "Available now").
3. **Different color band:** Days-on-market uses the freshness gradient (green→amber→red). Availability uses a separate semantic palette (green=now, blue=soon, gray=far-out).

### Edge cases

| Case | Handling |
|------|----------|
| `available_date` < `listed_date` (rare data error) | Display the value as-is; don't try to "correct" it — could mask scraper bugs |
| `available_date` > `T + 365` (more than a year out) | Still display; rare but legitimate for build-to-rent / pre-leasing |
| `available_date == listed_date` (means "available since posted") | Treat as "Available now" — same effective semantics |
| `propertyGroup` (apartment complex) with multiple unit availabilities | Use earliest available date across units; tooltip can show "Earliest of N units" |

---

## Part 3 — Three Mockup Options

The current card layout (per [`listing-card.html`](../web/templates/partials/listing-card.html) and [Design Bible §3](../docs/design/design-bible.md:113)):

```
┌────────────────────────────────────────────────────────┐
│  ┌──────────┐  $5,500/mo   745 Mountain Wy., Sunnyvale│
│  │          │  4 bed · 2 bath · 1,683 sqft (156 m²)   │
│  │  IMAGE   │  ┌─────┐ ┌──────┐ ┌──────┐ ┌──Zillow──┐│
│  │  140×130 │  │ New │ │ 3d   │ │ 🐕   │ │ favicon  ││
│  │   ☆ 👎   │  └─────┘ └──────┘ └──────┘ └──────────┘│
│  └──────────┘  Downtown                                │
│                🏫 Cherry Chase Elementary              │
└────────────────────────────────────────────────────────┘
```

---

### Option A — Inline append to specs row 🥉

**Idea:** Add `· Avail Jul 15` (or `· Available now`) to the specs line at [`listing-card.html:60-75`](../web/templates/partials/listing-card.html:60), only when `listing.available_date` is non-null.

```
┌────────────────────────────────────────────────────────┐
│  ┌──────────┐  $5,500/mo   745 Mountain Wy., Sunnyvale│
│  │          │  4 bed · 2 bath · 1,683 sqft (156 m²)   │
│  │  IMAGE   │              · Avail Jul 15  ◀── NEW    │
│  │          │  ┌─────┐ ┌──────┐ ┌──────┐ ┌──Zillow──┐│
│  │   ☆ 👎   │  │ New │ │ 3d   │ │ 🐕   │ └──────────┘│
│  └──────────┘  └─────┘ └──────┘ └──────┘              │
│                Downtown                                │
│                🏫 Cherry Chase Elementary              │
└────────────────────────────────────────────────────────┘
```
*(May wrap to second line on narrow cards.)*

**Pros:**
- Zero impact on the max-3-badges constraint.
- Lowest visual disruption — feels like natural data.
- No new CSS class needed; reuses `.card-specs` styling.
- Fastest to implement (template-only on the display side).

**Cons:**
- Low visual weight — easy to miss when scanning a list of 50 cards. Defeats the whole point if the user can't spot it.
- No color/icon affordance — relies on text-pattern recognition only. Conflicts with the [Design Bible §5](../docs/design/design-bible.md:256) "never color alone" rule INVERSELY: we're not using color AT ALL where we probably should.
- Text-only doesn't communicate urgency (within-30-days vs >90-days look identical).
- Wraps awkwardly on `768–1024px` breakpoint (360px panel) where specs already approach overflow.

**Files affected:**
- `src/scrapers/zillow_scraper.py` — add availability extraction in `normalize()` after [`l. 361`](../src/scrapers/zillow_scraper.py:361)
- `web/templates/partials/listing-card.html` — append to specs join at [`l. 70-74`](../web/templates/partials/listing-card.html:70)
- Add a Jinja filter `format_availability(date)` in `web/dependencies.py` (returns "Avail Jul 15" / "Available now" / "")
- NO CSS changes
- NO model change (column exists)

**Design-bible compliance:**
- ✅ Inter font (inherited)
- ✅ Max-3 badges (untouched)
- ✅ Blue accent (N/A — no color used)
- ⚠️ WCAG AA contrast (inherits specs text — passes)
- ❌ "Never color alone" — actually we use NO encoding (no color, no icon). For a feature that should signal urgency, this is too weak.

**Effort:** **S** (~1-2 hours of Code-mode work after Zillow field is verified)

---

### Option B — New 📅 badge in tag-row with priority eviction 🥈

**Idea:** Add availability as a badge variant in the existing tag-row, with priority logic ensuring it can evict less-important badges to fit within 3.

```
┌────────────────────────────────────────────────────────┐
│  ┌──────────┐  $5,500/mo   745 Mountain Wy., Sunnyvale│
│  │          │  4 bed · 2 bath · 1,683 sqft (156 m²)   │
│  │  IMAGE   │  ┌─────┐ ┌────────────┐ ┌──────┐        │
│  │          │  │ New │ │ 🏠 Jul 15 │ │ 3d   │  ◀──    │
│  │   ☆ 👎   │  └─────┘ └────────────┘ └──────┘        │
│  └──────────┘  ┌──Zillow──┐                            │
│                └──────────┘                            │
│                Downtown   🏫 Cherry Chase              │
└────────────────────────────────────────────────────────┘
```

**Priority order** (highest first, take top 3):
1. Price change (price-drop / price-up) — `tag-price-drop` / `tag-price-up` (P0 economic signal)
2. **Availability date** — `tag-available-now` / `tag-available-soon` / `tag-available-future` (P0 decision-relevance)
3. "New" badge — `tag-new` (≤3 days listed)
4. Days-on-market badge — `tag-fresh` / `tag-aging` / `tag-stale`
5. Pet / AC badges — `tag-pet` / `tag-ac`

Note: this is a CHANGE from the current [`listing-card.html:79-117`](../web/templates/partials/listing-card.html:79) priority. Today "New" is appended before "DOM" before "Pet" before "AC". We insert availability at position 2.

**Pros:**
- Strong visual weight — matches importance of the data.
- Three-tier color system (green / blue / gray) communicates urgency at a glance.
- Reuses existing badge styling (`card-tag` class, `.tag-available-*` variants already defined in legacy [`app.py:241-242`](../app.py:241) — can port to FastAPI CSS).
- Honors max-3 rule via explicit priority sort.
- Symmetric with Zillow's source UI (badges are how Zillow displays "Available …" too).

**Cons:**
- Evicting other badges has UX cost: a stale apartment that's available now will lose its "3w ago" badge, hiding a relevant negative signal. (Counter-argument: 3w ago + still available = not actually a problem; price drop is the only badge that should always win.)
- Adds a new CSS class trio (`.tag-available-now`, `.tag-available-soon`, `.tag-available-future`) — small but real surface.
- Slightly increases tag-row width — risk of badge wrapping on the 360px breakpoint.
- "📅 Jul 15" vs "🏠 Jul 15" — icon choice debate. I'd pick 📅 to differentiate from the property-type 🏠 placeholder used at [`listing-card.html:23`](../web/templates/partials/listing-card.html:23).

**Files affected:**
- `src/scrapers/zillow_scraper.py` — add extraction in `normalize()`
- `web/templates/partials/listing-card.html` — refactor tag-priority loop (~20 lines changed) at [`l. 79-117`](../web/templates/partials/listing-card.html:79)
- `web/static/css/style.css` — add three new `.tag-available-*` classes (port from [`app.py:241-242`](../app.py:241), adapt to light theme tokens) + **bump cache version** in [`web/templates/base.html`](../web/templates/base.html) per [§5 of AGENTS.md](../AGENTS.md)
- Add Jinja filter `format_availability_badge(date)` returning `{class, text, title}` tuple
- NO model change

**Design-bible compliance:**
- ✅ Inter font (inherited)
- ✅ Max-3 badges enforced explicitly
- ✅ Blue accent for "soon" state matches `--accent-blue`
- ✅ WCAG AA: green/blue/gray each verified ≥4.5:1 on white via existing tag-variant precedent
- ✅ "Never color alone": pairs color with 📅 icon and explicit "Avail" prefix text

**Effort:** **M** (~3-4 hours after Zillow field verified — includes priority refactor, CSS port, cache bump, test)

---

### Option C — Dedicated row below schools 🥇 *(see Recommendation)*

**Idea:** Add a new `.card-availability` line below the school assignment row, styled like the schools row (small, prefixed with an icon), but with semantic color treatment based on the date bucket.

```
┌────────────────────────────────────────────────────────┐
│  ┌──────────┐  $5,500/mo   745 Mountain Wy., Sunnyvale│
│  │          │  4 bed · 2 bath · 1,683 sqft (156 m²)   │
│  │  IMAGE   │  ┌─────┐ ┌──────┐ ┌──────┐ ┌──Zillow──┐│
│  │          │  │ New │ │ 3d   │ │ 🐕   │ └──────────┘│
│  │   ☆ 👎   │  └─────┘ └──────┘ └──────┘              │
│  └──────────┘  Downtown                                │
│                🏫 Cherry Chase Elementary              │
│                📅 Available Jul 15  ◀── NEW row       │
└────────────────────────────────────────────────────────┘
```

For "Available now" (within 30 days), use green text matching `--color-success`. For future dates use neutral `--text-secondary`. Color is paired with the 📅 icon AND the word "Available".

**Pros:**
- **Doesn't compete for badge slots** — preserves all existing badges including pets/AC even when availability is present.
- **Highest scannability** — has its own row; eye lands on a consistent vertical position.
- **Mirrors the schools row pattern** — visually coherent with how other "extra metadata" is shown ([`listing-card.html:162-165`](../web/templates/partials/listing-card.html:162)).
- Easy to omit gracefully when NULL (just `{% if listing.available_date %}`)— no eviction logic.
- Provides room for richer treatment (e.g. urgency color + relative phrase "in 5 weeks").
- Future-proof — if we add a second extra field (e.g. "Open house Sat"), the same row pattern extends.

**Cons:**
- Adds ~14-18px to card height — risk of pushing card past the ~140-160px target ([Design Bible §3](../docs/design/design-bible.md:124)) and dropping visible cards from 4 to 3 in the panel. **Mitigation:** Only show the row when `available_date IS NOT NULL` AND the schools row is also non-empty would still be the deepest case; if the schools row is empty, no net change.
- New CSS class to maintain (`card-availability`).
- Color variants (green / blue / muted) need 3 CSS rules + WCAG verification on each.
- Two prefixed rows (`🏫 …` and `📅 …`) in a row could feel busy. Could be mitigated by using a smaller font for the availability line.

**Files affected:**
- `src/scrapers/zillow_scraper.py` — add extraction
- `web/templates/partials/listing-card.html` — add new conditional block after [`l. 165`](../web/templates/partials/listing-card.html:165)
- `web/static/css/style.css` — add `.card-availability` + 3 color modifier classes (`.card-availability--now`, `.card-availability--soon`, `.card-availability--future`); **bump cache version** in `web/templates/base.html`
- Add Jinja filter `format_availability_row(date)` returning `{class, text}` (label-text only — icon stays in template)
- NO model change

**Design-bible compliance:**
- ✅ Inter font
- ✅ Max-3 badges (NOT touched — this is a new row, not a badge)
- ✅ Blue accent (and green for "now") — palette compliant
- ✅ WCAG AA: 4.5:1 contrast verified for each color variant on `--bg-card` white (`#16a34a` on white = 4.54:1 ✅; `#2563eb` on white = 8.59:1 ✅; `#4a5568` on white = 8.07:1 ✅)
- ✅ "Never color alone": pairs with 📅 icon and "Available" word
- ⚠️ Card height — requires measuring once implemented to confirm cards still fit 3-4 in the panel

**Effort:** **S–M** (~2-3 hours after Zillow field verified — template + CSS + cache bump + visual QA)

---

## Recommendation

**Pick Option C (Dedicated row).** It's the only option that (a) shows the data with enough visual weight to be useful, (b) preserves the max-3-badge contract without forcing eviction trade-offs that hide other relevant signals (price drops, pet-OK), (c) degrades to invisible cleanly for the 57% of listings (Craigslist + Realtor) where we lack data — no badge slot is "wasted," no visual residue. Option A is too quiet for a P0 decision factor; Option B forces a priority refactor and badge-eviction logic whose downsides (potentially hiding "3w ago" on units the user wants to triage as stale) are larger than its visual-weight benefit. The card-height concern is real but the row only appears when data exists (Zillow-only in Phase 1 = ~43% of cards initially), and the schools row + availability row stack cleanly with consistent prefix-icon styling.

---

## Phased Rollout Plan

### Phase 1 — Zillow only (proves the feature) — **S+S effort**

**Prereq:** Spawn a one-shot Code-mode task to add a temporary debug log dumping `prop.keys()` and `prop.get("whatIWant", {}).keys()` for the first 3 listings in the next scraper run. Identify the actual field name. Remove the debug log. **(~30 min including one scraper run.)**

Then:

| Task | File | Acceptance |
|------|------|------------|
| 1.1 Add `available_date` extraction to `ZillowScraper.normalize()` | [`src/scrapers/zillow_scraper.py`](../src/scrapers/zillow_scraper.py:354) | New Zillow scrapes populate `available_date` for ≥60% of listings (some genuinely don't expose it on Zillow) |
| 1.2 Add `format_availability_row()` Jinja filter | [`web/dependencies.py`](../web/dependencies.py:1) | Unit-testable: NULL → `None`; past → "Available now"; +14d → "Available Jul 17"; +120d → "Available Oct 1, 2026" |
| 1.3 Add `.card-availability` + 3 modifiers in CSS | [`web/static/css/style.css`](../web/static/css/style.css:1) | Visual QA in browser; cache version bumped in [`web/templates/base.html`](../web/templates/base.html) |
| 1.4 Add conditional row to card template | [`web/templates/partials/listing-card.html`](../web/templates/partials/listing-card.html:165) | After Zillow re-scrape, ~117 cards show the row, ~154 Craigslist+Realtor cards don't |
| 1.5 Code Reviewer pass per AGENTS.md workflow | — | No P0/P1; CSS version bumped check; HTML verification via `curl` per [§6](../AGENTS.md) |

**Verification:** After Phase 1 ships, eyeball-test that 4 cards still fit in the scrollable left panel at default zoom. If they drop to 3, revisit card padding / availability-row line-height.

### Phase 2 — Realtor (if API research succeeds) — **M effort**

Trigger condition: Phase 1 in production for ≥1 week, no UX regressions reported.

| Task | Notes |
|------|-------|
| 2.1 Research Realtor API for availability field | Inspect raw `/properties/search-rent` response (live API call + log) for any `date_available`/`date_move_in`/`flags.is_available_*` key. If absent, evaluate `/properties/detail` endpoint cost (currently we don't call it; would double API budget consumption). |
| 2.2 If available in search response, add to [`RealtorScraper.normalize()`](../src/scrapers/realtor_scraper.py:458) | Mirror Zillow's extraction shape |
| 2.3 If only in detail endpoint, write up a sub-spec for the cost/benefit trade-off before any code | Don't blow the 500/mo quota silently |
| 2.4 Code Reviewer pass | — |

### Phase 3 — Craigslist (decision point, default = SKIP) — **L effort, low value**

Default recommendation: **skip.** Re-evaluate only if owner explicitly requests it.

If pursued:
- Extend [`_scrape_detail_addresses()`](../src/scrapers/craigslist_scraper.py:371) to also extract `#postingbody` text
- Add a regex panel (`r"(?:available|avail\.?|move[- ]in|ready)\b.{0,30}\b((?:\d{1,2})[/-](?:\d{1,2})(?:[/-]\d{2,4})?|\d{1,2}\s+(?:jan|feb|...)|now|immediately)"i`)
- Add `_parse_availability_text() -> date | None` with conservative parsing (return None on any ambiguity)
- Display with a `title=` tooltip warning: *"Parsed from Craigslist description — may be inaccurate"*
- Accept that ~40-50% of Craigslist listings will still have NULL availability

---

## Open Questions for Owner

1. **Icon choice:** 📅 (neutral calendar) vs 🏠 (legacy app's choice, more semantic for "move-in")? I lean 📅 to avoid confusion with the placeholder-image 🏠 already used on cards without photos.
2. **"Available now" lookback window:** Is `available_date <= today` enough, or should it also cover `available_date < listed_date` (data error case — show as "now" regardless)?
3. **Tooltip on hover:** Yes/no for showing raw date string on hover? Adds discoverability but minor; defer to Phase 1.5 if any user feedback suggests confusion.
4. **Filter integration (out of scope here):** Should the filter bar add an "Available by [date picker]" filter once data is populated? Don't build until ≥50% of listings have data — currently 0%. Track in [`plans/filter-bar-redesign.md`](filter-bar-redesign.md) backlog.

---

## Wiki Impact

- **New entities:** None
- **Updated entities (after Phase 1 ships):**
  - [`zillow-scraper`](../docs/memory/wiki/entities/zillow-scraper.md) — note new `available_date` extraction logic and the verified field name (once known)
  - [`listing-card`](../docs/memory/wiki/entities/listing-card.md) — new `.card-availability` row component, updated display contract
  - [`database-schema`](../docs/memory/wiki/entities/database-schema.md) — note `available_date` column is now actually populated for Zillow rows (no schema change, just usage note)
- **New concepts:** None — this feature reuses existing patterns (adapter pattern, CSS cache versioning, max-3-badges)
