# CSS Cache Versioning

> Bump the `?v=N` query parameter on CSS `<link>` tags every time a CSS file is modified to prevent browsers from serving stale styles.

**Applies to:** [Admin Dashboard](../entities/admin-dashboard.md), [API Usage Page](../entities/api-usage-page.md), [Listing Card](../entities/listing-card.md), [Filter Bar](../entities/filter-bar.md)  
**Learned:** 2026-04-06  
**Source:** `docs/memory/shared/lessonsLearned.md` — CSS Cache Versioning Must Be Bumped

## Pattern

When modifying any CSS file, always bump the version query parameter (`?v=N`) in the corresponding `<link>` tag. This is a cache-busting mechanism — without it, browsers may serve stale CSS indefinitely, causing pages to render without any of the new styles.

This was discovered when ~500 lines of new CSS were added to `admin.css` but the `<link>` tag still referenced `?v=5`. The entire API Usage page rendered without any styling.

## Rules

1. **When modifying `web/static/css/admin.css`:** Always bump `?v=N` in `web/templates/admin/base.html`
2. **When modifying `web/static/css/style.css`:** Always bump `?v=N` in `web/templates/base.html`
3. **Code Reviewer check:** Verify CSS version was bumped when CSS files were modified — flag as **P1** if not (page will render with stale styles)

## Examples

- **Incident (2026-04-06):** API Usage page redesign added ~500 lines of CSS but didn't bump `?v=5` → page rendered completely unstyled
- **Also applies to config overrides:** When a code constant has a `config.yaml` counterpart (e.g., `API_BUDGET_LIMITS["realtor"] = 150` vs `monthly_budget: 100`), both must be updated together — the config value always wins at runtime

## Related

- [Admin Dashboard](../entities/admin-dashboard.md) — `admin.css` + `admin/base.html`
- [API Usage Page](../entities/api-usage-page.md) — where the incident occurred
- [Jinja2 Safety](jinja2-safety.md) — another template-related safety rule
