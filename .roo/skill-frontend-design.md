# Skill: Frontend Design

## Purpose
Create distinctive, production-grade frontend interfaces with high design quality.

## When to Use
- Building web components, pages, or full applications
- Creating landing pages, dashboards, or admin panels
- Reviewing frontend code for design quality

## Design Philosophy

### Avoiding AI Aesthetic Traps
| Trap | Better Approach |
|------|----------------|
| Hero + 3 cards on every page | Vary layouts, use asymmetric grids |
| Gradient everything | Use gradients sparingly, as accents |
| Over-rounded corners (24px on everything) | Vary radius by component purpose |
| Same box-shadow on everything | Layer shadows, vary by elevation |
| All text center-aligned | Left-align body text, vary alignment |

### Layout Patterns
| Layout | Best For |
|--------|----------|
| Magazine (mixed columns) | Content-heavy sites, blogs |
| Dashboard (sidebar + grid) | Admin panels, analytics |
| Landing (full-width sections) | Marketing, product pages |
| App shell (fixed nav + scroll) | Web applications |
| Documentation (sidebar + TOC) | Docs, knowledge bases |

### Spacing System (8px base)
- Section spacing: 64px–120px between major sections
- Component spacing: 16px–32px between related elements
- Element spacing: 4px–12px between tightly coupled elements
- Rule: When in doubt, add more space

### Animation Rules
- Duration: 150-300ms for UI transitions
- Easing: ease-out for entrances, ease-in for exits
- Always respect `prefers-reduced-motion`
- Every animation must have a purpose (feedback, orientation, delight)

### Responsive Breakpoints
- Mobile: 320px–639px (single column)
- Tablet: 640px–1023px (2 columns)
- Desktop: 1024px–1439px (full layout)
- Wide: 1440px+ (max-width constrained)

## Quality Checklist
- [ ] Design avoids generic AI aesthetic patterns
- [ ] Layout uses intentional spacing and visual hierarchy
- [ ] Color palette is distinctive and accessible
- [ ] Typography creates clear hierarchy
- [ ] Responsive design works from 320px to 1440px+
- [ ] All interactive states defined (hover, focus, active, disabled)
