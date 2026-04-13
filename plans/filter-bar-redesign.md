# Filter Bar Redesign — Zillow-Inspired

> **Status**: PROPOSAL — awaiting product owner review  
> **Author**: UX Designer  
> **Date**: 2026-03-31  
> **Depends on**: Design Bible ([`design-bible.md`](../docs/design/design-bible.md)), Filter Search UX Skill ([`.roo/skill-filter-search-ux.md`](../.roo/skill-filter-search-ux.md))

---

## Table of Contents

1. [Current State Audit](#1-current-state-audit)
2. [Proposed Design Overview](#2-proposed-design-overview)
3. [Filter-by-Filter Spec](#3-filter-by-filter-spec)
4. [HTMX Integration Notes](#4-htmx-integration-notes)
5. [Implementation Approach](#5-implementation-approach)
6. [Design Tokens](#6-design-tokens)
7. [ASCII Mockup](#7-ascii-mockup)
8. [Open Questions](#8-open-questions)

---

## 1. Current State Audit

### What We Have Today

The current filter bar lives in [`dashboard.html:4–63`](../web/templates/dashboard.html:4) with CSS in [`style.css:63–151`](../web/static/css/style.css:63).

| Element | Current Implementation |
|---------|----------------------|
| **Layout** | Sticky header (56px), flex row: Logo → Filter pills → Admin link |
| **Price** | Native `<select>` with 7 hardcoded ranges (Under $4K through $8K+) |
| **Beds** | Native `<select>` with 5 options (Any, 1+, 2+, 3+, 4+, 5+) |
| **Baths** | Native `<select>` with 4 options (Any, 1+, 2+, 3+) |
| **Source** | Native `<select>` with 3 options (All, Zillow, Craigslist) |
| **Sort** | Native `<select>` with 3 options (Newest, Price ↑, Price ↓) |
| **Interaction** | Each `<select>` fires `hx-get="/listings"` on change (instant, no Apply button) |
| **Active state** | None — pill looks the same whether "Any" or a specific value is selected |
| **Styling** | Pill-shaped (`border-radius: 16px`), white bg, gray border, custom SVG arrow |

### What Works ✅

- **Instant filtering via HTMX** — no page reload, results update immediately
- **Pill shape** — matches Design Bible (`--radius-pill: 16px`)
- **Sticky positioning** — filter bar stays visible while scrolling listings
- **Compact layout** — all 5 filters fit in one row without overflow
- **`hx-include="[name^='filter_']"`** — elegant pattern that auto-includes all filter values

### What Doesn't Work ❌

| Issue | Impact | Zillow Comparison |
|-------|--------|-------------------|
| **No active state** — can't tell which filters are applied | Users forget they have filters set, wonder why results are limited | Zillow shows selected value text + blue border on active pills |
| **No "Clear All" / Reset** — no way to reset all filters at once | Users must manually reset each dropdown to "Any" | Zillow has "Reset all filters" link in More panel |
| **Hardcoded price ranges** — can't enter custom min/max | Users can't search for $4,500–$5,500 (falls between our buckets) | Zillow has Min/Max text inputs for precise ranges |
| **Beds & Baths separate** — takes 2 pills for related criteria | Wastes horizontal space; Zillow combines them | Zillow uses one "Beds & Baths" dropdown with segmented buttons |
| **No "More" filters** — sqft, listed_date exist in DB but aren't exposed | Users can't filter by size or recency | Zillow has "More" overflow panel for secondary filters |
| **Native `<select>` styling** — limited visual control | Can't show rich content (button groups, inputs) in dropdown | Zillow uses custom dropdown panels with rich UI |
| **No result count in filter bar** — count is below in left panel | Users don't see filter impact immediately | Zillow shows count inline |

### Backend Filter Support (Already Implemented)

The [`get_filtered_listings()`](../src/database.py:158) function in [`database.py`](../src/database.py) already supports these filter keys that we're **not exposing in the UI**:

| Filter Key | DB Support | Currently in UI? |
|------------|-----------|-----------------|
| `min_price` / `max_price` | ✅ | ⚠️ Hardcoded ranges only |
| `min_bedrooms` / `max_bedrooms` | ✅ | ⚠️ Min only (1+, 2+, etc.) |
| `min_bathrooms` / `max_bathrooms` | ✅ | ⚠️ Min only |
| `min_sqft` / `max_sqft` | ✅ | ❌ Not exposed |
| `property_type` | ✅ | ❌ Hardcoded to "house" |
| `pet_friendly` | ✅ | ❌ Not exposed |
| `parking` | ✅ | ❌ Not exposed |
| `laundry` | ✅ | ❌ Not exposed |
| `ac` | ✅ | ❌ Not exposed |
| `furnished` | ✅ | ❌ Not exposed |
| `school_district` | ✅ | ❌ Not exposed |
| `neighborhood` | ✅ | ❌ Not exposed |
| `source` | ✅ | ✅ |

**Key insight**: The backend already supports rich filtering — the UI is the bottleneck.

---

## 2. Proposed Design Overview

### Design Philosophy

> **Practical Zillow, not pixel-perfect Zillow.** We adopt the interaction patterns that improve UX (dropdown panels, segmented buttons, active states) but skip features that don't make sense at our scale (histogram visualization, save search, map-based search).

### Core Changes

| Change | Rationale | Complexity |
|--------|-----------|------------|
| Replace native `<select>` with custom dropdown panels | Enables rich content (inputs, button groups) | Medium |
| Add active filter state (blue border + value text) | Users can see which filters are applied at a glance | Low |
| Combine Beds & Baths into one dropdown | Saves space, matches Zillow pattern | Low |
| Add Min/Max text inputs for Price | Enables precise price ranges | Low |
| Add "More" overflow dropdown | Exposes sqft filter + reset all | Medium |
| Add "Reset Filters" action | Quick way to clear all filters | Low |

### What We're NOT Doing (and Why)

| Zillow Feature | Why We Skip It |
|----------------|---------------|
| **Price histogram** | We have ~23 listings — histogram would be meaningless |
| **Dual-handle range slider** | Adds JS complexity; text inputs are sufficient for our scale |
| **Save Search button** | No user accounts; single-user app |
| **Home Type dropdown** | We only ingest houses — no need for a type filter |
| **Move-In Date picker** | `available_date` is rarely populated in our data |
| **Lot Size / Year Built** | Not in our data model |
| **Number of Stories** | Not in our data model |
| **Basement checkbox** | Not in our data model |

---

## 3. Filter-by-Filter Spec

### 3.1 Price Filter

**Pill button label**: `💰 Price` (default) → `$4K–$6K` (when set)

#### Dropdown Panel

```
┌─────────────────────────────────┐
│  Price Range                    │
│                                 │
│  ┌──────────┐  ┌──────────┐    │
│  │ Min ($)  │  │ Max ($)  │    │
│  │ No Min   │  │ No Max   │    │
│  └──────────┘  └──────────┘    │
│                                 │
│  Quick ranges:                  │
│  ○ Under $4,000                 │
│  ○ $4,000 – $5,000              │
│  ○ $5,000 – $6,000              │
│  ○ $5,000 – $6,500              │
│  ○ $6,000 – $7,000              │
│  ○ $7,000 – $8,000              │
│  ○ $8,000+                      │
│                                 │
│  ┌─────────────────────────┐    │
│  │        Apply            │    │
│  └─────────────────────────┘    │
└─────────────────────────────────┘
```

#### Interaction Pattern

| Action | Behavior |
|--------|----------|
| Click pill | Opens dropdown panel below pill |
| Type in Min/Max | Deselects any quick range radio; enables Apply button |
| Click quick range | Populates Min/Max fields with range values |
| Click Apply | Closes panel, updates pill text, fires HTMX request |
| Click outside panel | Closes panel **without applying** (reverts to previous state) |
| Press Escape | Same as click outside — closes without applying |
| Press Enter (in input) | Same as clicking Apply |

#### Active State

- **Default**: `💰 Price` — gray border (`#d1d5db`)
- **Active**: `$5K–$6.5K` — blue border (`#2563eb`), light blue background (`#f0f4ff`)
- Pill text updates to show the selected range in compact format (e.g., `$5K–$6.5K`, `Under $4K`, `$8K+`)

#### Accessibility

- Panel has `role="dialog"` and `aria-label="Price range filter"`
- Min/Max inputs have `<label>` elements (visually hidden if needed)
- Quick range options are `<input type="radio">` with `<label>` — keyboard navigable
- Apply button is focusable; focus trapped inside panel while open
- `aria-expanded="true/false"` on the pill button
- `aria-haspopup="dialog"` on the pill button
- When panel opens, focus moves to first input (Min)
- When panel closes, focus returns to the pill button

#### Backend Integration

- Min/Max values map directly to existing `min_price` / `max_price` filter keys
- Quick ranges populate the same `filter_price` query param format (e.g., `5000-6500`)
- Custom min/max sends `filter_price_min=5000&filter_price_max=6500` (new params)
- [`parse_filters()`](../web/routes/__init__.py:6) needs update to accept `filter_price_min` / `filter_price_max` alongside the existing range format

---

### 3.2 Beds & Baths (Combined)

**Pill button label**: `🛏️ Beds & Baths` (default) → `3+ bd, 2+ ba` (when set)

#### Dropdown Panel

```
┌─────────────────────────────────────┐
│  Number of Bedrooms                 │
│                                     │
│  ┌─────┬─────┬─────┬─────┬─────┐   │
│  │ Any │ 1+  │ 2+  │ 3+  │ 4+  │   │
│  └─────┴─────┴─────┴─────┴─────┘   │
│                                     │
│  Number of Bathrooms                │
│                                     │
│  ┌─────┬─────┬─────┬─────┐         │
│  │ Any │ 1+  │ 2+  │ 3+  │         │
│  └─────┴─────┴─────┴─────┘         │
│                                     │
│  ┌─────────────────────────────┐    │
│  │           Apply             │    │
│  └─────────────────────────────┘    │
└─────────────────────────────────────┘
```

#### Segmented Button Group Design

- Buttons are visually connected (shared border, no gap)
- Selected button: `background: #2563eb`, `color: #fff`, `font-weight: 600`
- Unselected button: `background: #fff`, `color: var(--text-primary)`, `border: 1px solid #d1d5db`
- Hover (unselected): `background: #f0f4ff`, `border-color: rgba(59,130,246,0.4)`
- Each button is 48px wide × 36px tall (meets 44px touch target minimum)
- Border radius: first button gets left radius (8px), last button gets right radius (8px), middle buttons have 0 radius

#### Interaction Pattern

| Action | Behavior |
|--------|----------|
| Click pill | Opens dropdown panel |
| Click segment button | Selects that option (visual feedback immediate) |
| Click Apply | Closes panel, updates pill text, fires HTMX request |
| Click outside | Closes without applying (reverts selection) |
| Press Escape | Same as click outside |

#### Active State

- **Default**: `🛏️ Beds & Baths` — gray border
- **Beds only**: `3+ bd` — blue border
- **Baths only**: `2+ ba` — blue border
- **Both**: `3+ bd, 2+ ba` — blue border
- Emoji removed from pill text when active (value text is sufficient)

#### Accessibility

- Segmented buttons use `role="radiogroup"` with `aria-label="Number of Bedrooms"` / `"Number of Bathrooms"`
- Each button is `role="radio"` with `aria-checked="true/false"`
- Arrow keys navigate between options within a group
- Tab moves between the two groups (Bedrooms → Bathrooms → Apply)
- Selected button has `aria-checked="true"` and visual indicator (not color alone — uses filled background + bold text)

#### Backend Integration

- Maps to existing `min_bedrooms` and `min_bathrooms` filter keys
- Query params: `filter_beds=3&filter_baths=2` (same as current)
- No backend changes needed

---

### 3.3 Source Filter

**Recommendation**: Keep as a simple `<select>` dropdown — **no redesign needed**.

#### Rationale

- Only 2 options (Zillow, Craigslist) + "All" — a rich dropdown panel would be overkill
- Native `<select>` works fine for 3 options
- The current instant-on-change HTMX behavior is ideal for this filter

#### Only Change: Active State

- When source ≠ "All", the pill gets the active style (blue border + light blue bg)
- Pill text changes from `📡 Source` to `📡 Zillow` or `📡 Craigslist`

#### Accessibility

- Already accessible as a native `<select>` element
- Add `aria-label="Filter by listing source"` for screen readers

---

### 3.4 Sort Control

**Recommendation**: Keep as a simple `<select>` dropdown — **no redesign needed**.

#### Rationale

- Sort is not a filter — it doesn't reduce results, just reorders them
- 3 options is perfect for a native `<select>`
- Instant-on-change is the right behavior for sort

#### Visual Differentiation

- Move sort to the **right side** of the filter bar (after a visual separator)
- This separates "what to show" (filters) from "how to order" (sort)
- Sort pill does NOT get the active blue border treatment (it always has a value)

#### Layout Change

```
[Logo] [Price ▾] [Beds & Baths ▾] [Source ▾] [More ▾]  |  [Sort ▾] [Admin →]
```

The `|` is a 1px vertical divider (`border-left: 1px solid #e2e8f0`, height 24px).

---

### 3.5 "More" Overflow Dropdown

**Pill button label**: `⚙️ More` (default) → `⚙️ More (2)` (when N filters active)

#### Dropdown Panel

```
┌───────────────────────────────────────────┐
│  Additional Filters                       │
│                                           │
│  Square Feet                              │
│  ┌──────────┐  ┌──────────┐              │
│  │ Min sqft │  │ Max sqft │              │
│  │ No Min   │  │ No Max   │              │
│  └──────────┘  └──────────┘              │
│  (Shows as: "800–1,500 sqft (74–139 m²)")│
│                                           │
│  ─────────────────────────────────────    │
│                                           │
│  Features                                 │
│  ☐ Pet Friendly                           │
│  ☐ Air Conditioning                       │
│  ☐ Furnished                              │
│                                           │
│  ─────────────────────────────────────    │
│                                           │
│  ⟲ Reset all filters                     │
│                                           │
│  ┌─────────────────────────────────┐      │
│  │            Apply                │      │
│  └─────────────────────────────────┘      │
└───────────────────────────────────────────┘
```

#### What's Included (and Why)

| Filter | Included? | Rationale |
|--------|-----------|-----------|
| **Square Feet** (min/max) | ✅ | `sqft` exists in DB, useful for size-conscious renters |
| **Pet Friendly** | ✅ | `pet_friendly` exists in DB, common deal-breaker |
| **Air Conditioning** | ✅ | `ac` exists in DB, important in Sunnyvale summers |
| **Furnished** | ✅ | `furnished` exists in DB, relevant for short-term renters |
| **Parking** | ❌ Skip for now | Data is sparse (mostly NULL) |
| **Laundry** | ❌ Skip for now | Data is sparse |
| **School District** | ❌ Skip for now | Only useful with more listings |
| **Neighborhood** | ❌ Skip for now | Data is sparse |

#### Sqft Display Rule

Per Design Bible: always show BOTH sqft AND m². The sqft inputs accept sqft values, but the preview text below shows both:

> `800–1,500 sqft (74–139 m²)`

Conversion: `m² = Math.round(sqft × 0.0929)`

#### "Reset All Filters" Behavior

- Styled as a text link (not a button): `color: #2563eb`, `text-decoration: underline`
- Resets ALL filters (Price, Beds, Baths, Source, Sqft, Features) to defaults
- Closes the More panel
- Fires a single HTMX request with all params set to defaults
- Updates all pill button labels back to their default text
- Removes active state (blue border) from all pills

#### Interaction Pattern

| Action | Behavior |
|--------|----------|
| Click pill | Opens dropdown panel |
| Type in sqft fields | Enables Apply button |
| Toggle checkboxes | Enables Apply button |
| Click Apply | Closes panel, updates pill badge count, fires HTMX request |
| Click "Reset all filters" | Resets everything, closes panel, fires HTMX request |
| Click outside | Closes without applying |

#### Active State

- **Default**: `⚙️ More` — gray border
- **1+ filters active**: `⚙️ More (2)` — blue border, count badge shows number of active "More" filters
- The count badge is a small inline number, not a separate element

#### Accessibility

- Panel has `role="dialog"` and `aria-label="Additional filters"`
- Sqft inputs have associated `<label>` elements
- Checkboxes are native `<input type="checkbox">` with `<label>` — fully keyboard accessible
- "Reset all filters" is a `<button>` (not `<a>`) with `aria-label="Reset all filters to defaults"`
- Focus management: focus moves to first input on open, returns to pill on close

#### Backend Integration

- Sqft maps to existing `min_sqft` / `max_sqft` filter keys
- Checkboxes map to existing `pet_friendly`, `ac`, `furnished` boolean filter keys
- New query params: `filter_sqft_min`, `filter_sqft_max`, `filter_pet`, `filter_ac`, `filter_furnished`
- [`parse_filters()`](../web/routes/__init__.py:6) needs update to accept these new params
- [`filtered_listings()`](../web/routes/listings.py:20) needs new `Query()` parameters

---

## 4. HTMX Integration Notes

### Current Pattern (Keep)

The existing HTMX pattern is elegant and should be preserved:

```html
<select hx-get="/listings" hx-target="#listing-cards" hx-include="[name^='filter_']">
```

- `hx-get="/listings"` — fetches filtered listing cards partial
- `hx-target="#listing-cards"` — swaps the listing cards container
- `hx-include="[name^='filter_']"` — auto-includes ALL inputs with `name` starting with `filter_`

### Adaptation for Custom Dropdowns

Custom dropdown panels can't use `hx-get` on `<select>` change events. Instead:

#### Option A: Apply Button Triggers HTMX (Recommended)

```html
<!-- Hidden inputs hold the current filter values -->
<input type="hidden" name="filter_price_min" value="">
<input type="hidden" name="filter_price_max" value="">
<input type="hidden" name="filter_beds" value="any">
<input type="hidden" name="filter_baths" value="any">
<input type="hidden" name="filter_sqft_min" value="">
<input type="hidden" name="filter_sqft_max" value="">
<input type="hidden" name="filter_pet" value="">
<input type="hidden" name="filter_ac" value="">
<input type="hidden" name="filter_furnished" value="">

<!-- Apply button fires the HTMX request -->
<button class="filter-apply-btn"
        hx-get="/listings"
        hx-target="#listing-cards"
        hx-include="[name^='filter_']">
    Apply
</button>
```

**Flow**:
1. User interacts with dropdown panel (selects options, types values)
2. JavaScript updates the hidden `<input>` values
3. User clicks Apply → HTMX fires `GET /listings` with all `filter_*` params
4. Panel closes, pill text updates

#### Why Apply Button (Not Instant)

For **Price** and **More** filters, an Apply button is better than instant filtering because:
- Users may want to set both Min AND Max before seeing results
- Prevents unnecessary intermediate requests (e.g., typing "5" then "0" then "0" then "0" = 4 requests)
- Matches Zillow's pattern for complex filters

For **Source** and **Sort**, keep instant-on-change (they're simple single-value selects).

### OOB Result Count Update

The current OOB (Out-of-Band) swap for result count should continue working:

```html
<!-- In listing-cards.html partial response -->
<div id="result-count" hx-swap-oob="true" class="result-count">
    <span class="result-count-number">{{ listing_count }}</span> listings
</div>
```

### Map Refresh

When filters change, the map markers also need to update. Current approach:
- The HTMX response includes listing data that JavaScript uses to refresh markers
- This pattern should continue — the Apply button's HTMX request triggers the same flow

### URL State (Future Enhancement)

Currently, filter state is NOT preserved in the URL. A future enhancement could:
- Push filter params to URL via `history.pushState()` after each filter change
- Read URL params on page load to restore filter state
- This is a P2 item — not part of this redesign

---

## 5. Implementation Approach

### Technology

- **Pure HTML/CSS/JS** — no framework (consistent with existing codebase)
- **HTMX** — for server communication (already in use)
- **Jinja2** — for server-side rendering of initial filter state
- **No build step** — all JS is vanilla, inline or in a single file

### File Changes

| File | Change Type | Description |
|------|------------|-------------|
| [`dashboard.html`](../web/templates/dashboard.html) | **Major rewrite** | Replace `<select>` elements with custom dropdown pill + panel HTML |
| [`style.css`](../web/static/css/style.css) | **Add ~200 lines** | Dropdown panel styles, segmented buttons, active states, transitions |
| [`__init__.py`](../web/routes/__init__.py) | **Extend** | Add new filter params to `parse_filters()` |
| [`listings.py`](../web/routes/listings.py) | **Extend** | Add new `Query()` parameters for sqft, pet, ac, furnished |
| [`dashboard.py`](../web/routes/dashboard.py) | **Extend** | Pass new filter params to initial page load |
| New: `web/static/js/filters.js` | **Create** | Dropdown open/close logic, Apply handlers, active state management |

### Estimated Complexity

| Component | Effort | Notes |
|-----------|--------|-------|
| Dropdown panel open/close JS | 2–3h | Click outside detection, escape key, focus trap |
| Price dropdown panel HTML/CSS | 1–2h | Min/Max inputs + quick range radios |
| Beds & Baths segmented buttons | 1–2h | Button group with radio behavior |
| "More" overflow panel | 2–3h | Sqft inputs + checkboxes + reset |
| Active state CSS | 1h | Blue border + value text on pills |
| HTMX integration (hidden inputs + Apply) | 1–2h | Wire up Apply buttons to HTMX |
| Backend `parse_filters()` update | 0.5h | Add new param parsing |
| Accessibility (ARIA, focus, keyboard) | 1–2h | Focus trap, aria-expanded, radiogroup |
| Testing & polish | 1–2h | Cross-browser, edge cases |
| **Total** | **~10–17h** | |

### Implementation Order

1. **Phase 1 — Active States** (2h) — Add active pill styling to existing `<select>` elements. Immediate visual win, no structural changes.
2. **Phase 2 — Dropdown Infrastructure** (3h) — Build the reusable dropdown panel component (open/close, focus trap, Apply pattern). Test with Price filter.
3. **Phase 3 — Price Dropdown** (2h) — Replace Price `<select>` with custom panel (Min/Max inputs + quick ranges).
4. **Phase 4 — Beds & Baths Combined** (2h) — Replace separate Beds/Baths `<select>` with combined dropdown + segmented buttons.
5. **Phase 5 — More Dropdown** (3h) — Add "More" pill with sqft + feature checkboxes + reset all.
6. **Phase 6 — Polish** (2h) — Transitions, mobile responsiveness, edge cases, accessibility audit.

---

## 6. Design Tokens

### Existing Tokens (Reuse)

| Token | Value | Usage in Filter Bar |
|-------|-------|-------------------|
| `--accent-blue` | `#2563eb` | Active pill border, Apply button bg, selected segment |
| `--bg-secondary` | `#f8f9fa` | Filter bar background |
| `--text-primary` | `#1a202c` | Pill text, input text |
| `--text-secondary` | `#4a5568` | Placeholder text |
| `--text-muted` | `#718096` | Helper text, sqft conversion |
| `--border-card` | `#e2e8f0` | Panel border, dividers |
| `--border-card-hover` | `rgba(59,130,246,0.4)` | Pill hover border |
| `--shadow-card` | `0 1px 3px rgba(0,0,0,0.08)` | Panel shadow |
| `--radius-pill` | `16px` | Pill border radius |

### New Tokens Needed

| Token | Value | Usage |
|-------|-------|-------|
| `--filter-panel-bg` | `#ffffff` | Dropdown panel background |
| `--filter-panel-shadow` | `0 4px 16px rgba(0,0,0,0.12)` | Dropdown panel shadow (deeper than card) |
| `--filter-panel-radius` | `12px` | Dropdown panel border radius |
| `--filter-panel-width` | `320px` | Default panel width (Price, Beds & Baths) |
| `--filter-panel-width-wide` | `400px` | Wide panel width (More) |
| `--filter-active-bg` | `#f0f4ff` | Active pill background tint |
| `--filter-active-border` | `#2563eb` | Active pill border (same as `--accent-blue`) |
| `--filter-segment-selected-bg` | `#2563eb` | Selected segment button background |
| `--filter-segment-selected-text` | `#ffffff` | Selected segment button text |
| `--filter-divider` | `#e2e8f0` | Horizontal divider inside panels |

---

## 7. ASCII Mockup

### Default State (No Filters Active)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ 🏠 SunnyNest   [💰 Price ▾] [🛏️ Beds & Baths ▾] [📡 Source ▾] [⚙️ More ▾]  │  [🕐 Newest ▾]  Admin → │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Active State (Filters Applied)

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│ 🏠 SunnyNest   [╔$5K–$6.5K▾╗] [╔3+ bd, 2+ ba▾╗] [📡 Source ▾] [╔⚙️ More (1)▾╗]  │  [💲 Price ↑ ▾]  Admin → │
└──────────────────────────────────────────────────────────────────────────────────────┘
                   ╚═══blue═══╝   ╚════blue═════╝                  ╚════blue════╝
```

*`╔═╗` represents blue border on active pills*

### Price Dropdown Open

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ 🏠 SunnyNest   [╔$5K–$6.5K▾╗] [🛏️ Beds & Baths ▾] [📡 Source ▾] [⚙️ More ▾] │
└────────────────────┼───────────────────────────────────────────────────────────┘
                     │
                     ▼
              ┌─────────────────────────────┐
              │  Price Range                │
              │                             │
              │  Min ($)        Max ($)     │
              │  ┌──────────┐ ┌──────────┐ │
              │  │ 5,000    │ │ 6,500    │ │
              │  └──────────┘ └──────────┘ │
              │                             │
              │  Quick ranges:              │
              │  ○ Under $4,000             │
              │  ○ $4,000 – $5,000          │
              │  ● $5,000 – $6,500          │
              │  ○ $6,000 – $7,000          │
              │  ○ $7,000 – $8,000          │
              │  ○ $8,000+                  │
              │                             │
              │  ┌───────────────────────┐  │
              │  │       Apply           │  │
              │  └───────────────────────┘  │
              └─────────────────────────────┘
```

### Beds & Baths Dropdown Open

```
              ┌───────────────────────────────────┐
              │  Number of Bedrooms               │
              │                                   │
              │  ┌─────┬─────┬─────┬─────┬─────┐ │
              │  │ Any │ 1+  │ 2+  │▐3+ ▌│ 4+  │ │
              │  └─────┴─────┴─────┴─────┴─────┘ │
              │                    (selected=blue) │
              │  Number of Bathrooms              │
              │                                   │
              │  ┌─────┬─────┬─────┬─────┐       │
              │  │ Any │ 1+  │▐2+ ▌│ 3+  │       │
              │  └─────┴─────┴─────┴─────┘       │
              │                                   │
              │  ┌─────────────────────────────┐  │
              │  │           Apply             │  │
              │  └─────────────────────────────┘  │
              └───────────────────────────────────┘
```

### "More" Dropdown Open

```
              ┌───────────────────────────────────────┐
              │  Additional Filters                   │
              │                                       │
              │  Square Feet                          │
              │  ┌──────────┐  ┌──────────┐          │
              │  │ Min sqft │  │ Max sqft │          │
              │  │ No Min   │  │ No Max   │          │
              │  └──────────┘  └──────────┘          │
              │  (Shows: "800–1,500 sqft (74–139 m²)")│
              │                                       │
              │  ─────────────────────────────────    │
              │                                       │
              │  Features                             │
              │  ☑ Pet Friendly                       │
              │  ☐ Air Conditioning                   │
              │  ☐ Furnished                          │
              │                                       │
              │  ─────────────────────────────────    │
              │                                       │
              │  ⟲ Reset all filters                 │
              │                                       │
              │  ┌─────────────────────────────────┐  │
              │  │            Apply                │  │
              │  └─────────────────────────────────┘  │
              └───────────────────────────────────────┘
```

### Full Filter Bar Layout (Responsive)

```
Desktop (>1024px):
┌─────────────────────────────────────────────────────────────────────────────┐
│ 🏠 SunnyNest  [Price ▾] [Beds & Baths ▾] [Source ▾] [More ▾]  │  [Sort ▾]  Admin → │
└─────────────────────────────────────────────────────────────────────────────┘

Tablet (768–1024px):
┌─────────────────────────────────────────────────────────────┐
│ 🏠  [Price ▾] [Beds & Baths ▾] [Source ▾] [More ▾] [Sort ▾] │
└─────────────────────────────────────────────────────────────┘
(Logo text hidden, Admin link hidden — accessible via /admin/ URL)

Mobile (<768px):
┌─────────────────────────────────┐
│ 🏠 SunnyNest    [Filters (3) ▾] │
└─────────────────────────────────┘
(Single "Filters" button opens full-screen filter panel)
(Per skill-filter-search-ux.md mobile pattern)
```

---

## 8. Open Questions

| # | Question | Options | Recommendation |
|---|----------|---------|----------------|
| 1 | **Should Source filter become a segmented button group** (like Beds) instead of a `<select>`? | A) Keep as `<select>` B) Segmented buttons (All / Zillow / Craigslist) | **A** — only 3 options, `<select>` is fine. Revisit if we add more sources. |
| 2 | **Should we add a "Favorites Only" toggle** to the filter bar? | A) Yes, as a pill toggle B) No, keep it separate C) Add to "More" panel | **C** — add as a checkbox in the "More" panel. Not common enough for a top-level pill. |
| 3 | **Should the Apply button be blue (filled) or outlined?** | A) Filled blue (`#2563eb` bg, white text) B) Outlined (white bg, blue border) | **A** — filled blue, matching Zillow's pattern. Clear call-to-action. |
| 4 | **Should we show a "No results" inline hint** when filters are too restrictive? | A) Yes, show hint in filter bar area B) No, rely on empty state in listing panel | **B** — the existing empty state in the listing panel is sufficient. Adding a hint in the filter bar would add complexity. |
| 5 | **Price quick ranges — keep current 7 ranges or simplify?** | A) Keep all 7 B) Reduce to 5 (Under $4K, $4K–$5K, $5K–$6.5K, $6.5K–$8K, $8K+) | **B** — 5 ranges is cleaner. Users who need precision can use Min/Max inputs. |

