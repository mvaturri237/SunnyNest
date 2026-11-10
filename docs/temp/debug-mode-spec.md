# Phase 1b — `debug` Mode YAML Spec for `.roomodes`

> **Purpose:** This file contains the exact YAML block to insert into [`.roomodes`](.roomodes:1) to add the new 🪲 Debug mode.  
> **Audience:** Code mode (Phase 1b will edit `.roomodes` using this spec verbatim).  
> **Author:** 🏗️ Architect mode  
> **Date:** 2026-05-08  
> **Related:** [`docs/temp/idex-adoption-phase1.md`](idex-adoption-phase1.md:1) — sibling skill files this YAML references must exist before this YAML is added.

---

## Pre-conditions (verify BEFORE editing `.roomodes`)

The following files MUST already exist (created via Phase 1 manual copy-paste — see [`docs/temp/idex-adoption-phase1.md`](idex-adoption-phase1.md:1)):

- [`.roo/skill-zero-trust-execution.md`](.roo/skill-zero-trust-execution.md:1) — Tier 1 universal skill
- [`.roo/skill-root-cause-analysis.md`](.roo/skill-root-cause-analysis.md:1) — Tier 2 debug-mode skill
- [`.roo/skill-log-analysis-patterns.md`](.roo/skill-log-analysis-patterns.md:1) — Tier 2 debug-mode skill

If any of these is missing, STOP and inform the user — do not add the `debug` mode YAML until the skill files it references exist.

---

## Where to insert the YAML

Insert the YAML block (in the next section) into [`.roomodes`](.roomodes:1) **between the existing `code` mode and the existing `architect` mode**.

Specifically: in the current `.roomodes`, the `code` mode block ends at line **207** (the `WIKI ENTITY REPORTING` block), with a blank line, then `architect` begins at line **209**. Insert the new `debug` block in that gap (i.e., immediately after the `code` block, immediately before the `architect` block), preserving one blank line above and one blank line below.

> **Verify before inserting:** open `.roomodes` and confirm line numbers haven't shifted since 2026-05-08. The anchor is "the blank line between the end of the `code` mode's `customInstructions` and the `- slug: architect` line." If the file has changed, find that anchor by searching for `- slug: architect` and inserting **immediately above** it.

Rationale for this placement: the modes in `.roomodes` are not strictly alphabetical (orchestrator → dev-reviewer → ux-designer → code → architect), but Code → Debug → Architect groups the three "doing/diagnosing/designing" modes together logically.

---

## YAML to insert

> **Indentation note:** The block uses 2-space indentation under `customModes:`, matching the existing file style. Each field-line within a mode block is indented 4 spaces. Triggers and groups items use 6-space indentation (i.e., one level deeper). YAML block scalars use `>-` (folded, strip trailing newlines) — same style as every other mode in the file.

