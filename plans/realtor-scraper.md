# Realtor.com Scraper — Architecture Plan

**Date:** 2026-04-01
**Status:** PROPOSAL
**Author:** Architect Agent
**Estimated Effort:** 8–14 hours

---

## 1. Overview

Add a third data source — **Realtor.com** — to SunnyNest's rental listing aggregator. This scraper follows the existing adapter pattern established by [`ZillowScraper`](../src/scrapers/zillow_scraper.py) and [`CraigslistScraper`](../src/scrapers/craigslist_scraper.py), extending [`BaseScraper`](../src/scrapers/base.py) with `scrape()` and `normalize()` methods.

**Goal:** Increase listing coverage for Sunnyvale, CA (zip codes 94085, 94086, 94087, 94089) by adding Realtor.com as a complementary source alongside Zillow and Craigslist.

---

## 2. API Selection — Recommendation

### 2.1 Recommended API: **"Realtor Search" by API_Jeeves on RapidAPI**

| Criteria | Details |
|----------|---------|
| **API Name** | Realtor Search (by API_Jeeves) |
| **RapidAPI URL** | `https://rapidapi.com/API_Jeeves/api/realtor-search` |
| **Host** | `realtor-search.p.rapidapi.com` |
| **Key Endpoint** | `GET /properties/search-rent` |
| **Free Tier** | 100 requests/month (Basic plan: 500 req/month at ~$10/mo) |
| **Response Format** | JSON with structured property data |
| **Search By** | City/state, zip code, coordinates |
| **Data Quality** | Addresses ✅, prices ✅, photos ✅, beds/baths ✅, sqft ✅, pet policy ⚠️ (limited), lat/lng ✅ |

### 2.2 Budget Feasibility Analysis

With 4 zip codes scraped every 6 hours:
- **Per sync:** 4 zip codes × 1–2 pages each = 4–8 API calls
- **Per day:** 4 syncs × 4–8 calls = 16–32 calls/day
- **Per month:** 32 × 30 = ~960 calls/month

**Verdict:** The free tier (100 req/month) is **NOT sufficient**. The Basic plan (500 req/month) is tight. Options:
1. **Reduce sync frequency for Realtor.com** to every 12h or 24h → ~240–480 calls/month ✅ fits Basic plan
2. **Search by city instead of per-zip** → 1 call per page instead of 4 → ~120–240 calls/month ✅ fits Basic plan
3. **Combine both optimizations** → ~60–120 calls/month ✅ fits free tier

**Recommendation:** Search by city (`Sunnyvale, CA`) with `max_pages: 2`, synced every 12 hours. This yields ~120 calls/month, fitting comfortably within the Basic plan and leaving headroom.

### 2.3 Alternative APIs Considered

| API | Free Tier | Why Not |
|-----|-----------|---------|
| Realtor.com API (by apimaker) | 50 req/month | Too low for any useful scraping |
| Realtor16 (by Jeeves) | 100 req/month | Older version, less maintained |
| US Real Estate (by RealtyMole) | 50 req/month | Focused on property data, not rental search |
| Realty in US (by Mak) | 500 req/month | Less reliable uptime, sparse documentation |

### 2.4 Expected Response Structure

Based on the Realtor Search API documentation, the response for `/properties/search-rent` looks like:

```json
{
  "status": 200,
  "data": {
    "results": [
      {
        "property_id": "R1234567890",
        "listing_id": "2960123456",
        "status": "for_rent",
        "list_price": 5500,
        "description": {
          "beds": 3,
          "baths": 2,
          "sqft": 1800,
          "type": "single_family",
          "text": "Beautiful 3BR house..."
        },
        "location": {
          "address": {
            "line": "123 Main St",
            "city": "Sunnyvale",
            "state_code": "CA",
            "postal_code": "94086",
            "coordinate": {
              "lat": 37.3688,
              "lon": -122.0363
            }
          },
          "county": "Santa Clara",
          "neighborhood_name": "Downtown Sunnyvale"
        },
        "photos": [
          { "href": "https://ap.rdcpix.com/..." }
        ],
        "pet_policy": {
          "cats": true,
          "dogs": true,
          "text": "Cats and dogs OK"
        },
        "features": [
          { "category": "Parking", "text": ["2-car garage"] },
          { "category": "Laundry", "text": ["In-unit"] }
        ],
        "list_date": "2026-03-15T00:00:00Z"
      }
    ],
    "total": 42,
    "count": 20
  }
}
```