---

## Appendix: Component CSS Sketch

```css
/* === Dropdown Panel (shared) === */
.filter-dropdown {
    position: relative;
    display: inline-block;
}

.filter-pill {
    appearance: none;
    background: #ffffff;
    border: 1px solid #d1d5db;
    border-radius: var(--radius-pill);
    font-family: var(--font-family);
    font-size: 13px;
    font-weight: 500;
    padding: 6px 28px 6px 12px;
    cursor: pointer;
    transition: border-color 0.2s, background 0.2s;
    white-space: nowrap;
    /* Dropdown arrow */
    background-image: url("data:image/svg+xml,...");
    background-repeat: no-repeat;
    background-position: right 10px center;
}

.filter-pill:hover {
    border-color: var(--border-card-hover);
    background-color: #f0f4ff;
}

.filter-pill[aria-expanded="true"],
.filter-pill.is-active {
    border-color: var(--filter-active-border);
    background-color: var(--filter-active-bg);
}

.filter-panel {
    position: absolute;
    top: calc(100% + 8px);
    left: 0;
    width: var(--filter-panel-width);
    background: var(--filter-panel-bg);
    border: 1px solid var(--border-card);
    border-radius: var(--filter-panel-radius);
    box-shadow: var(--filter-panel-shadow);
    padding: 16px;
    z-index: 1001;
    display: none; /* JS toggles to block */
}

.filter-panel.is-open {
    display: block;
}

/* === Segmented Button Group === */
.segment-group {
    display: flex;
    border: 1px solid #d1d5db;
    border-radius: 8px;
    overflow: hidden;
}

.segment-btn {
    flex: 1;
    padding: 8px 12px;
    border: none;
    border-right: 1px solid #d1d5db;
    background: #ffffff;
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    min-width: 48px;
    min-height: 36px;
    transition: background 0.15s, color 0.15s;
}

.segment-btn:last-child {
    border-right: none;
}

.segment-btn[aria-checked="true"] {
    background: var(--filter-segment-selected-bg);
    color: var(--filter-segment-selected-text);
    font-weight: 600;
}

.segment-btn:hover:not([aria-checked="true"]) {
    background: #f0f4ff;
}

/* === Apply Button === */
.filter-apply-btn {
    display: block;
    width: 100%;
    padding: 10px;
    background: var(--accent-blue);
    color: #ffffff;
    border: none;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    margin-top: 12px;
    transition: background 0.15s;
}

.filter-apply-btn:hover {
    background: #1d4ed8;
}

.filter-apply-btn:focus-visible {
    outline: 2px solid var(--accent-blue);
    outline-offset: 2px;
}
```

---

*This document is a design plan for review. No code changes should be made until the product owner approves the approach.*
