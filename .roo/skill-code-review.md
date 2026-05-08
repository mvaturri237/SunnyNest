# Skill: Code Review

## Purpose
Systematic code review for quality, security, performance, and maintainability.

## When to Use
When asked to review code, check a PR, or audit a module.

## Review Dimensions

### 1. Correctness
- Does the code do what it claims?
- Are edge cases handled (empty results, API timeouts, malformed data)?
- Are error boundaries in place?

### 2. Security
- Is user input sanitized before use?
- Are API keys/secrets stored in environment variables (not hardcoded)?
- Are third-party API responses validated before rendering?
- Is there rate limiting on scraping/sync operations?

### 3. Performance
- Are API calls batched or parallelized where possible?
- Is data cached appropriately (listing data, map tiles)?
- Are images lazy-loaded?
- Are large lists virtualized (only render visible items)?

### 4. Maintainability
- Are functions small and single-purpose?
- Is business logic separated from UI rendering?
- Are data transformations (Zillow format -> SunnyNest format) isolated in adapters?
- Is there consistent error handling pattern?

### 5. Data Integrity
- Is listing deduplication handled (same property on Zillow and Craigslist)?
- Are prices normalized to the same format across sources?
- Are stale listings detected and removed?
- Is the sync timestamp accurate?

## Output Format (Strict — MUST follow exactly)

For each issue found, use this format:

```
[P1|P2|P3] [path/to/file.py:line] Short issue title
Why: 1-2 sentence explanation of risk/impact.
Fix: 1-2 line code suggestion or specific action.
```

**Severity definitions:**
- **P1:** Bug, security flaw, data loss risk, broken build → **MUST fix** before merge
- **P2:** Design flaw, performance regression, missing edge case → **SHOULD fix** before merge
- **P3:** Maintainability, naming, style preference → **MAY fix**; reviewer's call

After all issues, end with **EXACTLY ONE** of:

- `✅ APPROVED — no P1/P2 issues` (Orchestrator may complete the task)
- `🔄 CHANGES REQUESTED — P1/P2 issues exist` (Orchestrator must delegate back to Code)

**Parsing rules (do not deviate):**

- The bracketed `[P1]` / `[P2]` / `[P3]` tokens MUST be at the **start of the line** so the Orchestrator can deterministically grep them.
- The `[path/to/file.py:line]` reference MUST come immediately after the severity token, in square brackets, with a colon-separated line number.
- The closing `✅` / `🔄` line is **mandatory** — without it, the Orchestrator cannot decide whether the cycle is complete.

**Optional sections (place BEFORE the issue list, not after):**

- `## What's Good` — 1-3 bullets of positive observations (keeps tone constructive).
- `## Suggestions (P3 polish)` — non-blocking polish items, formatted the same as P3 issues.

Example:

```
## What's Good
- Clean separation of geocoder logic into adapter
- Tests cover empty/null cases

## Issues

[P1] [src/scrapers/zillow_scraper.py:88] XSS in listing title
Why: `title` is interpolated into HTML without escaping; Zillow titles can contain script tags.
Fix: Wrap with `html.escape(title)` before passing to template.

[P2] [src/orchestrator.py:142] Missing safety threshold on mark_inactive
Why: A partial scrape failure could mark all listings inactive.
Fix: Require ≥30% of active listings be seen before deactivating others (see [Orchestrator entity](../docs/memory/wiki/entities/orchestrator.md)).

[P3] [src/utils.py:14] Function name `do_thing` is unclear
Why: Reader has to read the body to know what it does.
Fix: Rename to `convert_sqft_to_sqm`.

🔄 CHANGES REQUESTED — P1/P2 issues exist
```
