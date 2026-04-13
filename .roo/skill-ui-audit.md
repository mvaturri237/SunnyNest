# Skill: UI Audit & Improvement Proposals

## Purpose
Systematically review an existing app UI (from screenshots, URLs, or HTML files) and produce a prioritized list of design improvements.

## When to Use
When asked to "review this UI", "audit this design", "improve this interface", or "what's wrong with this UI".

## Input Methods
The user may provide:
- A screenshot (image file or pasted image)
- A live URL (use browser to inspect)
- An HTML file to review
- A description of the current UI

## Audit Framework — 7 Dimensions

### 1. Visual Hierarchy (Is the most important thing obvious?)
- Is there a clear focal point on each screen?
- Do headings, subheadings, and body text have distinct sizes/weights?
- Are primary actions visually dominant over secondary ones?
- Is color used intentionally to guide attention?

### 2. Consistency (Does everything feel like one product?)
- Are button styles consistent across the app?
- Is spacing uniform (same gaps between similar elements)?
- Are fonts, colors, and icons from the same family/style?
- Do similar pages follow the same layout pattern?

### 3. Whitespace & Density (Does it breathe or feel cramped?)
- Is there enough padding inside cards, buttons, and containers?
- Are sections separated by adequate vertical space?
- Is the information density appropriate for the audience?
- Are margins consistent between the content and screen edges?

### 4. Color & Contrast (Is it accessible and intentional?)
- Does text meet WCAG AA contrast (4.5:1 for body, 3:1 for large text)?
- Are there too many colors competing for attention?
- Is color used consistently for meaning (red=error, green=success)?
- Does the palette work for colorblind users?

### 5. Typography (Is text readable and well-structured?)
- Is the body font readable at its current size (minimum 14px, ideally 16px)?
- Are there too many font families (max 2-3)?
- Is line height comfortable (1.4-1.6 for body text)?
- Are line lengths reasonable (45-75 characters per line)?

### 6. Interaction Design (Is it obvious what's clickable?)
- Do buttons look like buttons (not flat text)?
- Do links have visible differentiation (color, underline)?
- Are hover/focus states present on interactive elements?
- Are form labels visible (not placeholder-only)?
- Are error messages clear and positioned near the problem?

### 7. Responsiveness & Edge Cases (Does it work everywhere?)
- Does the layout work on mobile (320px)?
- Are touch targets large enough (44x44px minimum)?
- What happens with long text, empty states, or many items?
- Is there a loading state for async content?

## Output Format

Structure your review as:

---

## UI Audit Report: [App/Screen Name]

### Executive Summary
[2-3 sentences: overall impression, biggest strength, biggest weakness]

### Severity Scale
- P0 Critical: Blocks usability or accessibility — fix immediately
- P1 High: Significantly hurts UX — fix this sprint
- P2 Medium: Noticeable quality issue — fix this quarter
- P3 Low: Polish item — nice to have

### Findings

#### P0 — Critical
| # | Issue | Dimension | Current | Recommended |
|---|-------|-----------|---------|-------------|
| 1 | [description] | [dimension] | [what it is now] | [what it should be] |

#### P1 — High
| # | Issue | Dimension | Current | Recommended |
|---|-------|-----------|---------|-------------|

#### P2 — Medium
| # | Issue | Dimension | Current | Recommended |
|---|-------|-----------|---------|-------------|

#### P3 — Low (Polish)
| # | Issue | Dimension | Current | Recommended |
|---|-------|-----------|---------|-------------|

### Quick Wins (< 1 hour each)
1. [specific change with exact values — e.g., "Increase body font from 13px to 16px"]
2. [specific change]
3. [specific change]

### Before/After Mockup
[If requested, generate an HTML mockup showing the improved version]

---

## Rules
- Be specific: say "change padding from 8px to 16px", not "add more padding"
- Include exact values: hex colors, pixel sizes, font weights
- Prioritize by user impact, not personal preference
- Praise what works well — don't only list problems
- Limit to 15-20 findings maximum (focus on highest impact)
- Offer to create a before/after HTML mockup for the top 3 improvements