> ⚠️ **Note:** The exact response structure must be verified against the live API during implementation. The above is based on API documentation and may differ. The Code agent should make a test call and log the raw response before writing the `normalize()` method.

---

## 3. Configuration

### 3.1 New `realtor_api` section in [`config.yaml`](../config.yaml)

Add after the existing `zillow_api` section:

```yaml
# Realtor.com API (RapidAPI — Realtor Search by API_Jeeves)
# Sign up at https://rapidapi.com and subscribe to "Realtor Search" by API_Jeeves
# Basic plan: 500 requests/month (~$10/mo)
# Endpoint used: /properties/search-rent
realtor_api:
  rapidapi_key: ""  # Set via REALTOR_RAPIDAPI_KEY env var (or falls back to RAPIDAPI_KEY)
  rapidapi_host: "realtor-search.p.rapidapi.com"
  monthly_budget: 500       # API call limit per month
  budget_threshold: 450     # 90% — stop scraping when reached
  sync_interval_hours: 12   # Override: sync Realtor.com less frequently than Zillow
  enabled: true             # Can disable without removing config
```

### 3.2 API Key Strategy

**Decision: Use a SEPARATE environment variable `REALTOR_RAPIDAPI_KEY`** with fallback to `RAPIDAPI_KEY`.

Rationale:
- Zillow and Realtor.com are different RapidAPI subscriptions with separate billing
- The user may want to use different RapidAPI accounts for budget isolation
- Fallback to `RAPIDAPI_KEY` maintains backward compatibility if the user subscribes to both APIs under one RapidAPI account

Key resolution order in `__init__`:
```python
self.api_key = (
    os.environ.get("REALTOR_RAPIDAPI_KEY")
    or os.environ.get("RAPIDAPI_KEY")
    or realtor_cfg.get("rapidapi_key", "")
)
```

### 3.3 Environment Variable

Add to [`.env.example`](../.env.example):
```
# Realtor.com RapidAPI key (optional — falls back to RAPIDAPI_KEY if not set)
# Subscribe to "Realtor Search" by API_Jeeves on RapidAPI
REALTOR_RAPIDAPI_KEY=
```

---

## 4. Implementation — `RealtorScraper`

### 4.1 File: [`src/scrapers/realtor_scraper.py`](../src/scrapers/realtor_scraper.py)

**Class:** `RealtorScraper(BaseScraper)` — ~350–450 lines estimated.

### 4.2 `__init__(self)` — Constructor

Mirror the [`ZillowScraper.__init__`](../src/scrapers/zillow_scraper.py:74) pattern exactly:

```python
def __init__(self) -> None:
    config = load_config()  # with try/except FileNotFoundError
    
    realtor_cfg = config.get("realtor_api", {})
    self.api_key = (
        os.environ.get("REALTOR_RAPIDAPI_KEY")
        or os.environ.get("RAPIDAPI_KEY")
        or realtor_cfg.get("rapidapi_key", "")
    )
    self.api_host = realtor_cfg.get("rapidapi_host", "realtor-search.p.rapidapi.com")
    self.enabled = realtor_cfg.get("enabled", True)
    self.monthly_budget = realtor_cfg.get("monthly_budget", 500)
    self.budget_threshold = realtor_cfg.get("budget_threshold", 450)
    
    # Search params from shared config
    search_cfg = config.get("search", {})
    filters_cfg = config.get("filters", {})
    self.city = search_cfg.get("city", "Sunnyvale")
    self.state = search_cfg.get("state", "CA")
    self.min_price = filters_cfg.get("min_price", 5000)
    self.max_price = filters_cfg.get("max_price", 6500)
    self.min_beds = filters_cfg.get("min_bedrooms", 3)
    self.max_beds = filters_cfg.get("max_bedrooms", 4)
    
    # Scraper settings
    scraper_cfg = config.get("scraper", {})
    self.max_pages = scraper_cfg.get("max_pages", 2)
    self.delay_min = scraper_cfg.get("request_delay_min", 3)
    self.delay_max = scraper_cfg.get("request_delay_max", 8)
```

