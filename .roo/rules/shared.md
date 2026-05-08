# Universal Rules — SunnyNest Project

## Project Context
SunnyNest is a rental listing aggregator that scrapes/fetches listings from multiple sources
(Zillow, Craigslist, and others) and presents them in a unified interface with map view.

## Core Rules

### 1. Data Source Awareness
- Always consider multi-source implications (data format differences, deduplication)
- Never hardcode source-specific logic in shared components
- Use the adapter pattern for all external data sources

### 2. User Data Privacy
- Never store user search history without consent
- Saved searches and favorites are user-private data
- API keys for external sources must be in environment variables

### 3. Performance First
- Listing images must be lazy-loaded
- Map markers must be clustered when zoomed out
- Search results must load in under 2 seconds
- Use pagination or virtual scrolling for large result sets

### 4. Error Handling
- Never show a blank screen — always show cached data or a helpful empty state
- When a source fails, show results from other sources with a warning banner
- Log all scraping errors with source, timestamp, and error details

### 5. Code Quality
- Always explain your reasoning before making changes
- Never delete files without confirmation
- Write tests for data transformation logic (source adapters)

### 6. App Isolation (Dashboard ↔ Backoffice)
- `app.py` (dashboard) and `backoffice.py` (backoffice) are separate Streamlit apps with independent UI
- **`app.py` must NEVER use `st.sidebar`** — the dashboard hides `stHeader` via CSS; the sidebar toggle lives inside `stHeader`, making sidebar content permanently inaccessible
- Changes to backoffice UI/features must NOT require CSS or layout changes in `app.py`
- Cross-app links (e.g., "Admin →") must use `st.markdown()` in the main content area, not `st.sidebar`
- Before modifying `app.py`, always check the CSS section for `stHeader` hiding rules

---

## ⚡ 13. APPROVAL MINIMIZATION — REDUCE USER CLICKS (MEDIUM)
[Source: User request 2026-04-13]

* **Rule:** ALL agents MUST minimize the number of user approval prompts per task.
* **Why:** Every `execute_command` and built-in tool call (`read_file`, `write_to_file`, `search_files`, `list_files`, `apply_diff`) requires a manual user click. Excessive approvals cause click-fatigue and slow down workflows.
* **Mandatory Practices:**
  1. **Command Chaining:** When `execute_command` is unavoidable and you need multiple commands, chain them with `&&` or `;` into a SINGLE `execute_command` call:
     - ❌ Three separate `execute_command` calls = 3 clicks
     - ✅ `cd repos/cas && find . -name "*.py" -path "*/scanner*" | head -20 && wc -l apps/scanner-iac/common/iac_scanner_common/scanner.py` = 1 click
  2. **Parallel Tool Calls:** When multiple tool calls are independent (no data dependency between them), issue ALL of them in a single assistant response. The platform supports parallel execution.
     - ❌ Read file A → wait → read file B → wait → read file C = 3 approval rounds
     - ✅ Read files A, B, C in one response = 1 approval round
  3. **Auto-Approved First:** ALWAYS check if an auto-approved custom tool can replace a built-in tool:
     - `read_file` → use `file_operations` (read) or `roo_file_editor` (read) instead
     - `search_files` → use `workspace_search` (grep) instead
     - `list_files` → use `safe_shell` (`ls`, `tree`, `find`) or `file_operations` (list_dir) instead
     - `write_to_file` for docs/ → use `file_operations` (write) instead
     - `apply_diff` → still needed for source code edits (no auto-approved alternative)
  4. **Batch Planning:** Before starting execution, mentally group operations. If you need to read 5 files, do it in one parallel batch — not 5 sequential calls.
* **Exceptions:**
  - Sequential dependency (output of call A needed for call B) — sequential is correct
  - `apply_diff` for code edits — no auto-approved alternative exists, approval required
  - Complex interactive commands — cannot be chained safely

---

## ⚡ 14. AGENT RUNS COMMANDS — USER IS NOT A TERMINAL (P0 — User Preference)
[Source: User explicit directive 2026-05-08, codified per AGENTS.md §9]

* **Rule:** Agents DEFAULT to running commands via `execute_command`. The user is the **approver** of commands, not the **executor**.
* **Why:** Generating shell scripts and asking the user to copy-paste-and-run them is strictly worse than running them via `execute_command`. The user reads the diff/output afterward to verify; per-command approval is much less friction than copy-paste-run-paste-back.
* **Mandatory:**
  1. Use `execute_command` for any shell operation.
  2. Chain related commands with `&&` into ONE `execute_command` call.
  3. Set generous `timeout` values (60s+ for installs, 300s+ for builds).
  4. If a command hangs, kill it via `pkill -f <pattern>` in a follow-up `execute_command` — don't make the user figure out `Ctrl-C`.
  5. Chain verification into the same `execute_command` (e.g., `do_thing && verify_thing`).
* **Anti-patterns (NEVER):**
  - ❌ "Save this as `install.sh` then run it"
  - ❌ "Open Terminal.app and paste:"
  - ❌ "After this, please run `git status` and tell me what it says"
  - ❌ Markdown-with-bash-fence install scripts that require `sed`+`bash` extraction
* **Acceptable fallbacks (only when truly necessary):**
  - ✅ Command needs interactive input the agent can't provide (keychain unlock)
  - ✅ Command needs UI access (System Settings clicks)
  - ✅ User explicitly says "give me the commands, I'll run them" (rare)
* For each fallback, **explain WHY** before delegating to the user.
* See [`AGENTS.md`](../../AGENTS.md) §9 + [`docs/memory/shared/lessonsLearned.md`](../../docs/memory/shared/lessonsLearned.md) "Agent Runs Commands By Default" for the full incident report.
