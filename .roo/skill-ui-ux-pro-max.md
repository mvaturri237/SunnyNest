# Skill: UI/UX Pro Max

## Purpose
Comprehensive UI/UX design intelligence covering visual styles, color palettes, font pairings, chart types, and component patterns.

## When to Use
- Planning or designing UI components (buttons, modals, tables, forms, charts)
- Choosing color palettes, typography, or visual styles
- Reviewing or improving existing UI/UX

## Visual Styles Reference

| Style | Characteristics | Best For |
|-------|----------------|----------|
| Glassmorphism | Frosted glass, blur, transparency | Overlays, cards, modals |
| Neumorphism | Soft extruded shapes, subtle shadows | Settings panels, controls |
| Minimalism | Whitespace, limited palette, clean type | SaaS, portfolios, docs |
| Brutalism | Raw, bold, unconventional layouts | Creative portfolios |
| Flat Design | No shadows, solid colors, clean icons | Enterprise, dashboards |
| Bento Grid | Grid-based cards, varied sizes | Dashboards, feature pages |
| Dark Mode | Dark backgrounds, accent colors | Developer tools, media apps |

## Color Palette Guide

| Category | Use Case |
|----------|----------|
| Monochromatic (shades of one hue) | Elegant, focused interfaces |
| Complementary (opposite hues) | High contrast, CTAs |
| Analogous (adjacent hues) | Harmonious, natural feel |
| Neutral + Accent (grays + bold color) | Professional SaaS |
| Dark Mode (dark grays + muted accents) | Developer tools |

### Accessibility Rules
- Contrast ratio: minimum 4.5:1 for normal text (WCAG AA)
- Large text: minimum 3:1 (18px+ or 14px+ bold)
- Never rely on color alone — use icons or labels alongside
- Avoid pure white (#fff) on pure black (#000) in dark mode

## Typography Pairings

| Style | Heading | Body |
|-------|---------|------|
| Modern SaaS | Inter | Inter |
| Editorial | Playfair Display | Source Serif Pro |
| Startup | Poppins | Nunito |
| Corporate | Roboto | Roboto |
| Creative | Space Grotesk | DM Sans |
| Technical | JetBrains Mono | Inter |
| Friendly | Quicksand | Open Sans |

### Type Scale
xs: 12px | sm: 14px | base: 16px | lg: 18px | xl: 20px | 2xl: 24px | 3xl: 30px | 4xl: 36px

## Chart Selection Guide

| Data Type | Chart | When |
|-----------|-------|------|
| Comparison | Bar chart | Comparing categories |
| Trend | Line chart | Time series |
| Proportion | Donut chart | Parts of whole (≤6 segments) |
| Distribution | Histogram | Data spread |
| Correlation | Scatter plot | Variable relationships |
| Flow | Sankey diagram | Process/conversion flows |
| Progress | Gauge / progress bar | KPIs, completion |

## Component Architecture (Atomic Design)
- Atoms: Button, Input, Badge, Icon
- Molecules: SearchBar, FormField, Card
- Organisms: Navbar, Sidebar, DataTable
- Templates: DashboardLayout, AuthLayout
- Pages: Dashboard, Settings, Profile

## UI Review Checklist
- [ ] Consistent spacing (4px/8px grid)
- [ ] Proper color contrast (WCAG AA)
- [ ] Typography hierarchy is clear
- [ ] Hover states on all interactive elements
- [ ] Focus states visible for keyboard navigation
- [ ] Loading, error, and empty states designed
- [ ] Touch targets minimum 44x44px on mobile
- [ ] No horizontal scroll on any breakpoint