### 4.3 `scrape(self)` — Data Fetching

Follow the [`ZillowScraper.scrape()`](../src/scrapers/zillow_scraper.py:105) pattern:

1. **Guard: API key missing** → log warning, return `[]`
2. **Guard: `enabled` flag** → if `False`, log info, return `[]`
3. **Budget guard** → call [`get_api_call_count("realtor")`](../src/database.py:870) — skip if ≥ `budget_threshold`
4. **Calculate effective max pages** from remaining budget
5. **HTTP client** → `httpx.AsyncClient(timeout=30.0)`
6. **Search strategy** → Search by city/state (not per-zip) to minimize API calls:
   ```python
   params = {
       "city": self.city,
       "state_code": self.state,
       "status": "for_rent",
       "price_min": self.min_price,
       "price_max": self.max_price,
       "beds_min": self.min_beds,
       "beds_max": self.max_beds,
       "type": "single_family",  # Match our house-only filter
       "limit": 50,              # Results per page
       "offset": (page - 1) * 50,
   }
   ```
7. **Headers** → same RapidAPI pattern:
   ```python
   headers = {
       "x-rapidapi-key": self.api_key,
       "x-rapidapi-host": self.api_host,
   }
   ```
8. **Pagination** → loop through pages with offset, stop when:
   - No more results returned
   - Reached `effective_max_pages`
   - Total results exhausted (`offset >= total`)
9. **Log every call** → [`log_api_call("realtor", endpoint=url, status_code=code)`](../src/database.py:860)
10. **Error handling** → HTTP errors, rate limiting (429), JSON parse errors — identical to Zillow
11. **Random delays** → `asyncio.sleep(random.uniform(self.delay_min, self.delay_max))`
12. **Return** → list of raw property dicts from `data.results`

### 4.4 `normalize(self, raw)` — Field Mapping

Map Realtor.com API response fields to the [`Listing`](../src/models.py) model:

| Listing Field | Realtor.com Source Path | Notes |
|---------------|------------------------|-------|
| `external_id` | `raw["property_id"]` or `raw["listing_id"]` | Prefer `property_id` for stability |
| `source` | `"realtor"` | Hardcoded |
| `url` | `f"https://www.realtor.com/realestateandhomes-detail/{property_id}"` | Construct from property_id |
| `title` | `raw.get("description", {}).get("text", "")[:100]` or address | Truncate long descriptions |
| `address` | `location.address.line + city + state + zip` | Same format as Zillow: `"123 Main St, Sunnyvale, CA 94086"` |
| `neighborhood` | `location.get("neighborhood_name")` | Available in Realtor.com data ✅ |
| `city` | `location.address.city` | |
| `zip_code` | `location.address.postal_code` | |
| `price` | `raw["list_price"]` | Direct numeric field |
| `bedrooms` | `description.beds` | |
| `bathrooms` | `description.baths` | May be `baths_full` + `0.5 * baths_half` |
| `sqft` | `description.sqft` | |
| `property_type` | `_map_property_type(description.type)` | See mapping below |
| `pet_friendly` | `_extract_pet_friendly(raw)` | From `pet_policy` object |
| `parking` | `_extract_parking(raw)` | From `features` array |
| `laundry` | `_extract_laundry(raw)` | From `features` array |
| `image_urls` | `json.dumps([p["href"] for p in photos[:10]])` | Limit to 10 images |
| `latitude` | `location.address.coordinate.lat` | |
| `longitude` | `location.address.coordinate.lon` | Note: `lon` not `lng` |
| `listed_date` | `raw.get("list_date")` | Parse ISO 8601 string to `date` |

### 4.5 Property Type Mapping

```python
_PROPERTY_TYPE_MAP: dict[str, str] = {
    "single_family": "house",
    "multi_family": "apartment",
    "apartment": "apartment",
    "condo": "condo",
    "condos": "condo",
    "townhomes": "townhouse",
    "townhouse": "townhouse",
    "duplex_triplex": "apartment",
    "farm": "house",
    "land": "house",
    "mobile": "house",
    "mfd_mobile_home": "house",
}
```

