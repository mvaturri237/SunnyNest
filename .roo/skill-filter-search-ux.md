# Skill: Filter & Search UX Patterns

## Purpose
Guide the design of filter bars, search interfaces, and faceted navigation.

## When to Use
When building or reviewing search, filter, or faceted navigation UI.

## Filter Bar Patterns

### Pill/Chip Filters (SunnyNest Pattern)
- Active filters shown as pills with current value
- Click pill to open dropdown/popover with options
- "X" on pill to clear that filter
- "Clear All" button when any filter is active
- Show result count that updates as filters change

### Filter Types
| Filter | UI Pattern | Example |
|--------|-----------|---------|
| Range (price, sqft) | Dual slider + input fields | $5K - $6.5K |
| Multi-select (beds, baths) | Chip group or checkbox list | 3-4 Beds |
| Single-select (type) | Radio group or dropdown | For Rent / For Sale |
| Boolean (features) | Toggle switches | Has Parking, Pet Friendly |
| Location | Autocomplete + map | Sunnyvale, CA 94087 |
| Source | Multi-select chips | Zillow, Craigslist |

### Search UX Rules
- Show result count prominently ("11 rentals available")
- Update results in real-time as filters change (no "Apply" button needed)
- Preserve filters in URL (shareable search links)
- Save recent searches for quick access
- Show "No results" state with suggestions to broaden filters

### Sort Options
- Newest First (default for rentals)
- Price: Low to High / High to Low
- Distance from center
- Best Match (relevance score)

### Mobile Filter UX
- Collapse filter bar to a single "Filters" button on mobile
- Open full-screen filter panel on tap
- Show active filter count on button badge: "Filters (3)"
- "Show X results" button at bottom of filter panel
