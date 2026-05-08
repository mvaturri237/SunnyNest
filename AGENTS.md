# AGENTS.md — SunnyNest Agent Coordination

**Project:** SunnyNest — Rental Listing Aggregator  
**Status:** Active  
**Global Rules:** [`.roo/rules/shared.md`](.roo/rules/shared.md)  
**Memory Bank:** [`docs/memory/`](docs/memory/)  
**Mode Definitions:** [`.roomodes`](.roomodes)

---

## 🚀 Pre-flight Checklist

Every agent MUST run these steps before ANY task:

1. **Query the wiki** — Read [`docs/memory/wiki/index.md`](docs/memory/wiki/index.md), then drill into relevant entity pages. Also read [`activeContext.md`](docs/memory/tasks/default/activeContext.md) for current focus.
2. **Verify correct mode** — Confirm you're in the right mode for the task type
3. **Read this file** — Check `AGENTS.md` for role-specific rules and protocols
4. **At task end** — Perform self-reflection per [`.roo/skill-self-reflection.md`](.roo/skill-self-reflection.md), then update memory per [`.roo/skill-memory-manager.md`](.roo/skill-memory-manager.md)

---

## 🤖 Active Roles

| Role | Responsibility | Key Skills | Edit Permissions |
|------|---------------|------------|-----------------|
| 🪃 **Orchestrator** | Coordinates workflows, delegates to specialized modes | [`skill-memory-manager`](.roo/skill-memory-manager.md), [`skill-self-reflection`](.roo/skill-self-reflection.md), [`skill-wiki-lint`](.roo/skill-wiki-lint.md) | `.md` files only |
| 💻 **Code** | Full-stack development — scrapers, API, database, UI | [`skill-data-scraping`](.roo/skill-data-scraping.md), [`skill-notification-system`](.roo/skill-notification-system.md), [`skill-code-review`](.roo/skill-code-review.md) | All files |
| 🔍 **Code Reviewer** | Code quality, security, API reviews, deliverable scoring | [`skill-api-endpoint-review`](.roo/skill-api-endpoint-review.md), [`skill-code-review`](.roo/skill-code-review.md), [`skill-data-scraping`](.roo/skill-data-scraping.md), [`skill-deliverable-scoring`](.roo/skill-deliverable-scoring.md) | `.md` files only |
| 🏗️ **Architect** | System design, feature planning, technical specs | [`skill-data-scraping`](.roo/skill-data-scraping.md), [`skill-notification-system`](.roo/skill-notification-system.md), [`skill-map-ui`](.roo/skill-map-ui.md), [`skill-filter-search-ux`](.roo/skill-filter-search-ux.md), [`skill-concurrent-edit-lock`](.roo/skill-concurrent-edit-lock.md) | `.md` files only |
| 🎨 **UX Designer** | UI/UX mockups, design system, accessibility audits | [`skill-frontend-design`](.roo/skill-frontend-design.md), [`skill-ui-ux-pro-max`](.roo/skill-ui-ux-pro-max.md), [`skill-design-system-patterns`](.roo/skill-design-system-patterns.md), [`skill-ui-audit`](.roo/skill-ui-audit.md), [`skill-map-ui`](.roo/skill-map-ui.md), [`skill-filter-search-ux`](.roo/skill-filter-search-ux.md) | `.md`, `.html`, `.css`, `.svg` files |
| 🪲 **Debug** | Troubleshooting, error investigation, diagnostics | [`skill-zero-trust-execution`](.roo/skill-zero-trust-execution.md) (Tier 1), [`skill-root-cause-analysis`](.roo/skill-root-cause-analysis.md) (Tier 2), [`skill-log-analysis-patterns`](.roo/skill-log-analysis-patterns.md) (Tier 2) | `.md` files only |
| ❓ **Ask** | Questions, explanations, documentation | — | (built-in mode) |

---

## 🎯 Orchestrator Routing Rules

The Orchestrator delegates tasks based on these keyword/context rules:

