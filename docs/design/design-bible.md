# SunnyNest Design Bible

> **Purpose**: Single source of truth for all UI/UX design decisions.
> The UX Designer agent MUST read this file before every task and update it after each task if new decisions are made.
>
> **Last updated**: 2026-03-30

### Mockup Versioning Rule (MANDATORY)
> **Every design change MUST create a new versioned file** — never overwrite an existing mockup.
> - Naming: `sunnynest-v1.html`, `sunnynest-v2.html`, `sunnynest-v3.html`, etc.
> - Keep all previous versions so the owner can compare and fall back if a change wasn't good.
> - Reference the version number in the changelog entry.
> - Only delete old versions when the owner explicitly approves.

---

## 1. User Preferences (Owner Notes)

These are explicit instructions from the product owner. They override any conflicting design pattern.

### Units & Measurements
- **Area/Size**: Always display BOTH sqft AND square meters — e.g., "1,200 sqft (111 m²)"
- Conversion: 1 sqft = 0.0929 m². Round m² to nearest whole number.
- This applies to: listing cards, detail views, filters, map popups, export data, comparison tables

### Locale & Formatting
- **Currency**: USD with comma separators — e.g., "$5,200/mo"
- **Dates**: YYYY-MM-DD format in data, "Mar 27, 2026" in UI display
- **Numbers**: Use comma separators for thousands — e.g., "1,200 sqft"

### Content Rules
- Never use Lorem ipsum — always use realistic rental listing data
- Use Sunnyvale, CA addresses and realistic Bay Area rental prices ($2,000–$8,000/mo range)
- Include realistic property photos or placeholder images that look like real properties

---

## 2. Design Tokens

### Colors — Light Theme (Production — FastAPI Dashboard)

> **Note**: The production FastAPI dashboard uses a light theme as of 2026-03-30. These tokens document the actual running UI.

| Token | Value | Usage |
|-------|-------|-------|
| `--bg-primary` | `#ffffff` | Page background |
| `--bg-secondary` | `#f8f9fa` | Filter bar, secondary surfaces |
| `--bg-card` | `#ffffff` | Card backgrounds |
| `--bg-card-hover` | `#f0f4ff` | Card hover state |
| `--border-card` | `#e2e8f0` | Card borders, dividers |
| `--border-card-hover` | `rgba(59, 130, 246, 0.4)` | Card hover border (blue glow) |
| `--text-primary` | `#1a202c` | Headings, titles, body text |
| `--text-secondary` | `#4a5568` | Specs, secondary text |
| `--text-muted` | `#718096` | Labels, metadata, location |
| `--accent-blue` | `#2563eb` | Primary actions, links, prices |
| `--accent-blue-light` | `#3b82f6` | Hover accents |
| `--shadow-card` | `0 1px 3px rgba(0,0,0,0.08)` | Card shadow |
| `--shadow-card-hover` | `0 4px 12px rgba(59,130,246,0.12)` | Card hover shadow (blue) |
| `--color-success` | `#16a34a` | New listings, positive metrics |
| `--color-warning` | `#d97706` | Price drops, aging listings |
| `--color-danger` | `#dc2626` | Price increases, above-average price |

### Colors — Dark Theme (Legacy — Streamlit App, Deprecated)

> **Note**: The Streamlit app has been replaced by the FastAPI dashboard. These tokens are kept for reference only.

| Token | Value | Usage |
|-------|-------|-------|
| `--color-bg` | `#0e1117` | Page background (Streamlit dark) |
| `--color-surface` | `rgba(255,255,255,0.025)` | Card backgrounds |
| `--color-text-primary` | `#ffffff` | Headings, titles |
| `--color-text-secondary` | `#cccccc` | Specs text |
| `--color-border` | `rgba(255,255,255,0.10)` | Card borders |

#### Light Theme Badge Variants
| Class | Background | Border | Text Color | Usage |
|-------|-----------|--------|------------|-------|
| `.tag-new` | `rgba(34,197,94,0.08)` | `rgba(34,197,94,0.3)` | `#16a34a` | New listing |
| `.tag-fresh` | `rgba(67,160,71,0.08)` | `rgba(67,160,71,0.3)` | `#2e7d32` | Recently listed (≤3 days) |
| `.tag-aging` | `rgba(249,168,37,0.08)` | `rgba(249,168,37,0.3)` | `#f57f17` | Aging listing (4–14 days) |
| `.tag-stale` | `rgba(198,40,40,0.08)` | `rgba(198,40,40,0.3)` | `#c62828` | Stale listing (>14 days) |
| `.tag-pet` | `rgba(25,118,210,0.08)` | `rgba(25,118,210,0.3)` | `#1565c0` | Pet friendly |
| `.tag-ac` | `rgba(2,136,209,0.08)` | `rgba(2,136,209,0.3)` | `#0277bd` | Air conditioning |
| `.tag-price-drop` | `rgba(217,119,6,0.08)` | `rgba(217,119,6,0.3)` | `#b45309` | Price decrease |
| `.tag-price-up` | `rgba(220,38,38,0.08)` | `rgba(220,38,38,0.3)` | `#dc2626` | Price increase |