### 4.6 Helper Methods

#### `_extract_price(raw) -> float | None`
```python
# Realtor.com is simpler than Zillow — price is usually at top level
price = raw.get("list_price")
if price and isinstance(price, (int, float)) and price > 0:
    return float(price)
# Fallback: check list_price_min for ranges
return raw.get("list_price_min")
```

#### `_extract_pet_friendly(raw) -> bool | None`
```python
pet_policy = raw.get("pet_policy", {})
if not pet_policy:
    return None
# Check explicit boolean fields
if pet_policy.get("cats") or pet_policy.get("dogs"):
    return True
# Check text description
text = pet_policy.get("text", "").lower()
if any(kw in text for kw in ("dog", "cat", "pet", "allowed", "ok")):
    return True
if any(kw in text for kw in ("no pet", "not allowed", "none")):
    return False
return None
```

#### `_extract_parking(raw) -> str | None`
```python
features = raw.get("features", [])
for feature in features:
    if feature.get("category", "").lower() in ("parking", "garage"):
        texts = feature.get("text", [])
        if texts:
            return ", ".join(texts)
# Fallback: check description.garage field
garage = raw.get("description", {}).get("garage")
if garage and isinstance(garage, (int, float)) and garage > 0:
    return f"{int(garage)}-car garage"
return None
```

#### `_extract_laundry(raw) -> str | None`
```python
features = raw.get("features", [])
for feature in features:
    if feature.get("category", "").lower() == "laundry":
        texts = feature.get("text", [])
        combined = ", ".join(texts).lower()
        if "in unit" in combined or "in-unit" in combined:
            return "in-unit"
        if "hookup" in combined:
            return "hookups"
        if "shared" in combined or "common" in combined:
            return "shared"
        return ", ".join(texts) if texts else None
return None
```

#### `_parse_list_date(raw) -> date | None`
```python
list_date_str = raw.get("list_date")
if not list_date_str:
    return None
try:
    # ISO 8601: "2026-03-15T00:00:00Z"
    return datetime.fromisoformat(list_date_str.replace("Z", "+00:00")).date()
except (ValueError, AttributeError):
    return None
```

---

## 5. Integration Points — Files to Modify

### 5.1 [`src/orchestrator.py`](../src/orchestrator.py) — Add to scraper list

**Lines affected:** ~25 (import) and ~35–38 (`__init__`)

```python
# Add import
from src.scrapers.realtor_scraper import RealtorScraper

# Add to self._scrapers list
self._scrapers = [
    ("zillow", ZillowScraper()),
    ("craigslist", CraigslistScraper()),
    ("realtor", RealtorScraper()),       # ← NEW
]
```

No other orchestrator changes needed — the existing `asyncio.gather` + normalize + enrich pipeline handles any number of scrapers automatically.

### 5.2 [`config.yaml`](../config.yaml) — New `realtor_api` section

Add after line 52 (after `zillow_api` section):

```yaml
# Realtor.com API (RapidAPI — Realtor Search by API_Jeeves)
# Subscribe at https://rapidapi.com → "Realtor Search" by API_Jeeves
# Basic plan: 500 requests/month (~$10/mo)
# Endpoint used: /properties/search-rent
realtor_api:
  rapidapi_key: ""  # Set via REALTOR_RAPIDAPI_KEY env var (or falls back to RAPIDAPI_KEY)
  rapidapi_host: "realtor-search.p.rapidapi.com"
  monthly_budget: 500
  budget_threshold: 450
  enabled: true
```

### 5.3 [`.env.example`](../.env.example) — Document new env var

Add after `RAPIDAPI_KEY=`:

```
# Realtor.com RapidAPI key (optional — falls back to RAPIDAPI_KEY if not set)
# Subscribe to "Realtor Search" by API_Jeeves on RapidAPI
REALTOR_RAPIDAPI_KEY=
```

### 5.4 [`web/main.py`](../web/main.py) — Extend startup validation

