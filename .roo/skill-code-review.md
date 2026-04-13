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

## Output Format
- Passed: [what's good]
- Issues: [prioritized list with severity P0-P3]
- Suggestions: [specific improvements with code examples]