### Typography

| Level | Size | Weight | Usage |
|-------|------|--------|-------|
| Price | 20px | 800 | Card price (dominant scanning element) |
| Heading | 18px | 700 | Section titles |
| Body | 14px | 400–500 | Specs, address, descriptions |
| Small | 13px | 500 | Filter pills, badges |
| Micro | 12px | 500–600 | Metric labels, sync info |
| Tiny | 11px | 600 | Tag badges |

- **Font family**: Inter (fallback: system-ui, -apple-system, sans-serif)
- **Spacing base**: 8px grid

### Border Radius

| Component | Radius |
|-----------|--------|
| Cards | 12px |
| Buttons | 8px |
| Filter pills | 16px (full round) |
| Badges/tags | 10px |
| Inputs | 6px |

---

## 3. Layout Principles

### Split-Panel Layout (Primary)
- **Left panel**: Listing cards (440px width on desktop, scrollable)
- **Right panel**: Interactive map (fills remaining width, sticky)
- **Breakpoints**:
  - `> 1024px`: Full split-panel (440px listings + flexible map)
  - `768–1024px`: Narrower listings panel (360px)
  - `< 768px`: Stacked layout (listings top, map bottom)

### Card Design
- **Layout**: Horizontal — thumbnail image (left) + text content (right), NOT vertical/stacked
- **Visibility**: 3–4 cards must be visible at once in the scrollable left panel (card height ~140–160px max)
- **Scrolling**: Left panel scrolls independently; user scrolls to see more cards below the visible 3–4
- Cards use surface color on page background for clear visual separation
- **Hover**: Subtle lift (-2px translateY) + shadow increase + border glow
- **Selected**: Brand-color border + shadow

#### Required Card Content (all must be visible — never omit)
Each listing card MUST display ALL of the following:
1. **Thumbnail image** — left side, ~140–160px square, with lazy loading
2. **Price** — dominant element (20px / 800 weight), e.g. "$5,500/mo"
3. **Address** — full street address, truncated with ellipsis if needed
4. **Size** — BOTH sqft AND m², e.g. "1,683 sqft (156 m²)"
5. **Beds & Baths** — e.g. "4 bed · 2 bath"
6. **Source link + logo** — Zillow/Craigslist favicon + name, links to original listing
7. **Favorite/heart button** — toggle to mark favorites (☆/★ or ♡/♥)
8. **Days since published** — e.g. "1d ago", "4d ago", "3w ago"

#### Card Content Priority (visual hierarchy, left-to-right then top-to-bottom)
- Image column: thumbnail + favorite overlay button
- Text column:
  1. Price + Address (same row or stacked)
  2. Specs: beds · baths · sqft (m²)
  3. Badges: New, price change, days ago (max 3)
  4. Source pill link (Zillow/Craigslist with favicon)
  5. Location/school district (if space allows)

### Filter Bar
- Pill-style filter buttons with clear labels and emoji icons
- Active state: blue background tint
- Result count badge inline with filters
- Sort dropdown at end of filter bar

---

## 4. Component Patterns

### Property Cards
- **IMPORTANT**: Horizontal layout (image left + text right) — NOT vertical/stacked
- Image column (~140–160px): thumbnail with heart/favorite overlay button
- Text column contains ALL of:
  - Price (20px/800, dominant) + Address (truncated)
  - Specs: `4 bed · 2 bath · 1,683 sqft (156 m²)`
  - Badges row: status tags (max 3) + source link pill
  - Source link: Zillow/Craigslist favicon + name, opens original listing
  - Days since published (as badge or text)
  - School district / location (if space allows)
- Specs row format: `3 bd | 2 ba | 1,200 sqft (111 m²)`
- Price per sqft in metrics: show both `$/sqft` and `$/m²`
- **Card height constraint**: ~140–160px so 3–4 cards are visible simultaneously

### Map