Add to [`_validate_environment()`](../web/main.py:31) after the `RAPIDAPI_KEY` check:

```python
# --- REALTOR_RAPIDAPI_KEY (Realtor.com scraper) ---
realtor_key = os.environ.get("REALTOR_RAPIDAPI_KEY") or os.environ.get("RAPIDAPI_KEY")
if not realtor_key:
    try:
        config = load_config()
        realtor_enabled = config.get("realtor_api", {}).get("enabled", True)
    except FileNotFoundError:
        realtor_enabled = True
    if realtor_enabled:
        logger.warning(
            "⚠️  REALTOR_RAPIDAPI_KEY is not set (and RAPIDAPI_KEY fallback is also missing) "
            "— Realtor.com scraper will be disabled. "
            "Set it in .env or as an environment variable."
        )
        has_warnings = True
```

### 5.5 [`web/dependencies.py`](../web/dependencies.py) — Extend `get_env_status()`

Add Realtor.com key status to the health check dict returned by `get_env_status()`:

```python
"REALTOR_RAPIDAPI_KEY": bool(
    os.environ.get("REALTOR_RAPIDAPI_KEY") or os.environ.get("RAPIDAPI_KEY")
),
```

### 5.6 [`web/routes/admin.py`](../web/routes/admin.py) — Extend API usage route

The [`admin_api_usage()`](../web/routes/admin.py:334) route currently only tracks Zillow. It needs to become **multi-source aware**.

**Changes to [`admin_api_usage()`](../web/routes/admin.py:334):**

```python
@router.get("/api-usage")
async def admin_api_usage(request: Request):
    """API call tracking and budget monitoring — multi-source."""
    
    # --- Zillow budget ---
    zillow_calls = get_api_call_count("zillow")
    zillow_daily = get_api_calls_by_day("zillow")
    zillow_recent = get_recent_api_calls("zillow", 25)
    
    # --- Realtor.com budget ---
    realtor_calls = get_api_call_count("realtor")
    realtor_daily = get_api_calls_by_day("realtor")
    realtor_recent = get_recent_api_calls("realtor", 25)
    
    # Load config for budget limits
    config = load_config()
    zillow_budget = API_BUDGET_LIMIT  # 500
    realtor_cfg = config.get("realtor_api", {})
    realtor_budget = realtor_cfg.get("monthly_budget", 500)
    
    # Build per-source budget data
    sources = [
        _build_budget_data("Zillow", "zillow", zillow_calls, zillow_budget, 
                           zillow_daily, zillow_recent, config.get("zillow_api", {})),
        _build_budget_data("Realtor.com", "realtor", realtor_calls, realtor_budget,
                           realtor_daily, realtor_recent, realtor_cfg),
    ]
    
    # ... pass `sources` list to template
```

Add a helper function `_build_budget_data()` that computes budget_pct, budget_status, projected, remaining, daily_avg, etc. for any source — DRY refactor of the current Zillow-only logic.

### 5.7 [`web/templates/admin/api-usage.html`](../web/templates/admin/api-usage.html) — Multi-source UI

Refactor the template to iterate over a `sources` list instead of hardcoding Zillow:

```html
{% for source in sources %}
<div class="source-section">
    <h2 class="section-title">{{ source.display_name }} API</h2>
    
    <!-- Budget KPIs (same 4-card grid, per source) -->
    <div class="kpi-grid kpi-grid-4">
        <!-- Budget Used / Projected / Daily Avg / Remaining -->
    </div>
    
    <!-- Last API Call indicator -->
    <!-- Daily Usage chart -->
    <!-- Recent Calls table -->
    <!-- API Configuration -->
</div>
{% endfor %}
```

### 5.8 [`web/templates/admin/dashboard.html`](../web/templates/admin/dashboard.html) — KPI update

The admin dashboard currently shows a single "API Budget" KPI card for Zillow. Options:
- **Option A:** Show combined budget across all API sources
- **Option B:** Show the worst-case budget status (whichever source is closest to limit)

**Recommendation:** Option B — show the source with the highest budget utilization percentage, with a tooltip showing both.

### 5.9 [`web/templates/admin/settings.html`](../web/templates/admin/settings.html) — Config display

