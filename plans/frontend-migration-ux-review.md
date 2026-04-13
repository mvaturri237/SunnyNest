# UX Review — Frontend Migration Plan (FastAPI + HTMX + Jinja2)

> **Date**: 2026-03-29  
> **Author**: UX Designer Agent  
> **Reviewed Document**: [`plans/frontend-migration.md`](frontend-migration.md)  
> **Design Bible**: [`docs/design/design-bible.md`](../docs/design/design-bible.md)  
> **Existing Mockups**: [`sunnynest-v4.html`](../docs/temp/mockups/sunnynest-v4.html), [`backoffice.html`](../docs/temp/mockups/backoffice.html)

---

## Executive Summary

The migration from Streamlit to FastAPI + HTMX + Jinja2 is **strongly endorsed from a UX perspective**. The current Streamlit architecture is the single biggest blocker to design quality — 530 lines of CSS hacks fighting injected wrapper divs, no mobile responsiveness, no real-time updates, and no animation control. The proposed stack gives us 100% HTML/CSS ownership, which unlocks every UX improvement the design bible envisions but Streamlit prevents.

**Verdict**: ✅ Proceed — with the specific recommendations below incorporated before coding begins.

---

## 1. Layout & Responsiveness

### ✅ Split-Panel Layout — Fully Supported

The split-panel layout (440px listing cards + flexible map) defined in the [design bible §3](../docs/design/design-bible.md) is **perfectly suited** to FastAPI + HTMX. The existing [`sunnynest-v4.html`](../docs/temp/mockups/sunnynest-v4.html) mockup already implements this with clean CSS:

```css
.split { display: flex; height: calc(100vh - 56px); }
.left  { width: 440px; min-width: 380px; max-width: 480px; }
.right { flex: 1; }
```

This CSS transfers directly into Jinja2 templates with zero modification. No Streamlit wrapper divs to fight.

### ⚠️ Responsive Breakpoints — Missing from Migration Plan

The migration plan (Phase 3) mentions "Mobile responsive: CSS media queries" but provides no detail. The design bible defines three breakpoints that **must** be implemented:

| Breakpoint | Layout | Status in Plan |
|-----------|--------|---------------|
| `> 1024px` | Full split-panel (440px + map) | ✅ Implied |
| `768–1024px` | Narrower panel (360px + map) | ❌ Not mentioned |
| `< 768px` | Stacked (listings top, map bottom) | ❌ Not mentioned |

**Recommendation**: Add responsive breakpoint implementation as an explicit task in **Phase 1** (not Phase 3). The split-panel layout is the core UX — it must work at all sizes from day one. Deferring mobile to Phase 3 risks building desktop-only patterns that are expensive to retrofit.

### ⚠️ Sidebar Discrepancy Between Mockups

The [`user-dashboard.html`](../docs/temp/mockups/user-dashboard.html) mockup has a 260px fixed sidebar (generic analytics layout), while [`sunnynest-v4.html`](../docs/temp/mockups/sunnynest-v4.html) has **no sidebar** — just a top filter bar. The migration plan's project structure shows `base.html` as a shared layout, but doesn't clarify which layout pattern to use.

