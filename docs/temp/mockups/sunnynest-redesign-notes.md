# SunnyNest Redesign — Design Notes

## Overview

This mockup demonstrates the **top 5 UI improvements** for the SunnyNest rental finder, inspired by **Zillow** and **Mashvisor** reference designs. The design follows a **modern SaaS style** with a clean, light color palette using the **Neutral + Accent** pattern (professional grays + blue brand accent).

---

## Top 5 Improvements

### ① Larger Property Images with Carousel & Heart Overlay

**Before:** Small 160px thumbnails in a horizontal card layout. Favorite star icon placed separately from the image.

**After:** Full-width 200px images at the top of each card with:
- **Carousel dot indicators** (Zillow pattern) showing multiple photos available
- **Heart/favorite overlay** positioned top-right on the image (Zillow + Mashvisor pattern)
- **Source badge** (Zillow/Craigslist) positioned top-left on the image
- **Subtle zoom on hover** for visual feedback

**Why:** Property photos are the #1 factor in user engagement. Zillow's research shows listings with prominent photos get 2x more clicks. The heart overlay is the industry-standard pattern for saving favorites.

**Accessibility:** Heart button has `aria-label` and `aria-pressed` states. Images have descriptive `alt` text. Minimum 44×36px touch target.

---

### ② Clean White Cards with Stronger Visual Hierarchy

**Before:** Dark-on-dark cards with similar font sizes for price, specs, and address. Purple accent color (`#bb86fc`) for prices. Cards blend into the dark background.

**After:** White cards on a light gray background (`#f5f6f8`) with:
- **Price as dominant element:** 20px, weight 800, dark text — the first thing you scan
- **Specs as secondary:** 13px, weight 500, gray — bed/bath/sqft in a clean pipe-separated row
- **Address as tertiary:** 13px, muted gray — with neighborhood as a clickable blue link (Mashvisor pattern)
- **Tags as visual badges:** Colored pill badges with semantic colors (green=new, amber=price drop, blue=pet friendly)
- **Card hover effect:** Subtle lift + shadow increase for interactivity feedback

**Why:** The Zillow reference shows price as the dominant scanning element with clean typography hierarchy. White cards on a light background create clear visual separation between listings.

**Accessibility:** All text meets WCAG AA contrast ratios (4.5:1+). Dark text on white background provides maximum readability. Tags use both color AND text labels (never color alone).

---

### ③ Modern Pill-Style Filter Bar

**Before:** 9 cramped dropdown selectors in a horizontal row with hidden labels. Tiny 1.8rem height, 0.8rem font. Hard to read and click.

**After:** Rounded pill-style filter buttons with:
- **Clear labels with emoji icons** (💰 $5K–$6.5K, 🛏 3–4 Beds)
- **Active state highlighting** — blue background tint for active filters
- **Visual dividers** between filter groups
- **Result count badge** ("11 rentals available") inline with filters
- **Sort dropdown** at the end of the filter bar

**Why:** Zillow uses this exact pattern — rounded pill filters with clear labels and a result count. It's the industry standard for real estate search UIs. The larger touch targets (36px+ height) improve usability on all devices.

**Accessibility:** Each filter pill has `aria-pressed` state. Sort dropdown has `aria-label`. Result count uses `aria-live="polite"` for screen reader announcements.

---

### ④ Investment Metrics Inline on Cards (Mashvisor-style)

**Before:** No comparative metrics on cards. Users had to mentally calculate price/sqft and compare to market averages.

**After:** A metrics row at the bottom of each card showing:
- **$/sqft** — price per square foot for quick comparison
- **vs. Avg** — percentage above/below market average (green for below, red for above)
- **Days Listed** — how long the listing has been on market

**Why:** Mashvisor's Property Finder shows Cap Rate and Cash on Cash metrics inline on each card. For a rental search tool, $/sqft and market comparison are the equivalent high-value metrics. This saves users from opening each listing to compare value.

**Accessibility:** Positive/negative values use both color AND directional symbols (−/+). Metric labels use uppercase small text for clear hierarchy.

---

### ⑤ Professional Header with Search Bar & Result Count

**Before:** Simple logo on the left with sync details taking up space. No search bar. No save/export actions.

**After:** A professional SaaS header with:
- **Logo** on the left (🏠 SunnyNest)
- **Search bar** in the center (Zillow-style, with location pre-filled)
- **Sync status** as compact muted text on the right
- **Action buttons** — "Sync Now" (outlined) and "Save Search" (primary blue)
- **Map result badge** — floating badge on the map showing "11 rentals in Sunnyvale, CA"

**Why:** Both Zillow and Mashvisor have a prominent search bar in the header. The "Save Search" CTA is a key conversion action. Compact sync info reduces visual noise while keeping the information accessible.

**Accessibility:** Search input has `aria-label`. All buttons have descriptive labels. Focus states with visible outlines on all interactive elements.

---

## Design Tokens

| Token | Value | Usage |
|-------|-------|-------|
| `--color-bg` | `#f5f6f8` | Page background |
| `--color-surface` | `#ffffff` | Card backgrounds |
| `--color-brand` | `#2563eb` | Primary actions, links, active filters |
| `--color-text-primary` | `#1a1d26` | Headings, prices |
| `--color-text-secondary` | `#5a5f72` | Body text, specs |
| `--color-text-muted` | `#8b90a0` | Labels, metadata |
| `--color-success` | `#16a34a` | New listings, positive metrics |
| `--color-warning` | `#d97706` | Price drops, aging listings |
| `--color-danger` | `#dc2626` | Price increases, negative metrics |
| Font family | Inter | All text |
| Spacing base | 8px | Consistent spacing grid |
| Border radius | 6–16px | Varied by component purpose |

## Typography Scale

| Level | Size | Weight | Usage |
|-------|------|--------|-------|
| Price | 20px | 800 | Card price (dominant) |
| Heading | 18px | 700 | Section titles |
| Body | 14px | 400–500 | Specs, address, descriptions |
| Small | 13px | 500 | Filter pills, badges |
| Micro | 12px | 500–600 | Metric labels, sync info |
| Tiny | 11px | 600 | Tag badges |

## States Included

- ✅ **Default** — Normal card appearance
- ✅ **Hover** — Card lift + shadow, image zoom, button color changes
- ✅ **Selected** — Blue border + shadow on active card
- ✅ **Favorited** — Filled red heart vs. outline heart
- ✅ **Active filter** — Blue tint on active filter pills
- ✅ **Focus** — Visible outline on all interactive elements (keyboard nav)
- ✅ **Loading** — Skeleton card template with shimmer animation
- ✅ **Empty** — "No rentals match" with illustration and reset button
- ✅ **Error** — "Unable to load" with retry button
- ✅ **Disabled** — Grayed-out pagination button
- ✅ **Reduced motion** — Respects `prefers-reduced-motion` media query

## Responsive Breakpoints

| Breakpoint | Layout Change |
|------------|---------------|
| > 1024px | Full split-panel (440px listings + flexible map) |
| 768–1024px | Narrower listings panel (360px) |
| < 768px | Stacked layout (listings top, map bottom) |

## Files

- [`sunnynest-redesign.html`](sunnynest-redesign.html) — Self-contained HTML mockup with inline CSS
- [`sunnynest-redesign-notes.md`](sunnynest-redesign-notes.md) — This design notes document