The settings page displays config sections. The new `realtor_api` section will need to be added to the config display. This should happen automatically if the settings route iterates over all config keys, but verify.

### 5.10 Source Filter Dropdown — Auto-populates ✅

The source filter dropdown in the dashboard is populated from [`get_source_counts()`](../src/database.py:820) which queries the `listing_sources` table with `GROUP BY source`. When Realtor.com listings are inserted, `"realtor"` will automatically appear in the dropdown. **No UI changes needed.**

### 5.11 [`src/models.py`](../src/models.py) — ListingSource docstring

Update the [`ListingSource`](../src/models.py:28) docstring to include `"realtor"` in the source examples:

```python
source: Origin site — ``"zillow"``, ``"craigslist"``, or ``"realtor"``.
```

---

## 6. Files Summary

| File | Action | Description |
|------|--------|-------------|
| `src/scrapers/realtor_scraper.py` | **CREATE** | New scraper class (~350–450 lines) |
| `src/orchestrator.py` | **MODIFY** | Add import + append to `self._scrapers` (2 lines) |
| `config.yaml` | **MODIFY** | Add `realtor_api` section (~10 lines) |
| `.env.example` | **MODIFY** | Add `REALTOR_RAPIDAPI_KEY` documentation (3 lines) |
| `web/main.py` | **MODIFY** | Extend `_validate_environment()` (~12 lines) |
| `web/dependencies.py` | **MODIFY** | Extend `get_env_status()` (3 lines) |
| `web/routes/admin.py` | **MODIFY** | Refactor `admin_api_usage()` to multi-source + add `_build_budget_data()` helper (~60 lines) |
| `web/templates/admin/api-usage.html` | **MODIFY** | Refactor to iterate over sources list (~80 lines changed) |
| `web/templates/admin/dashboard.html` | **MODIFY** | Update API budget KPI to multi-source (~10 lines) |
| `web/templates/admin/settings.html` | **VERIFY** | Confirm `realtor_api` section auto-displays |
| `src/models.py` | **MODIFY** | Update `ListingSource` docstring (1 line) |

**Total: 1 new file, 9 modified files, 1 verification**

---

## 7. Deduplication Considerations

Realtor.com listings will overlap significantly with Zillow listings (both aggregate from MLS data). The existing [deduplication pipeline](../src/dedup.py) in the orchestrator (step 6) handles this:

1. **Address normalization** → same address from Zillow and Realtor.com will match
2. **Candidate narrowing** → `zip_code + bedrooms` filter before scoring
3. **Merge strategy** → existing listing is canonical; Realtor.com data gap-fills NULL fields
4. **`listing_sources` table** → a single listing can have entries for `"zillow"`, `"craigslist"`, AND `"realtor"`

**No dedup changes needed** — the existing system handles N sources automatically.

---

## 8. Testing Strategy

### 8.1 Manual Verification Steps

1. **API connectivity test** — Make a single test call to verify the API key works and response format matches expectations
2. **Raw response logging** — Log the first raw response to verify field paths before writing `normalize()`
3. **Normalize accuracy** — Compare 5 listings manually: Realtor.com website vs. normalized output
4. **Dedup verification** — Check that listings appearing on both Zillow and Realtor.com are properly merged
5. **Budget guard test** — Verify the scraper skips when `get_api_call_count("realtor")` exceeds threshold

### 8.2 Unit Tests (recommended)

- `test_normalize_standard_listing()` — standard single-family rental
- `test_normalize_missing_fields()` — graceful handling of None/missing data
- `test_extract_pet_friendly()` — various pet_policy formats
- `test_extract_parking()` — garage, parking features
- `test_extract_laundry()` — in-unit, shared, hookups
- `test_map_property_type()` — all known Realtor.com property types
- `test_budget_guard()` — scraper returns `[]` when over budget

---

## 9. Rollout Plan

### Phase 1: Scraper Implementation (4–6 hours)
1. Create `src/scrapers/realtor_scraper.py`
2. Add `realtor_api` section to `config.yaml`
3. Add `REALTOR_RAPIDAPI_KEY` to `.env.example`
4. Add import + registration in `src/orchestrator.py`
5. Test with a single API call

