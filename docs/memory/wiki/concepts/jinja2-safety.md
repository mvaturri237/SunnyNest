# Jinja2 Safety

> Never use HTML numeric entities (`&#xNNNN;`) inside Jinja2 `{{ }}` expressions — always use actual Unicode characters (✓, ✗, 📊, 🔑) to avoid auto-escaping breakage.

**Applies to:** [API Usage Page](../entities/api-usage-page.md), [Admin Dashboard](../entities/admin-dashboard.md), [Listing Card](../entities/listing-card.md)  
**Learned:** 2026-04-06  
**Source:** `docs/memory/shared/lessonsLearned.md` — Jinja2 Auto-Escaping Breaks HTML Entities

## Pattern

Jinja2's auto-escaping converts `&` to `&amp;` in template expressions. When you write `{{ '&#x2713;' }}`, Jinja2 produces `&amp;#x2713;` in the HTML output — which the browser renders as literal text `&#x2713;` instead of the intended checkmark character ✓.

HTML entities are only interpreted by the browser when they appear in raw HTML, not when they pass through Jinja2's auto-escaping pipeline.

## Rules

1. **Never use HTML numeric entities (`&#xNNNN;`) inside Jinja2 `{{ }}` expressions**
2. **Always use actual Unicode characters** (✓, ✗, 📊, 🔑) directly in templates
3. **This applies to both `{{ }}` expressions and plain HTML** — using Unicode everywhere is safer and more consistent
4. **After any template change:** `curl` the page and grep for `&#x` in the HTML output to verify no raw entities leak through
5. **Code Reviewer check:** Flag `&#x` patterns inside `{{ }}` expressions as **P1** (will render as broken text)

## Examples

- **Incident (2026-04-06):** API Usage page redesign used `&#x2713;` (✓), `&#x2717;` (✗), `&#x1F511;` (🔑) inside Jinja2 expressions. All rendered as raw entity text instead of symbols.
- **Fix:** Replaced all HTML entities with Unicode characters: `✓`, `✗`, `🔑`
- **Anti-pattern:** `{{ '&#x2713;' }}` → renders as `&#x2713;`
- **Correct:** `{{ '✓' }}` → renders as ✓

## Related

- [API Usage Page](../entities/api-usage-page.md) — where the incident occurred
- [CSS Cache Versioning](css-cache-versioning.md) — another template-related safety rule
- [Admin Dashboard](../entities/admin-dashboard.md) — all admin templates affected