#### Tile Layers
- **Light theme (active)**: OpenStreetMap Standard (fallback: Stadia Outdoors)
- **Dark theme (legacy)**: Stadia Alidade Smooth Dark (fallback: CartoDB Dark Matter)
- Tiles MUST show: parks (green areas), water (blue), street names, transit stations
- Satellite toggle available via layer control
- **Anti-pattern**: Never use CartoDB Positron or other minimal tiles that hide parks/POIs

#### Price Pill Markers
- Background: `#ffffff` (white) — light, clean style on light-theme map
- Text: `#1a202c` (dark), 12px, 700 weight, Inter font
- Border: `1.5px solid rgba(59, 130, 246, 0.4)` (blue tint)
- Border radius: 12px
- Shadow: `0 2px 6px rgba(0, 0, 0, 0.15)`
- Hover state: `#2563eb` bg, white text, blue border, `scale(1.1)`
- Highlighted state (card↔map sync): `#2563eb` bg, white text, `scale(1.15)`
- Selected state (planned): `#1d4ed8` bg, white text, `scale(1.1)`, z-index boost
- Marker clustering when zoomed out with unit count badges (planned — `Leaflet.markercluster`)
- Implementation: `L.divIcon` with `.price-pill` CSS class — see [`map.js:74-79`](web/static/js/map.js:74), [`style.css:571-609`](web/static/css/style.css:571)

#### POI Markers (Custom Interest Points)
- Shape: 24×24px circle with 2px white border
- Icon: emoji centered in circle
- Shadow: `0 2px 4px rgba(0,0,0,0.3)`
- Label: tooltip on hover (never always-visible — keeps map clean)
- Must be visually distinct from price pills (circles, not pills)
- Categories and colors:

| Category | Color | Icon | Token |
|----------|-------|------|-------|
| Work | `#6366f1` | 🏢 | `--color-poi-work` |
| School | `#f59e0b` | 🏫 | `--color-poi-school` |
| Park | `#16a34a` | 🌳 | `--color-poi-park` |
| Transit | `#8b5cf6` | 🚉 | `--color-poi-transit` |
| Shopping | `#ec4899` | 🛒 | `--color-poi-shopping` |
| Custom | `#64748b` | 📍 | `--color-poi-custom` |

#### Layer Control
- Position: top-right corner of map
- Toggle for each layer with item count — e.g., "🏫 Schools (3)"
- Default ON: Listings, City Boundary, user-added POI categories
- Default OFF: empty POI categories, satellite view

#### Map Popups
- Background: white (`#ffffff`), border-radius: 8px, padding: 12px
- Title: dark (`#111111`), bold
- Price: brand blue (`#2563eb`), 1.1em, bold
- Specs: gray (`#555555`)
- Source links: brand blue with ↗ arrow
- Min width: 200px, max width: 300px

#### Floating Result Count
- Badge on map showing total visible listings

### Tags/Badges
- Semantic colors: green=new, amber=price drop, blue=pet friendly
- Max 3 visible badges per card (priority: price change > new > availability)
- Use both color AND text labels (never color alone — accessibility)
- Informational badges (days, AC) use outlined style, not solid

### Empty States
- Never show a blank screen
- Show illustration + actionable guidance ("No rentals match your filters. Try adjusting...")
- Include a "Reset Filters" button

### Loading States
- Skeleton card placeholders with shimmer animation
- Never just a spinner

---

## 5. Accessibility Requirements (Non-Negotiable)

- **WCAG AA** compliance on all designs (minimum)
- **Contrast**: 4.5:1 for normal text, 3:1 for large text
- **Semantic HTML**: Use proper heading hierarchy, landmarks, lists
- **Focus states**: Visible outline on all interactive elements
- **Keyboard navigation**: All interactive elements reachable via Tab
- **ARIA**: `aria-label` on icon-only buttons, `aria-pressed` on toggles, `aria-live="polite"` on dynamic content (result counts, filter changes)
- **Touch targets**: Minimum 44×44px on mobile
- **Color independence**: Never convey information through color alone — always pair with text, icons, or symbols (e.g., ↑/↓ for price changes)
- **Motion**: Respect `prefers-reduced-motion` media query

---

## 6. States Checklist

Every mockup MUST include these states:

- [ ] **Default** — Normal appearance
- [ ] **Hover** — Visual feedback on interactive elements
- [ ] **Selected/Active** — Currently selected item
- [ ] **Focus** — Keyboard navigation indicator
- [ ] **Loading** — Skeleton/shimmer placeholder
- [ ] **Empty** — No results, with guidance
- [ ] **Error** — Failed to load, with retry
- [ ] **Disabled** — Non-interactive state
- [ ] **Favorited** — Filled heart vs. outline
- [ ] **Reduced motion** — Respects user preference

