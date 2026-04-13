# Skill: Map & Geospatial UI Patterns

## Purpose
Guide the design and implementation of map-based interfaces for location data.

## When to Use
When building or reviewing map views, location search, or geospatial features.

## Map UI Patterns

### Split-Pane Layout (SunnyNest Pattern)
- Left panel: scrollable list of results (cards)
- Right panel: interactive map with markers
- Hover on card highlights marker on map (and vice versa)
- Click on marker scrolls to and highlights the card
- Resize handle between panels (optional)

### Map Markers
- Use price as marker label (like SunnyNest does: "$5.5K")
- Color-code by source or status (purple=Zillow, orange=Craigslist)
- Cluster markers when zoomed out (show count)
- Active/selected marker should be visually distinct (larger, different color)
- Marker popup on click: thumbnail, price, beds/baths, link to detail

### Map Controls
- Search area: "Search as I move the map" toggle
- Draw area: let user draw a custom search boundary
- Zoom to results: auto-fit map bounds to show all results
- Satellite/street toggle
- Current location button

### Performance
- Only render markers visible in the current viewport
- Debounce map move events (300ms) before fetching new results
- Use marker clustering library (Supercluster, MarkerClusterer)
- Lazy-load map tiles and marker images

### Mobile Considerations
- Map and list should be toggleable (not side-by-side) on mobile
- Bottom sheet pattern: list slides up over map
- Markers must be tappable (minimum 44x44px touch target)