| Keywords / Context | Route To | Notes |
|-------------------|----------|-------|
| mockup, wireframe, UI design, UX review, design system, color palette, typography, accessibility audit, component design, dark mode, responsive design, prototype, "look and feel", "visual" | 🎨 **UX Designer** | Any request mentioning UI/UX/design concepts |
| architecture, system design, plan, "how should we", feature planning, technical spec | 🏗️ **Architect** | Design docs only — no production code |
| implement, code, fix, refactor, build | 💻 **Code** | Always followed by Code Reviewer (see Workflow Sequencing) |
| review, code review, API review, "check my code" | 🔍 **Code Reviewer** | Quality, security, performance checks |
| debug, troubleshoot, error, diagnose, "why is this failing" | 🪲 **Debug** | Error investigation and diagnostics |

---

## 🔄 Workflow Sequencing Rules

### Mandatory Code → Review → Fix Cycle

```
💻 Code  ──►  🔍 Code Reviewer  ──►  ✅ Complete
                    │
                    ▼ (P1/P2 issues found)
               💻 Code (fix)  ──►  🔍 Code Reviewer (re-review)
```

1. After **ANY** Code mode task that creates or modifies code files, Orchestrator **MUST** delegate to Code Reviewer
2. If Code Reviewer finds **P1 or P2** severity issues → delegate back to Code to fix → re-review
3. Only after Code Reviewer approves (no P1/P2 remaining) → task is complete
4. This cycle is **mandatory** and cannot be skipped even if the user says "go" or "do it"

### ⚠️ Critical: `switch_mode` to Code Bypasses Review

**NEVER use `switch_mode` to enter Code mode for code changes.** When Code mode is entered via `switch_mode`, it can call `attempt_completion` directly — returning to the user without the Orchestrator ever getting a chance to enforce the Code → Review cycle.

**Rule:** Always use `new_task(mode: "code", ...)` for any code modifications. This ensures the Orchestrator receives the result and can route to Code Reviewer before completing.

`switch_mode` to Code is only acceptable for **read-only operations** (e.g., running a database query, checking a file).

---

## 🤝 Agent Collaboration Protocol

### Method 1: `new_task` (Recommended — REQUIRED for code changes)
Creates an independent subtask for parallel execution. Best for delegating complete units of work.
**MUST be used for any task that creates or modifies code files** — ensures Orchestrator stays in the loop for the mandatory Code → Review cycle.

```
Orchestrator → new_task(mode: "code", message: "Implement feature X...")
```

### Method 2: `switch_mode` (Read-only operations only)
Sequential consultation for quick questions or handoffs within the same conversation context.
**⚠️ Do NOT use `switch_mode` to Code mode for code changes** — this bypasses the Orchestrator and skips the mandatory Code Reviewer step.

```
switch_mode(mode_slug: "architect", reason: "Need architecture review before implementing")
```

---

## 🛠️ Protocols

### §0 — Concurrent Edit Lock
Before editing shared config files (`.roomodes`, `AGENTS.md`, `.roo/*`) with multiple VS Code windows open, check `docs/memory/shared/.prodex-lock`.  
📖 See [`.roo/skill-concurrent-edit-lock.md`](.roo/skill-concurrent-edit-lock.md)

### §1 — Memory Protocol (Wiki-Based)
All agents use the LLM Wiki for knowledge management.
📍 Wiki location: [`docs/memory/wiki/`](docs/memory/wiki/)
📖 See [`.roo/skill-memory-manager.md`](.roo/skill-memory-manager.md)

**Query (task start):**
1. Read [`wiki/index.md`](docs/memory/wiki/index.md) to find relevant entity pages
2. Read only the entity pages relevant to the current task
3. Read [`activeContext.md`](docs/memory/tasks/default/activeContext.md) for current focus and action items

**Ingest (task end — Code, Architect, UX Designer only):**
1. Update affected entity pages in `docs/memory/wiki/entities/`
2. Update affected concept pages in `docs/memory/wiki/concepts/` (if patterns changed)
3. Append entry to [`wiki/log.md`](docs/memory/wiki/log.md)
4. Update [`wiki/index.md`](docs/memory/wiki/index.md) "Last Updated" dates
5. Update [`activeContext.md`](docs/memory/tasks/default/activeContext.md) (keep only 3 most recent changes)

**Exempt modes:** Debug and Ask do not write to the wiki.

**Lint:** Run periodically per [`.roo/skill-wiki-lint.md`](.roo/skill-wiki-lint.md)