---

## 7. Anti-Patterns (Never Do This)

- ❌ Generic purple gradients on white backgrounds ("AI slop")
- ❌ Cookie-cutter layouts without context-specific character
- ❌ Lorem ipsum or placeholder text
- ❌ Color-only information encoding
- ❌ Tiny touch targets (< 44px)
- ❌ Showing only sqft without m² equivalent
- ❌ Blank screens when data fails to load
- ❌ More than 3 badge/tags per card
- ❌ Flat cards with no depth or hover feedback
- ❌ Mismatched map tiles and UI theme (e.g., dark tiles in light UI or vice versa)
- ❌ Minimal/empty map tiles (e.g., CartoDB Positron) that hide parks, transit, and POIs — use rich tiles that show environmental context
- ❌ POI markers that look like price pills — POIs must be visually distinct (circles with icons, not pills)
- ❌ Reusing listing blue (`#3b82f6`) for POI markers — each POI category has its own designated color
- ❌ Vertical/stacked card layout (image on top, text below) — makes cards too tall, only 1-2 visible
- ❌ Cards showing only images without text content (price, address, specs, source link, days)
- ❌ Fewer than 3 cards visible in the scroll area at once
- ❌ Using `position: absolute` on card images — breaks layout flow, causes squished/misaligned content
- ❌ Using `align-items: stretch` + `align-self: stretch` on card thumbnails — makes images stretch unpredictably
- ❌ Iterative CSS "fixes" that change multiple layout properties at once — always revert to last working state first

### Card Image/Text Alignment Rules (Lessons Learned)
> **IMPORTANT**: These rules prevent recurring alignment bugs in horizontal card layouts.

1. **Use fixed dimensions for thumbnails** — e.g., `width: 140px; height: 130px;` — never auto-height
2. **Never use `position: absolute` on card images** — it removes them from flow and breaks the card layout
3. **Use `object-fit: cover`** on `<img>` tags — ensures proper aspect ratio without distortion
4. **Set `overflow: hidden`** on both the card AND the thumbnail container — clips any overflow cleanly
5. **Keep card padding consistent** — `padding: 10px` on all sides; thumbnail height + padding must not exceed card height
6. **Use `flex-shrink: 0`** on the thumbnail — prevents it from being compressed by text content
7. **Test with real images** — placeholder divs behave differently than actual `<img>` tags with varying aspect ratios
8. **When fixing alignment bugs**: revert to the last known working state, then make ONE small change at a time

---

## 8. Reference Designs

- **Zillow**: Property cards, search bar, filter pills, heart overlay, carousel dots
- **Mashvisor Property Finder**: Split-panel layout, inline metrics, map clustering, compact cards

---

## 9. Changelog