**Recommendation**: The SunnyNest dashboard should use the **no-sidebar, top filter bar** pattern from `sunnynest-v4.html`. Reasons:
1. A sidebar steals 260px from the already-constrained listing panel (440px → 180px usable = unusable)
2. The current Streamlit app has no sidebar (it's architecturally forbidden per [AGENTS.md §4](../AGENTS.md))
3. The filter bar is the primary navigation — it belongs at the top, always visible
4. The backoffice can use a sidebar (it's a different layout with different needs)

### 📐 Specific Layout Recommendations

1. **Filter bar height**: Keep at 56px (current `sunnynest-v4.html` value). The migration plan doesn't specify this.
2. **Map sticky behavior**: The right panel must use `position: sticky` or remain in the viewport as the left panel scrolls. The plan mentions this but doesn't specify the CSS approach — use `overflow: hidden` on `.right` with Leaflet filling 100% height.
3. **Resizable split panel**: Consider adding a drag handle between panels (CSS `resize` or a small JS snippet). This is a UX improvement not possible in Streamlit. Low priority but worth noting in Phase 3.

---

## 2. Interaction Patterns (HTMX)

### ✅ Filter Changes → Partial Page Swap

The proposed pattern is correct and well-suited:

```html
<select hx-get="/listings" hx-target="#listing-cards" hx-include="[name='filter']">
```

**UX Enhancement**: Add `hx-indicator` to show a loading state during the swap. The design bible requires skeleton card placeholders (§4 Loading States), not just a spinner.

```html
<div id="listing-cards" class="scroll">
  <!-- HTMX swaps this content -->
</div>
<template id="loading-skeleton">
  <!-- Skeleton cards shown during load -->
</template>
```

**Recommendation**: Create a `partials/listing-skeleton.html` template that renders 3–4 shimmer skeleton cards. Use HTMX's `hx-indicator` class to show it during filter changes. This is a **Phase 1** task, not Phase 3.

### ✅ Favorite/Dislike Toggles → Inline Swap

The proposed pattern is clean:

```html
<button hx-post="/api/favorite/{{ listing.id }}" 
        hx-swap="outerHTML"
        hx-target="this">♡</button>
```

**UX Enhancements**:

1. **Optimistic UI**: Add `hx-on::before-request` to immediately toggle the heart icon visually, then revert if the server returns an error. This makes the interaction feel instant.
2. **ARIA attributes**: The button must include `aria-pressed="true/false"` and `aria-label="Add to favorites"` / `"Remove from favorites"`. The server response must return the updated ARIA state.
3. **Dislike button**: The plan mentions favorites but not the dislike/hide feature. Add `hx-post="/api/dislike/{{ listing.id }}"` with `hx-swap="outerHTML"` on the card itself — the card should animate out (fade + slide) and be removed from the DOM.

### ✅ Map Marker Clicks → Highlight Card

This requires a small JavaScript bridge between Leaflet events and HTMX/DOM:

```javascript
// map.js — when a marker is clicked
marker.on('click', () => {
  document.querySelector(`[data-listing-id="${id}"]`)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  document.querySelector('.card.selected')?.classList.remove('selected');
  document.querySelector(`[data-listing-id="${id}"]`)?.classList.add('selected');
});
```

**UX Enhancements**:

1. **Bidirectional sync**: Card hover/click should also highlight the corresponding map marker (scale 1.1, z-index boost, darker blue). This is mentioned in Phase 3 but should be **Phase 1** — it's core to the split-panel UX.
2. **Scroll into view**: When a marker is clicked, the corresponding card must scroll into view in the left panel. Use `scrollIntoView({ behavior: 'smooth', block: 'center' })`.
3. **Visual feedback**: Selected card gets `border-color: var(--brand)` + `box-shadow` (already in design bible §3 Card Design).
4. **Data attribute**: Every card must have `data-listing-id="{{ listing.id }}"` for the JS bridge. Every marker must store the listing ID.

### ⚠️ SSE for Real-Time Notifications — Needs UX Specification

The plan proposes SSE at `/stream/listings` for new listing notifications. The UX for this is **not specified**:

**Recommendation — Toast Notification Pattern**:

1. When SSE delivers a new listing, show a **toast notification** at the top of the listing panel:
   ```
   ┌─────────────────────────────────────┐
   │ 🏠 3 new listings found  [View ↑]  │
   └─────────────────────────────────────┘
   ```
2. Clicking "View ↑" scrolls to the top and triggers an HTMX refresh of the listing cards.
3. The toast uses `aria-live="polite"` for screen reader announcement.
4. New listings should NOT auto-insert into the list (this causes layout shift while the user is reading). Instead, batch them and show the toast.
5. The toast auto-dismisses after 10 seconds but remains accessible via a "New listings available" indicator in the filter bar.

**HTMX SSE integration**:
```html
<div hx-ext="sse" sse-connect="/stream/listings" sse-swap="new-listing">
  <!-- Toast appears here -->
</div>
```

This requires the `htmx-ext-sse` extension (~2KB).

### 🆕 URL-Based Filter State — Critical UX Win

The plan mentions "URL-based filters" in Phase 3. This should be **Phase 1**. Reasons:

1. **Bookmarkable searches**: Users can save filter combinations as browser bookmarks
2. **Browser back/forward**: Filter changes push to history, so back button undoes the last filter change
3. **Shareable**: Copy URL to share a specific filtered view (useful even for single-user — different browser tabs)
4. **HTMX supports this natively**: `hx-push-url="true"` on filter elements

```html
<select hx-get="/listings" hx-target="#listing-cards" hx-push-url="true" name="beds">
```

---

## 3. Design Bible Compliance — Risk Assessment

### ✅ Low Risk (Direct Transfer)

These design bible requirements transfer directly from mockups to Jinja2 templates:

| Requirement | Risk | Notes |
|------------|------|-------|
| Font: Inter (400–800) | ✅ None | Google Fonts CDN link stays the same |
| Price: 20px/800 weight | ✅ None | CSS unchanged |
| Horizontal card layout | ✅ None | HTML/CSS from `sunnynest-v4.html` drops in |
| Max 3 badges per card | ✅ None | Jinja2 `{% for badge in listing.badges[:3] %}` |
| Area in sqft AND m² | ✅ None | Jinja2 `{{ listing.sqft }} sqft ({{ listing.sqm }} m²)` |
| Color palette (grays + #2563eb) | ✅ None | CSS variables unchanged |
| Border radius (12px cards, 8px buttons, 16px pills) | ✅ None | CSS unchanged |
| Empty state with guidance | ✅ None | Jinja2 `{% if not listings %}` block |
| Error state with retry | ✅ None | HTMX `hx-on::error` handler |

### ⚠️ Medium Risk (Needs Attention During Migration)

| Requirement | Risk | Mitigation |
|------------|------|------------|
| **Dark theme** | ⚠️ Medium | The `sunnynest-v4.html` mockup uses dark theme, but the design bible has BOTH light and dark tokens. The migration plan asks the owner to decide (§12 Decision Checklist). **Recommendation**: Implement dark theme first (matches current production), add light theme toggle in Phase 3 using `prefers-color-scheme` + manual toggle. CSS variables make this trivial. |
| **Map tile theme matching** | ⚠️ Medium | Design bible §4 requires Stadia Alidade Smooth Dark for dark theme. The current production uses OpenStreetMap (light tiles on dark UI — a known mismatch, P3 item). **Recommendation**: Use Stadia dark tiles from day one in the FastAPI version. This is a one-line Leaflet config change. |
| **Loading skeleton shimmer** | ⚠️ Medium | The design bible requires skeleton placeholders, not spinners. HTMX's default `hx-indicator` shows a spinner. **Recommendation**: Override with custom skeleton HTML in `partials/listing-skeleton.html`. |
| **Hover states** | ⚠️ Low | Card hover (translateY -2px + shadow) is in the mockup CSS. Ensure it's preserved in the Jinja2 template extraction. |
| **Focus states** | ⚠️ Low | `:focus-visible` is in the mockup CSS. Ensure it's in `style.css`, not lost during template splitting. |

### 🔴 High Risk (Regression Likely Without Explicit Action)

| Requirement | Risk | Mitigation |
|------------|------|------------|
| **`aria-live` on dynamic content** | 🔴 High | HTMX swaps DOM content, but screen readers need `aria-live="polite"` on the swap target to announce changes. The listing cards container, result count, and filter summary must all have `aria-live` regions. **This is not mentioned in the migration plan.** |
| **Keyboard navigation** | 🔴 High | The plan mentions "Arrow keys for card navigation" in Phase 3. This is too late — keyboard users need Tab navigation through cards from Phase 1. Each card must be `tabindex="0"` with `role="article"` and keyboard-accessible favorite/dislike buttons. |
| **Touch targets (44×44px)** | 🔴 High | The favorite button in `sunnynest-v4.html` is 30×30px (line 146). This violates WCAG AA touch target requirements. **Must be fixed to 44×44px minimum** in the Jinja2 template. |
| **Map popup accessibility** | 🔴 High | Leaflet popups are not keyboard-accessible by default. Custom popup content must include focusable elements and be reachable via Tab. |

---

## 4. UX Improvements Enabled by Migration

These improvements are **impossible in Streamlit** but become trivial with FastAPI + HTMX:

### 4.1 Animations & Transitions (High Impact)

| Animation | Streamlit | FastAPI + HTMX |
|-----------|-----------|---------------|
| Card hover lift + shadow | ❌ Unreliable (wrapper divs intercept) | ✅ Native CSS `transform` + `box-shadow` |
| Card enter animation (stagger) | ❌ Impossible | ✅ CSS `@keyframes` with `animation-delay: calc(var(--i) * 50ms)` |
| Favorite heart pulse | ❌ Impossible | ✅ CSS `@keyframes pulse` on toggle |
| Filter pill active transition | ❌ Partial (Streamlit re-renders) | ✅ Smooth CSS transition on class toggle |
| Card removal (dislike) | ❌ Instant disappear | ✅ Fade out + slide up animation before DOM removal |
| Map marker bounce on select | ❌ Limited (Folium wrapper) | ✅ Leaflet native `setIcon()` with CSS animation |
| Skeleton → content transition | ❌ Impossible | ✅ CSS `opacity` + `transform` fade-in |
| Page transitions | ❌ Full page rerun | ✅ HTMX `hx-swap="innerHTML transition:true"` with View Transitions API |

### 4.2 Layout Fixes (Critical)

| Issue | Streamlit | FastAPI + HTMX |
|-------|-----------|---------------|
| Empty space gaps | ❌ 530 lines of CSS hacks | ✅ No wrapper divs = no gaps |
| Map height matching panel | ❌ Manual `st_folium(height=800)` | ✅ `height: 100%` on Leaflet container |
| Filter bar sticky | ❌ Streamlit controls scroll | ✅ `position: sticky; top: 0` |
| Card image alignment | ❌ Recurring bugs (see lessons learned) | ✅ Standard flexbox, no framework interference |
| Scrollbar styling | ❌ Browser default | ✅ Custom `::-webkit-scrollbar` (already in mockup) |

### 4.3 Mobile Experience (New Capability)

| Feature | Implementation |
|---------|---------------|
| Stacked layout (< 768px) | CSS `flex-direction: column` on `.split` |
| Map toggle button | Floating button to show/hide map on mobile |
| Swipe to dismiss cards | Touch event listeners (small JS) |
| Bottom sheet filters | CSS `position: fixed; bottom: 0` filter panel |
| Pull to refresh | HTMX + touch event → `hx-get="/listings"` |

### 4.4 Performance Improvements

| Feature | Streamlit | FastAPI + HTMX |
|---------|-----------|---------------|
| Initial page load | Full Python rerun + WebSocket | Single HTML response (~50KB) |
| Filter change | Full page rerun (all 73 `st.*` calls) | Partial swap (~5KB HTML fragment) |
| Favorite toggle | Full page rerun | Single button HTML swap (~200 bytes) |
| Image loading | All at once | Native `loading="lazy"` |
| Map initialization | Folium generates full HTML each time | Leaflet initializes once, markers update via JS |

---

## 5. CSS Framework Decision

### Recommendation: **Custom CSS (no framework)** ✅

| Option | Verdict | Reasoning |
|--------|---------|-----------|
| **Custom CSS** ✅ | **Recommended** | The mockups already have 500+ lines of production-quality CSS with design tokens. Adding a framework would require rewriting all of it. |
| Tailwind CSS | ❌ Not recommended | Requires a build step (PostCSS), adds toolchain complexity for a solo developer. Utility classes would make Jinja2 templates harder to read. Conflicts with the "solo dev friendly" requirement (R6). |
| Bootstrap | ❌ Not recommended | Opinionated styles would conflict with the design bible's custom tokens. Bootstrap's card component doesn't match the horizontal layout. Would need extensive overrides. |
| Pico CSS | ⚠️ Consider for backoffice only | Classless CSS framework that styles semantic HTML. Could simplify backoffice forms/tables. But the backoffice mockup already has custom CSS. |

### CSS Architecture Recommendation

Instead of a framework, organize the custom CSS into a design system:

```
web/static/css/
├── tokens.css          # CSS variables from design bible (colors, spacing, typography)
├── reset.css           # Box-sizing, margin reset, font smoothing
├── layout.css          # Split panel, filter bar, responsive breakpoints
├── components/
│   ├── card.css        # Listing card (horizontal layout, hover, selected, skeleton)
│   ├── filter.css      # Filter pills, dropdowns, active states
│   ├── map.css         # Map container, popups, price pills, POI markers
│   ├── badge.css       # Status badges, source pills
│   ├── button.css      # Favorite, dislike, action buttons
│   ├── toast.css       # SSE notification toasts
│   └── empty-state.css # Empty, error, loading states
└── utilities.css       # Helpers (sr-only, truncate, flex gaps)
```

**Total estimated CSS**: ~800–1,000 lines (vs. 530 lines of hacks in Streamlit). But these are **clean, standard CSS** — no `data-testid` selectors, no `!important` overrides, no version-dependent selectors.

### Dark/Light Theme Strategy

```css
/* tokens.css */
:root {
  /* Light theme (default) */
  --color-bg: #f5f6f8;
  --color-surface: #ffffff;
  /* ... */
}

@media (prefers-color-scheme: dark) {
  :root {
    --color-bg: #0c0f16;
    --color-surface: #1a1f2e;
    /* ... */
  }
}

/* Manual override */
[data-theme="dark"] {
  --color-bg: #0c0f16;
  --color-surface: #1a1f2e;
  /* ... */
}
```

Store theme preference in `localStorage` and apply via `data-theme` attribute on `<html>`. HTMX doesn't interfere with this because it swaps inner content, not the root element.

---

## 6. Accessibility (WCAG AA) — HTMX-Specific Concerns

### 🔴 Critical: HTMX Dynamic Content & Screen Readers

HTMX swaps DOM content without triggering native browser navigation events. Screen readers may not announce these changes unless explicitly told to.

**Required ARIA attributes on HTMX swap targets**:

```html
<!-- Listing cards container -->
<div id="listing-cards" 
     class="scroll" 
     role="feed" 
     aria-label="Rental listings"
     aria-live="polite"
     aria-busy="false">
  <!-- Cards swapped here by HTMX -->
</div>

<!-- Result count -->
<span id="result-count" 
      aria-live="polite" 
      aria-atomic="true">
  23 listings found
</span>
```

**HTMX event hooks for `aria-busy`**:
```javascript
document.body.addEventListener('htmx:beforeRequest', (e) => {
  e.detail.target?.setAttribute('aria-busy', 'true');
});
document.body.addEventListener('htmx:afterSwap', (e) => {
  e.detail.target?.setAttribute('aria-busy', 'false');
});
```

### 🔴 Critical: Focus Management After Swaps

When HTMX swaps content, focus is lost. If a user was navigating cards via keyboard and triggers a filter change, focus must be restored to the first card in the new results.

```javascript
document.body.addEventListener('htmx:afterSwap', (e) => {
  if (e.detail.target.id === 'listing-cards') {
    const firstCard = e.detail.target.querySelector('.card');
    if (firstCard) firstCard.focus();
  }
});
```

### ⚠️ Medium: Listing Card Semantics

Each listing card should use proper semantic HTML:

```html
<article class="card" 
         tabindex="0" 
         role="article"
         aria-label="$5,500/mo — 123 Main St, Sunnyvale"
         data-listing-id="{{ listing.id }}">
  <div class="thumb">
    <img src="{{ listing.image_url }}" 
         alt="Photo of {{ listing.address }}"
         loading="lazy"
         width="150" 
         height="140">
    <button class="fav" 
            aria-label="{% if listing.is_favorite %}Remove from favorites{% else %}Add to favorites{% endif %}"
            aria-pressed="{{ 'true' if listing.is_favorite else 'false' }}"
            hx-post="/api/favorite/{{ listing.id }}"
            hx-swap="outerHTML">
      {{ '♥' if listing.is_favorite else '♡' }}
    </button>
  </div>
  <div class="info">
    <div class="price">${{ listing.price }}/mo</div>
    <div class="address">{{ listing.address }}</div>
    <div class="specs">{{ listing.beds }} bd | {{ listing.baths }} ba | {{ listing.sqft }} sqft ({{ listing.sqm }} m²)</div>
    <!-- Badges, source pill, etc. -->
  </div>
</article>
```

### ⚠️ Medium: Map Accessibility

Leaflet maps are inherently challenging for accessibility. Recommendations:

1. **Skip link**: Add a "Skip to listings" link before the map for keyboard users
2. **Map description**: `aria-label="Map showing rental listings in Sunnyvale, CA"` on the map container
3. **Marker list alternative**: Consider a visually-hidden list of marker locations for screen readers
4. **Popup focus trap**: When a map popup opens, focus should move to it; Escape should close it and return focus to the marker

### ⚠️ Medium: SSE Notifications

SSE-delivered toasts must use `role="status"` and `aria-live="polite"`:

```html
<div id="sse-toast-container" 
     role="status" 
     aria-live="polite"
     aria-atomic="true">
  <!-- Toasts injected here by SSE -->
</div>
```

### Accessibility Checklist for Migration

- [ ] All HTMX swap targets have `aria-live="polite"`
- [ ] `aria-busy` toggled during HTMX requests
- [ ] Focus restored after content swaps
- [ ] Favorite buttons have `aria-pressed` and descriptive `aria-label`
- [ ] Cards are `tabindex="0"` with `role="article"`
- [ ] Images have descriptive `alt` text (not just "listing image")
- [ ] Map has `aria-label` and skip link
- [ ] SSE toasts use `role="status"`
- [ ] Touch targets ≥ 44×44px (fix favorite button from 30px → 44px)
- [ ] `prefers-reduced-motion` respected (already in mockup CSS)
- [ ] Color is never used alone — all badges have text labels (already in design bible)
- [ ] Contrast ratios verified for dark theme text on dark backgrounds

---

## 7. Mockup Clarification — Which Template to Use

The migration plan references [`user-dashboard.html`](../docs/temp/mockups/user-dashboard.html) as the template to convert. However, this file is a **generic analytics dashboard** (title: "Acme Analytics") with a sidebar, stat cards, data table, and activity feed. It does **not** contain:

- Split-panel layout (listings + map)
- Horizontal listing cards
- Filter bar with pills
- Map placeholder
- Favorite/dislike buttons

The **correct mockup** for the dashboard Jinja2 template is [`sunnynest-v4.html`](../docs/temp/mockups/sunnynest-v4.html) (543 lines), which has:

- ✅ Split-panel layout (440px left + flexible right)
- ✅ Top filter bar with pill buttons
- ✅ Horizontal listing cards with thumbnails
- ✅ Favorite button overlay
- ✅ Map placeholder area
- ✅ Dark theme with design bible tokens
- ✅ Summary bar with result count
- ✅ Skeleton loading states
- ✅ Empty state

**Recommendation**: Update the migration plan Phase 0 to reference `sunnynest-v4.html` instead of `user-dashboard.html`. The `user-dashboard.html` mockup could serve as a starting point for a future analytics/reporting page, but it is not the SunnyNest dashboard.

---

## 8. Recommended Changes to Migration Plan

### Phase 0 Changes (Foundation)

| Current | Recommended Change |
|---------|-------------------|
| Convert `user-dashboard.html` → Jinja2 | Convert **`sunnynest-v4.html`** → Jinja2 (correct mockup) |
| No CSS architecture mentioned | Add CSS file structure (tokens.css, layout.css, components/) |
| No accessibility setup | Add `aria-live` regions, focus management JS, skip links |

### Phase 1 Changes (Dashboard Core)

| Current | Recommended Change |
|---------|-------------------|
| Responsive in Phase 3 | Move responsive breakpoints to **Phase 1** |
| Map-card interaction in Phase 3 | Move bidirectional map-card sync to **Phase 1** |
| No loading skeleton spec | Add `partials/listing-skeleton.html` with shimmer animation |
| No URL-based filters | Add `hx-push-url="true"` on all filter elements |
| No focus management | Add HTMX `afterSwap` focus restoration |
| Favorite button 30px | Fix to 44×44px minimum touch target |
| No card semantics | Add `role="article"`, `tabindex="0"`, `aria-label` |

### Phase 3 Changes (Real-time & Polish)

| Current | Recommended Change |
|---------|-------------------|
| SSE with no UX spec | Add toast notification pattern (batch, don't auto-insert) |
| Keyboard shortcuts (arrow keys) | Clarify: Tab navigation is Phase 1; arrow keys within feed are Phase 3 |
| No theme toggle | Add dark/light theme toggle with `localStorage` persistence |
| No card animations | Add staggered card enter animation, dislike fade-out |

### New Phase 1 Task: Accessibility Foundation

Add these as explicit Phase 1 tasks:

- [ ] `aria-live="polite"` on listing cards container and result count
- [ ] `aria-busy` toggle during HTMX requests (global event listener)
- [ ] Focus restoration after content swaps
- [ ] Skip link: "Skip to listings" before map
- [ ] Semantic card markup (`article`, `tabindex`, `aria-label`)
- [ ] Favorite button: `aria-pressed`, `aria-label`, 44×44px touch target
- [ ] Map container: `aria-label` description

---

## 9. Template Partials Architecture

The migration plan proposes a `partials/` directory. Here's the recommended partial structure with HTMX swap boundaries:

```
web/templates/
├── base.html                    # <html>, <head>, CSS/JS includes, theme
├── dashboard.html               # Extends base. Filter bar + split panel
├── partials/
│   ├── filter-bar.html          # Full filter bar (HTMX swappable for reset)
│   ├── listing-cards.html       # Container with all cards (swap target for filters)
│   ├── listing-card.html        # Single card (swap target for favorite toggle)
│   ├── listing-skeleton.html    # 3-4 skeleton cards (shown during loading)
│   ├── result-summary.html      # "23 listings · sorted by newest" bar
│   ├── map-popup.html           # Leaflet popup content for a listing
│   ├── toast-new-listings.html  # SSE notification toast
│   ├── empty-state.html         # No results message + reset button
│   └── error-state.html         # Load failure message + retry button
├── admin/
│   ├── base.html                # Admin layout with sidebar
│   ├── dashboard.html           # KPIs page
│   ├── analytics.html           # Listing analytics
│   ├── api-usage.html           # API call tracking
│   ├── notifications.html       # Notification history
│   └── settings.html            # Email/config settings
```

**Key HTMX swap boundaries**:

| User Action | HTMX Target | Partial Swapped |
|------------|-------------|-----------------|
| Change filter | `#listing-cards` | `listing-cards.html` |
| Toggle favorite | `#fav-btn-{id}` | `listing-card.html` (just the button) |
| Dislike listing | `#card-{id}` | (removed from DOM) |
| Sort change | `#listing-cards` | `listing-cards.html` |
| SSE new listing | `#sse-toast` | `toast-new-listings.html` |
| Reset filters | `#filter-bar` + `#listing-cards` | Both partials |

---

## 10. Summary of Recommendations

### Must-Do Before Coding (P0)

1. **Use `sunnynest-v4.html` as the dashboard template**, not `user-dashboard.html`
2. **Move responsive breakpoints to Phase 1** — the split-panel must work at all sizes from day one
3. **Move map-card bidirectional sync to Phase 1** — it's core to the split-panel UX
4. **Add accessibility foundation to Phase 1** — `aria-live`, focus management, semantic markup, 44px touch targets
5. **Specify the SSE notification UX** — toast pattern, not auto-insert

### Should-Do (P1)

6. **CSS architecture**: Split into tokens/layout/components files instead of one monolithic `style.css`
7. **Loading skeletons**: Create `listing-skeleton.html` partial with shimmer animation
8. **URL-based filters**: Add `hx-push-url="true"` from Phase 1
9. **Dark theme first**: Start with dark (matches production), add light toggle in Phase 3
10. **Fix map tile mismatch**: Use Stadia dark tiles from day one

### Nice-to-Have (P2)

11. **Card enter animations**: Staggered fade-in on filter change
12. **Dislike animation**: Fade out + slide up before DOM removal
13. **Resizable split panel**: Drag handle between listings and map
14. **Theme toggle**: Manual dark/light switch with `localStorage`
15. **View Transitions API**: Smooth page transitions between dashboard and backoffice

---

*This review is based on the design bible, existing mockups, lessons learned, and WCAG AA requirements. All recommendations should be incorporated into the migration plan before coding begins.*