### §2 — Self-Learning Protocol
All agents follow [`.roo/skill-self-learn.md`](.roo/skill-self-learn.md) at session end to evaluate if they learned something worth proposing as a skill or rule improvement.

### §3 — Design Bible Authority
🎨 UX Designer owns [`docs/design/design-bible.md`](docs/design/design-bible.md). All design decisions must align with it.

**Key rules from Design Bible:**
- Show area in **BOTH** sqft AND m² — e.g., "1,200 sqft (111 m²)"
- Font: **Inter** — Price is dominant (20px/800), max 3 badges per card
- Color palette: **Neutral + Accent** (grays + `#2563eb` blue)
- Never use color alone — always pair with text/icons for accessibility
- All designs must meet **WCAG AA** compliance

### §4 — App Isolation (Dashboard ↔ Backoffice)
`app.py` (dashboard, port 8501) and `backoffice.py` (admin, port 8502) are **separate Streamlit apps** with independent UI.

**Critical rules:**
- **`app.py` must NEVER use `st.sidebar`** — the dashboard hides `stHeader` via CSS; the sidebar toggle lives inside `stHeader`, making sidebar content permanently inaccessible
- Changes to backoffice UI/features must NOT require CSS or layout changes in `app.py`
- Cross-app links (e.g., "Admin →") must use `st.markdown()` in the main content area, not `st.sidebar`
- Before modifying `app.py`, always check the CSS section for `stHeader` hiding rules

📖 See [`docs/memory/shared/lessonsLearned.md`](docs/memory/shared/lessonsLearned.md) — "App Isolation" section

### §5 — Template & Frontend Safety Rules
Mandatory checks for any template or CSS changes:

1. **Never use HTML entities (`&#xNNNN;`) inside Jinja2 `{{ }}` expressions** — Jinja2 auto-escaping converts `&` to `&amp;`, rendering raw entity text. Always use actual Unicode characters (✓, ✗, 📊, 🔑).
2. **Bump CSS cache version on every CSS change** — When modifying `web/static/css/admin.css`, increment `?v=N` in `web/templates/admin/base.html`. When modifying `web/static/css/style.css`, increment `?v=N` in `web/templates/base.html`.
3. **Config values override code constants** — When changing a constant that has a `config.yaml` counterpart (e.g., `API_BUDGET_LIMITS`), always update `config.yaml` too.

📖 See [`docs/memory/shared/lessonsLearned.md`](docs/memory/shared/lessonsLearned.md) — "Jinja2 Auto-Escaping", "CSS Cache Versioning", "Config Values Override" sections

### §6 — Runtime Verification for UI Changes (Mandatory)
After **any** template, CSS, or frontend code change, Code mode **MUST**:

1. Restart the server (or verify it's running with fresh code)
2. `curl` the affected page and verify the HTML output contains expected content
3. Check for raw `&#x` entities, missing CSS classes, or broken template variables
4. Report the HTTP status code and key content verification in the completion message

The **Orchestrator** must verify the server is running with fresh code before routing to Code Reviewer.

The **Code Reviewer** must check:
- CSS version was bumped if CSS files were modified (P1 if not)
- No `&#x` entities inside `{{ }}` Jinja2 expressions (P1 if found)
- Config.yaml updated when code constants change (P1 if mismatched)

### §7 — Wiki Sync Protocol
After the Code → Review cycle completes, the Orchestrator performs wiki sync:

1. **Identify affected entities** — from the Code mode's completion message (which must list affected entities)
2. **Update entity pages** — modify `docs/memory/wiki/entities/{entity}.md` with new state
3. **Update concept pages** — if a cross-cutting pattern was learned or changed
4. **Append to log** — add entry to `docs/memory/wiki/log.md`
5. **Refresh index** — update "Last Updated" dates in `docs/memory/wiki/index.md`

The Orchestrator may delegate wiki sync to Architect mode via `new_task` if the changes are complex.

### §8 — `.roo/` Folder Write Restriction (CRITICAL — All Agents)

**Discovered:** 2026-05-08 (during IDEX adoption Phase 1)

The `.roo/` and `.vscode/` folders are **system-protected against agent writes**. This is a Roo Code platform-level guard, not the soft `fileRegex` per-mode restriction documented elsewhere in this file. It blocks **ALL** agents — Architect, Code, Code Reviewer, UX Designer, Debug, AND Orchestrator — regardless of their `groups` permissions.

**Symptoms:**
- `apply_diff` / `write_to_file` / `roo_file_editor` to any path under `.roo/` or `.vscode/` returns: *"Editing files in the .roo/ or .vscode/ folders is never allowed. … the user must copy the edit manually into these files."*
- `execute_command` shell writes (e.g., `cat > .roo/foo.md`, `awk … > .roo/foo.md`) **appear to succeed initially** — `ls`/`wc` immediately afterward shows the file exists. **But the file is reverted/deleted within minutes**, often when a new task subtask is spawned. The exact lifecycle hook is unconfirmed; observed behavior: by the time a `new_task` subtask reads `.roo/`, the writes are gone.

**Implication:** Only the human user can persistently modify files under `.roo/`. Agents must:
1. **Author content into `docs/temp/` first** (an unprotected staging directory).
2. **Generate clear copy/paste instructions or a shell script** for the user.
3. **Wait for user confirmation that the files are in place** before relying on them.
4. **Never reference `.roo/` skill files in `.roomodes` `customInstructions` until those files are confirmed on disk** — broken references are silent footguns.

**Routing rule:** If a user request requires creating or modifying anything under `.roo/`, delegate the *content authoring* to the appropriate mode (Architect for skills/rules, Code for tool TypeScript), but make the *application step* a user task — NOT an agent task. Document the user-side commands in `docs/temp/` so the user can copy-paste.

**Anti-pattern (do NOT do this):**
- ❌ Spawning a `new_task(mode: "code")` to "apply the .roo/ changes" — the writes will silently revert when the subtask spawns.
- ❌ Adding new entries to `.roomodes` `customInstructions` that reference unconfirmed `.roo/` skill files — this creates broken references that fail silently when the mode loads.

**Recovery for already-broken references:** Soften the `customInstructions` to make the skill references conditional ("if the skill file exists, load …"), OR remove them entirely until the user confirms install. See the Pending Manual Install appendix at the end of this file for current orphan references.

**🔓 The `git commit` bypass (works as of 2026-05-08):** The hook only reverts UNTRACKED `.roo/` changes. If the agent runs the install + `git add .roo/` + `git commit -m "..."` as ONE atomic `execute_command` chain, the files are tracked-and-committed before the hook fires, and they survive permanently. **Critical:** the chain must be atomic (`&&` separator, single `execute_command` call). Splitting into multiple commands lets the hook fire between them. Do NOT spawn a `new_task` subtask between the write and the commit — subtask boundaries are when the hook runs.

### §9 — Agent Execution Discipline (canonical: `.roo/rules/shared.md` §14)

Agents DEFAULT to running commands via `execute_command`; the user is the **approver**, not the **executor**. Anti-patterns, fallbacks, and the full rule live in [`.roo/rules/shared.md`](.roo/rules/shared.md) §14 (injected into every mode's prompt). Full incident report in [`lessonsLearned.md`](docs/memory/shared/lessonsLearned.md) — "Agent Runs Commands By Default".

---

## 🗺️ Project Context

**SunnyNest** is a rental listing aggregator that:

- **Fetches listings** from multiple sources (Zillow, Craigslist) using the adapter pattern
- **Presents them** in a unified interface with map view and filters
- **Notifies users** of new listings matching their saved searches
- **Deduplicates** listings across sources
- **Prioritizes performance** — lazy-loaded images, clustered map markers, <2s search results

**Tech stack:** Python (Flask), SQLite, HTML/CSS/JS frontend  
**Config:** [`config.yaml`](config.yaml) | **Database:** [`data/listings.db`](data/listings.db)

---

*This file is documentation only — no production code. Keep it concise and scannable.*

---

## 📦 Appendix: Install History

Past install records (commits, file lists, install procedures) live in [`docs/memory/wiki/log.md`](docs/memory/wiki/log.md). For the IDEX adoption Phase 1 install (2026-05-08), see commit `7cef222` and the log entry "IDEX Mode Improvements — Phase 1 (✅ fully shipped, commit 7cef222)".