| Date | Change | By |
|------|--------|----|
| 2026-03-27 | Initial Design Bible created | Orchestrator |
| 2026-03-27 | Added dark theme tokens documenting production Streamlit app colors (purple accent, outlined badge variants) | UX Designer |
| 2026-03-27 | Created `sunnynest-dashboard.html` mockup — faithful reproduction of running app with all states | UX Designer |
| 2026-03-27 | Created `sunnynest-modern-saas.html` — modern SaaS redesign with blue accent, vertical cards, styled filter pills, improved typography (20px/800 price), metrics row, result summary bar | UX Designer |
| 2026-03-27 | **OWNER FEEDBACK**: Vertical cards rejected — too tall, only 1-2 visible. Updated Card Design rules: horizontal layout mandatory, 3-4 cards visible, all required content (price, address, size, source link, favorite btn, days) must be shown | UX Designer |
| 2026-03-27 | **LESSON LEARNED**: Added Card Image/Text Alignment Rules — never use `position: absolute` on card images, always use fixed thumbnail dimensions, avoid `align-items: stretch` on cards. Revert to last working state before fixing bugs. | UX Designer |
| 2026-03-28 | Created `backoffice.html` mockup — Streamlit-style admin dashboard with 5 pages (Dashboard KPIs, Listing Analytics, API Usage, Notifications, Settings). Dark theme, blue accent (#2563eb/#3b82f6), sidebar navigation, SVG charts (donut, bar, line, histogram, gauge), data tables, toggle switches, form inputs. WCAG AA compliant with semantic HTML, ARIA labels, focus states, keyboard navigation. | UX Designer |
| 2026-03-29 | **Map improvement consultation** (`plans/map-improvement.md`). Expanded Map section: tile layer recommendations (Stadia Outdoors > OSM > Mapbox), POI marker design system (6 categories with unique colors/icons), layer control UX, marker selected/hover states, popup styling. Added POI color tokens (`--color-poi-*`), updated `--color-map-marker` from purple to blue. Added 3 new anti-patterns for map tiles and POI markers. 5-phase implementation plan. | UX Designer |
| 2026-03-29 | **Frontend migration UX review** (`plans/frontend-migration-ux-review.md`). Reviewed FastAPI + HTMX migration plan across 6 dimensions: layout/responsiveness, interaction patterns, design bible compliance, UX improvements, CSS framework decision, WCAG AA accessibility. Key findings: use `sunnynest-v4.html` (not `user-dashboard.html`) as template, move responsive breakpoints and map-card sync to Phase 1, add accessibility foundation (aria-live, focus management, 44px touch targets), custom CSS over frameworks, toast pattern for SSE notifications. 15 prioritized recommendations (5 P0, 5 P1, 5 P2). | UX Designer |
| 2026-03-30 | **Phase 1 UX spec** (`plans/phase1-ux-spec.md`). Comprehensive visual audit of Phase 0 FastAPI dashboard against design bible. Scored Phase 0 across 7 dimensions (layout 7/10, cards 8/10, filters 8/10, map 4/10, interactions 3/10, accessibility 5/10, states 4/10). Identified 21 missing design elements. Created priority-ordered fix list: 3 P0 (panel width, dark tiles, price pills), 12 P1 (boundary, image fallback, favorites, card-map sync, skeleton, popups, OOB count, reset btn, focus states, semantics, error state, clustering), 6 P2 (dislike, active filters, URL state, animations, responsive, reduced-motion). Copy-paste-ready CSS/JS for all fixes. 5-sprint implementation plan (~7h total). | UX Designer |
| 2026-03-30 | **Switched entire dashboard to LIGHT MODE**. Updated all CSS custom properties from dark (`#0f1117` bg, white text, `rgba(255,255,255,*)` borders) to light (`#ffffff` bg, `#1a202c` text, `#e2e8f0` borders). New token naming: `--bg-primary`, `--bg-secondary`, `--bg-card`, `--border-card`, `--text-primary`, `--text-secondary`, `--text-muted`, `--accent-blue`, `--shadow-card`. Badge variants changed from outlined-on-dark to tinted-on-light (e.g., `.tag-fresh`: `rgba(67,160,71,0.08)` bg + `#2e7d32` text). Source pills, price pills, filter selects, scrollbars, Leaflet controls all updated for light backgrounds. Added `?v=2` cache-busting to CSS and JS includes. Design bible color tokens section updated. | Code |
| 2026-03-30 | **Map improvement plan updated for Leaflet.js stack** (`plans/map-improvement.md`). Revised entire plan for FastAPI + HTMX + Leaflet.js (was Streamlit + Folium). Added Migration Status section: 11 items completed during migration (OSM tiles, price pills, boundary, card↔map sync, hover/highlighted states, HTMX refresh, Leaflet control styling), 10 items remaining. Updated all file references from `app.py` to `web/` paths. Removed Streamlit constraints (iframe, `st_folium` sync, no custom JS). Added §10 New Opportunities (clustering, search-as-I-move, draw boundary, geolocation, fullscreen). Reduced effort estimates ~30-40% (13-24h → 10-15h remaining). Corrected Price Pill Markers tokens to match actual light-theme implementation (white bg + blue border, not blue bg + white text). | UX Designer |
| 2026-04-06 | **Admin API Usage page redesign mockup** (`docs/temp/mockups/api-usage-redesign-v1.html`). Complete redesign of `/admin/api-usage` page. Removed verbose 25-row tables and static API Configuration sections. New components: (1) **Source quota cards** with CSS-only conic-gradient donut charts showing used/remaining budget (Zillow 45/500, Realtor 12/150), (2) **Operational status** with last-call badge (✓ OK / ✗ Failed) and last-10-calls dot visualization with hover tooltips, (3) **7-day success rate trend** vertical bar chart (green=100%, amber=<100%), (4) **Monthly comparison** horizontal bars (this month vs last month with delta badges), (5) **Daily call volume sparklines** per source. All CSS-only (no JS charting libraries). Uses `--admin-*` design tokens from light theme. WCAG AA: semantic HTML, ARIA labels on all charts, `role="list"` on dot sequences, `prefers-reduced-motion`, focus-visible states, color+text pairing on all status indicators. Responsive at 1024px and 768px breakpoints. | UX Designer |

---

*This file is a living document. The UX Designer agent should update it whenever new design decisions are made during a session.*