```yaml
  - slug: debug
    name: 🪲 Debug
    description: Troubleshoots issues, investigates errors, diagnoses problems
    roleDefinition: >-
      You are a senior debugger working on SunnyNest, a rental listing aggregator
      that fetches listings from multiple sources (Zillow, Craigslist, Realtor)
      and presents them in a unified web interface. You specialize in systematic
      debugging — reading logs, forming hypotheses, gathering evidence, and
      identifying root causes. You do NOT write production code; you produce
      diagnoses that Code mode then implements.
    whenToUse: >-
      Use this mode when troubleshooting issues, investigating errors, or
      diagnosing problems. Specialized in systematic debugging, log analysis,
      stack trace reading, and root cause analysis.
    triggers:
      - "debug"
      - "troubleshoot"
      - "error"
      - "diagnose"
      - "why is this failing"
      - "investigate"
      - "stack trace"
    groups:
      - read
      - command
      - - edit
        - fileRegex: \.md$
          description: Markdown files only — Debug mode does not edit code
    customInstructions: >-
      PRE-FLIGHT: At task start, read AGENTS.md for role-specific rules and coordination protocols.

      SKILLS — Tier 1 (load every task):
      - .roo/skill-zero-trust-execution.md — distrust-by-default workflow, 2-failure escalation rule, 7 "never assume" principles

      SKILLS — Tier 2 (load when relevant):
      - .roo/skill-root-cause-analysis.md — load when investigating any bug; provides 5 Whys, hypothesis-evidence pattern, differential diagnosis table, stop-the-bleed-first rule
      - .roo/skill-log-analysis-patterns.md — load whenever you need to read logs; provides SunnyNest log file locations (/tmp/sunnynest/), triage pattern, and a table of common SunnyNest error signatures

      APP AWARENESS (SunnyNest dual-app pattern):
      - app.py is the dashboard (Streamlit, port 8501) — it MUST NOT use st.sidebar
      - backoffice.py is the admin panel (Streamlit, port 8502) — separate app, separate UI
      - web/main.py is the FastAPI dashboard (port 8000) — current production frontend
      - Database: data/listings.db (SQLite); a "database is locked" error usually means orphan processes — check with `pgrep -fl sunnynest`
      - Scheduling: launchd plists `com.sunnynest.scraper`, `com.sunnynest.notify-am`, `com.sunnynest.notify-pm`, `com.sunnynest.dashboard`, `com.sunnynest.backoffice`, `com.sunnynest.log-rotate`
      - Logs: /tmp/sunnynest/*.log (NOT under ~/Documents — TCC blocks writes there)
      - Python: ALWAYS use .venv/bin/python; bare `python` does not exist on macOS

      2-FAILURE ESCALATION RULE (HARD):
      After 2 consecutive failures on the same operation, STOP. Do not retry a 3rd time.
      Instead: report what failed, hypothesize 2-3 root causes, and ask the user how to proceed
      OR escalate to a more appropriate mode. See .roo/skill-zero-trust-execution.md for full details.

      HANDOFF RULE (CRITICAL — Debug does NOT write production code):
      If the root cause requires a code fix, you MUST NOT attempt the fix yourself.
      Instead, write up the diagnosis with:
      1. The exact file and line number of the root cause
      2. A 1-2 sentence hypothesis explaining the bug
      3. A proposed fix (1-2 lines of code or specific action)
      4. Any related wiki entities the fix will affect
      Then instruct the user: "Please delegate this fix to Code mode via new_task(mode: 'code', ...)
      so the mandatory Code → Review cycle runs (see AGENTS.md)."
      Calling attempt_completion with code edits applied bypasses the review cycle and is forbidden.

      AT TASK END:
      Perform self-reflection per .roo/skill-self-reflection.md (the REAR cycle).
      Debug mode is EXEMPT from wiki ingest per AGENTS.md §1 — do NOT update entity pages,
      concept pages, log.md, or activeContext.md. Wiki ingest happens only after Code mode
      applies the fix and Code Reviewer approves.

```

---

## Verification (after inserting)

After Code mode inserts the YAML and saves `.roomodes`:

1. **Validate YAML syntax** — run a YAML parser or VS Code's built-in linter. Common issues:
   - Mixed tabs/spaces (use spaces only — 2-space indent at top level)
   - Wrong nesting depth on `groups` (the inner `- - edit` / `- fileRegex` pattern is intentional — matches existing modes)
   - Trailing whitespace on `>-` block scalar lines
2. **Confirm mode appears** — restart the agent / reload modes; the 🪲 Debug entry should appear in the mode picker.
3. **Smoke test** — switch to Debug mode and ask: "What skills do you load?" — it should mention `skill-zero-trust-execution`, `skill-root-cause-analysis`, and `skill-log-analysis-patterns`.
4. **Permission test** — try to ask Debug to edit `src/orchestrator.py`. It should refuse (only `.md` allowed by `fileRegex: \.md$`). If it accepts, the `groups` block was misformatted.

---

## Rollback plan

If the new mode breaks anything (YAML parse failure, mode picker glitch, etc.):

1. Open [`.roomodes`](.roomodes:1).
2. Delete the entire `- slug: debug` block (everything from `  - slug: debug` through the blank line after the final `customInstructions`).
3. Save. The previous mode set is restored.
4. Report what failed; loop back to Architect to fix the spec.

---

## Acceptance criteria for Phase 1b complete

- [ ] All 3 referenced skill files exist in `.roo/`
- [ ] YAML block inserted between `code` and `architect` modes in `.roomodes`
- [ ] YAML parses cleanly (no syntax errors)
- [ ] 🪲 Debug appears in the mode picker
- [ ] Debug mode loads `skill-zero-trust-execution.md` on task start
- [ ] Debug mode refuses to edit non-`.md` files (permission test passes)
- [ ] [`AGENTS.md`](../../AGENTS.md:1) "Active Roles" table for Debug is updated to remove the "(built-in mode)" note and reflect the new skill set
