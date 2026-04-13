# Skill: Wiki Lint — Knowledge Base Health Check

## Purpose
Periodic health check of the LLM Wiki to detect contradictions, stale pages,
orphans, and missing cross-references. Keeps the wiki accurate and navigable.

## When to Run
- **Manual trigger:** User says "/wiki-lint" or "lint the wiki"
- **Suggested cadence:** Every ~10 completed tasks, or when an agent notices
  inconsistencies during a Query

## Lint Checks

### L1: Stale Pages (WARNING)
- Compare each entity page's `**Last updated:**` date against `wiki/log.md`
- If an entity page hasn't been updated in 14+ days but `log.md` mentions it
  in recent entries → the page is stale and needs refresh
- **Fix:** Update the entity page with current state from the codebase

### L2: Orphan Pages (WARNING)
- Check that every page in `entities/` and `concepts/` is listed in `index.md`
- Check that every entry in `index.md` has a corresponding file
- **Fix:** Add missing entries to index, or delete orphan pages

### L3: Broken Links (ERROR)
- Scan all wiki markdown files for `[text](path)` links
- Verify each linked file exists
- **Fix:** Update or remove broken links

### L4: Missing Cross-References (INFO)
- For each entity page, check that its "Related" section links to entities
  it interacts with (based on "Owner files" overlap or shared config sections)
- **Fix:** Add missing cross-references

### L5: Contradictions (ERROR)
- Compare entity page "Current State" against actual codebase:
  - Does the entity page say a feature is "Planned" but it's already implemented?
  - Does the entity page reference a file that no longer exists?
  - Does the config section match actual `config.yaml` values?
- **Fix:** Update entity page to match codebase truth

### L6: Index Freshness (WARNING)
- Compare `index.md` "Last Updated" dates against entity page `**Last updated:**` dates
- If they disagree → index is stale
- **Fix:** Refresh index dates

### L7: Log Completeness (INFO)
- Check that recent git commits (last 7 days) have corresponding `log.md` entries
- **Fix:** Add missing log entries

### L8: activeContext.md Size (WARNING)
- If `activeContext.md` exceeds 30 lines → it's growing back into a journal
- **Fix:** Trim to pointer format (current focus + 3 recent changes + links)

## Output Format

After running lint, produce a report:

# Wiki Lint Report — YYYY-MM-DD

## Summary
- Errors: N
- Warnings: N
- Info: N

## Findings

### ❌ L5: Contradiction — scheduler-launchd.md
- Page says "APScheduler still active as fallback"
- Reality: APScheduler fully removed in 2026-04-06
- **Fix:** Update Current State section

### ⚠️ L1: Stale — geocoder.md
- Last updated: 2026-03-27 (10 days ago)
- Recent log entries mention geocoder changes
- **Fix:** Review and refresh

### ℹ️ L4: Missing cross-reference — realtor-scraper.md
- Does not link to deduplication.md (but shares orchestrator pipeline)
- **Fix:** Add to Related section

## How to Trigger

Tell any agent: "Run wiki lint" or "/wiki-lint"

The agent should:
1. Read all files in `docs/memory/wiki/`
2. Run each check (L1-L8)
3. Produce the report in the chat
4. Optionally fix issues directly (if in a mode with edit permissions)
