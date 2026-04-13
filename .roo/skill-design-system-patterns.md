# Skill: Design System Patterns

## Purpose
Guide creation of scalable design systems: tokens, theming, component architecture, and documentation.

## When to Use
- Creating or defining design tokens
- Implementing theme switching (light/dark mode)
- Building component libraries
- Reviewing component architecture

## Design Token Taxonomy

| Level | Purpose | Example |
|-------|---------|---------|
| Primitive | Raw values | #3B82F6, 16px |
| Semantic | Contextual meaning | color-action-primary |
| Component | Component-specific | button-bg-primary |

### Token Naming Convention

Pattern: {category}-{property}-{variant}-{state}

Examples:
  color-bg-primary
  color-bg-primary-hover
  color-text-secondary
  font-size-heading-lg
  shadow-elevation-high
  border-radius-button

### Spacing Scale (4px base)

| Token | Value |
|-------|-------|
| space-0 | 0px |
| space-1 | 4px |
| space-2 | 8px |
| space-3 | 12px |
| space-4 | 16px |
| space-6 | 24px |
| space-8 | 32px |
| space-12 | 48px |
| space-16 | 64px |

## Component API Principles

- Single responsibility: one component, one purpose
- Composition over config: compose small parts
- Sensible defaults: works without props
- Accessible by default: ARIA built in

## Component States

| State | Visual Treatment |
|-------|-----------------|
| Default | Base styles |
| Hover | Subtle highlight |
| Focus | Visible focus ring (2px+) |
| Active | Depression or color shift |
| Disabled | Reduced opacity (0.5) |
| Loading | Spinner or skeleton |
| Error | Red border + message |
| Empty | Illustration + helpful text |

## Component Size Scale

| Size | Height | Font | Use Case |
|------|--------|------|----------|
| xs | 24px | 12px | Tags, dense UIs |
| sm | 32px | 14px | Secondary actions |
| md | 40px | 14px | Default |
| lg | 48px | 16px | Primary actions |
| xl | 56px | 18px | Hero CTAs |

## Dark Mode Checklist

- Use semantic tokens that map to different values per theme
- Background: dark grays, not pure black
- Text: off-white, not pure white
- Elevation: conveyed through lighter surfaces (not shadows)
- Status colors: adjusted for dark backgrounds
- Detect user preference via prefers-color-scheme
- Persist theme choice across sessions (localStorage)
- No flash of wrong theme on page load