### Phase 2: Admin UI Updates (3–5 hours)
1. Refactor `admin_api_usage()` route to multi-source
2. Refactor `api-usage.html` template to iterate over sources
3. Update admin dashboard KPI
4. Extend startup validation
5. Extend `get_env_status()`

### Phase 3: Verification (1–3 hours)
1. Run full sync and verify listings appear
2. Check dedup merges Zillow ↔ Realtor.com duplicates
3. Verify source filter dropdown shows "realtor"
4. Verify API usage page shows both sources
5. Monitor budget consumption over 24 hours

---

## 10. Open Questions for Owner

1. **API plan budget:** Are you willing to pay ~$10/month for the Basic plan (500 req/month), or should we optimize to fit the free tier (100 req/month) by reducing sync frequency to once daily?

2. **API key sharing:** Should Realtor.com use the same RapidAPI account as Zillow (shared `RAPIDAPI_KEY`), or a separate account (`REALTOR_RAPIDAPI_KEY`)? The plan supports both via fallback.

3. **Sync frequency:** Should Realtor.com sync at the same interval as Zillow (every 6 hours per `schedule.interval_hours`), or at a reduced frequency (every 12 or 24 hours) to conserve API budget? The plan recommends 12 hours.

4. **Property types:** Currently the orchestrator filters out non-house listings (line 108–117 in [`orchestrator.py`](../src/orchestrator.py:108)). Should we also request only `single_family` from the Realtor.com API (saving API bandwidth), or fetch all types and let the orchestrator filter?

5. **Source display name:** In the UI, should the source show as `"realtor"`, `"realtor.com"`, or `"Realtor.com"`? The database stores lowercase (`"realtor"`), but the display name in the admin panel and filter dropdown could be formatted differently.

6. **API verification:** Before committing to the Realtor Search API, should we first make a test call to verify the response format matches the documentation? The Code agent can do this as step 1 of Phase 1.

---

## 11. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| API response format differs from docs | Medium | High | Test call before writing normalize(); log raw responses |
| Free tier insufficient | High | Medium | Budget for Basic plan; optimize search strategy |
| High overlap with Zillow (wasted API calls) | High | Low | Existing dedup handles this; value is in gap-filling |
| API rate limiting (429) | Low | Low | Existing retry/backoff pattern from Zillow scraper |
| API deprecation/changes | Low | High | `enabled` flag allows quick disable; monitor API status |

---

## 12. Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                   ScraperOrchestrator                    │
│                                                         │
│  self._scrapers = [                                     │
│    ("zillow",     ZillowScraper()),     ← RapidAPI     │
│    ("craigslist", CraigslistScraper()), ← Playwright   │
│    ("realtor",    RealtorScraper()),     ← RapidAPI NEW │
│  ]                                                      │
│                                                         │
│  asyncio.gather(                                        │
│    _safe_scrape("zillow", ...),                         │
│    _safe_scrape("craigslist", ...),                     │
│    _safe_scrape("realtor", ...),   ← NEW               │
│  )                                                      │
│                                                         │
│  For each source's results:                             │
│    1. normalize()                                       │
│    2. filter $0 prices                                  │
│    3. filter non-house types                            │
│    4. geocode                                           │
│    5. school district + school assignment               │
│    6. sqm conversion                                    │
│    7. upsert                                            │
│    8. dedup (cross-source)                              │
│    9. price snapshot                                    │
│   10. mark inactive                                     │
└─────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
   ┌──────────┐      ┌──────────────┐     ┌──────────────┐
   │  Zillow   │      │  Craigslist  │     │  Realtor.com │
   │  RapidAPI │      │  Playwright  │     │  RapidAPI    │
   │  500/mo   │      │  No limit    │     │  500/mo      │
   │  RAPIDAPI │      │  (rate-      │     │  REALTOR_    │
   │  _KEY     │      │   limited)   │     │  RAPIDAPI_KEY│
   └──────────┘      └──────────────┘     └──────────────┘
```

---

*This plan is detailed enough for a Code mode agent to implement without ambiguity. All file paths, function signatures, field mappings, and integration points are specified.*
