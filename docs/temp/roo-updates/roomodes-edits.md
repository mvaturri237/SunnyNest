# .roomodes Edits Required (M11)

Since `.roomodes` is in a protected folder, these edits must be applied manually.

---

## Edit 1: Orchestrator `customInstructions`

**Location:** After line 55 (after `CRITICAL: Never use switch_mode...`), before `Always explain to the user...`

**Add these two blocks:**

```
      WIKI SYNC: After the Code→Review cycle completes (approved, no P1/P2), perform wiki sync:
      1. Read the Code mode's completion message for the list of affected entities
      2. Update the affected entity pages in docs/memory/wiki/entities/
      3. Append an entry to docs/memory/wiki/log.md
      4. Update "Last Updated" dates in docs/memory/wiki/index.md
      5. Update docs/memory/tasks/default/activeContext.md (keep only 3 most recent changes)
      If the wiki sync is complex (many entities, new concepts), delegate to Architect mode via new_task.

      WIKI LINT: When the user says "/wiki-lint" or "lint the wiki", run the checks defined in .roo/skill-wiki-lint.md. Produce a lint report and fix any issues you can (you can edit .md files).
```

---

## Edit 2: Code mode `customInstructions`

**Location:** After line 188 (after `MANDATORY REVIEW RULE:` block)

**Add:**

```
      WIKI ENTITY REPORTING: In your completion message, always include a "Wiki Entities Affected" section listing which entity pages need updating. Format:
      **Wiki Entities Affected:** zillow-scraper, orchestrator, database-schema
      This helps the Orchestrator perform wiki sync after the review cycle.
```

---

## Edit 3: Architect mode `customInstructions`

**Location:** After line 225 (after `OUTPUT: Create architecture docs...`)

**Add:**

```
      WIKI ENTITY IDENTIFICATION: When creating architecture plans, identify which wiki entities are affected or newly created. Include a "Wiki Impact" section in your plan output:
      ## Wiki Impact
      - **New entities:** {list of new entity pages to create}
      - **Updated entities:** {list of existing entity pages to update}
      - **New concepts:** {list of new concept pages, if any}
```

---

## Edit 4: UX Designer `customInstructions`

**Location:** After line 151 (after `ACCESSIBILITY: Every design must meet WCAG AA...`)

**Add:**

```
      WIKI ENTITY REPORTING: In your completion message, include which wiki entity pages are affected by your design work. Format:
      **Wiki Entities Affected:** filter-bar, listing-card, map-view
```
