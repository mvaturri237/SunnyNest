# IDEX Adoption — Phase 1 Deliverables (Manual Copy Required)

> **Status:** Architect-authored content for Phase 1.  
> **Action required:** The `.roo/` folder is protected from agent writes — the user must copy each section below into the listed path manually. Phase 1b (Code mode editing [`.roomodes`](.roomodes:1)) follows after these are placed.  
> **Author:** 🏗️ Architect mode  
> **Date:** 2026-05-08

---

## Index

| # | File | Action | Section |
|---|------|--------|---------|
| 1 | [`.roo/skill-zero-trust-execution.md`](.roo/skill-zero-trust-execution.md:1) | **CREATE** | [Section 1](#1-create-rooskill-zero-trust-executionmd) |
| 2 | [`.roo/skill-root-cause-analysis.md`](.roo/skill-root-cause-analysis.md:1) | **CREATE** | [Section 2](#2-create-rooskill-root-cause-analysismd) |
| 3 | [`.roo/skill-log-analysis-patterns.md`](.roo/skill-log-analysis-patterns.md:1) | **CREATE** | [Section 3](#3-create-rooskill-log-analysis-patternsmd) |
| 4 | [`.roo/skill-receiving-code-review.md`](.roo/skill-receiving-code-review.md:1) | **CREATE** | [Section 4](#4-create-rooskill-receiving-code-reviewmd) |
| 5 | [`.roo/skill-architect-design-review.md`](.roo/skill-architect-design-review.md:1) | **CREATE** | [Section 5](#5-create-rooskill-architect-design-reviewmd) |
| 6 | [`.roo/skill-code-review.md`](.roo/skill-code-review.md:40) | **EDIT** (replace Output Format section) | [Section 6](#6-edit-rooskill-code-reviewmd--output-format-section) |
| 7 | [`.roo/rules-ux-designer.md`](.roo/rules-ux-designer.md:16) | **EDIT** (insert Hard Stop §0) | [Section 7](#7-edit-roorules-ux-designermd--insert-hard-stop-§0) |

The Phase 1b YAML spec for the new `debug` mode lives in a separate file: [`docs/temp/debug-mode-spec.md`](docs/temp/debug-mode-spec.md:1).

---

## How to apply

For each "CREATE" section: copy the entire fenced block (the lines between `<<<FILE_START>>>` and `<<<FILE_END>>>` markers) into a new file at the exact path shown.

For each "EDIT" section: follow the surgical instructions inline (which lines to replace, which lines to insert).

---

## 1. CREATE `.roo/skill-zero-trust-execution.md`

Tier 1 — applies to ALL modes.

<<<FILE_START>>>
# Skill: Zero-Trust Execution

> **Tier 1 — applies to ALL modes.** Default posture is distrust: distrust your own assumptions, distrust prior steps, distrust tool output, distrust the user's stated intent until verified.

## Purpose
Prevent trigger-happy mistakes caused by acting on assumptions instead of evidence. Most production-impact bugs in SunnyNest came from skipping a verification step (see [Lessons Learned](../docs/memory/shared/lessonsLearned.md:134) — Jinja2 entities, CSS cache, env vars).

## When to Use
**Every non-trivial task.** Especially when:
- Editing shared config (`.roomodes`, `config.yaml`, templates, CSS)
- Acting on output from another agent
- Repeating a step that just failed
- The user says "just do it" or "should be easy"

---

## The 6-Step Workflow

### 1. THINK
> What is the user actually asking for? What is the success criterion?

Restate the goal in your own words. If you can't, ask via `ask_followup_question`.

### 2. PLAN
> What are the discrete steps? What files/tools does each touch?

Write the plan as an ordered list. Identify the **smallest reversible step** to start with.

### 3. CONSULT
> What do I need to read FIRST before acting?

- Relevant wiki entity pages ([`docs/memory/wiki/index.md`](../docs/memory/wiki/index.md:1))
- Active context ([`activeContext.md`](../docs/memory/tasks/default/activeContext.md:1))
- The actual file I'm about to edit (never assume contents)
- Sibling/parent files that might be coupled (e.g., template + CSS + cache version)

### 4. REPLAN
> Did Step 3 invalidate any of Step 2?

Often yes. Re-order, drop, or add steps based on what you learned.

### 5. VALIDATE
> Will this plan actually work? What could go wrong?

Walk through each step mentally. For each: "What if this fails? What if the file isn't what I expect? What downstream files break?"

### 6. EXECUTE
> One step at a time, smallest first, verify after each.

After each step, **explicitly check** the result before moving to the next. No batching destructive operations.

---

## The 2-Failure Escalation Rule (HARD)

> **After 2 consecutive failures on the same operation, STOP. Do NOT retry a 3rd time.**

### What counts as a failure
- Tool returned an error (non-zero exit, exception, "file not found")
- Tool was blocked (permission denied, file restriction, sandbox error)
- Output was unexpected (wrong content, empty when content expected, malformed)
- The same fix was attempted twice and the symptom persists

### What to do instead of retry #3
1. **STOP execution immediately.**
2. **Report** to the user: what was attempted, what failed, what the output was.
3. **Hypothesize** in writing: 2-3 possible root causes.
4. **Ask** the user how to proceed (or for the missing info), or escalate to a more appropriate mode.

> Retrying a 3rd time without changing approach is the #1 source of wasted tokens and corrupted state. The third retry almost never works — and often makes things worse (e.g., partial writes, half-applied diffs).

---

## The 7 "Never Assume" Principles

| # | Rule | Counter-action |
|---|------|----------------|
| 1 | Never assume **file contents** | Read the file (or relevant slice) before editing |
| 2 | Never assume **tool behavior** | Verify the output of each tool call before acting on it |
| 3 | Never assume **user intent** | Restate the goal; ask if ambiguous |
| 4 | Never assume **the previous step succeeded** | Check exit codes, output text, or re-read the file |
| 5 | Never assume **"small" changes are safe** | A 1-line CSS change still requires cache version bump and curl-verification |
| 6 | Never assume **your first instinct is correct** | Generate ≥2 options; pick with explicit reasoning |
| 7 | Never assume **another agent's output is correct** | Spot-check claims against the actual files (Code's "Wiki Entities Affected" list, Reviewer's severity calls) |

---

## SunnyNest-Specific Triggers (real past failures)

These are real bugs caused by skipping zero-trust steps. Treat them as canaries — if you're about to do anything similar, slow down.

### CSS-Not-Bumped Bug
*[Source: [`lessonsLearned.md` "CSS Cache Versioning"](../docs/memory/shared/lessonsLearned.md:144)]*

500 lines of new CSS were added to `admin.css`, but `?v=5` in `admin/base.html` was not bumped. The browser served stale CSS, the entire admin page rendered unstyled, and the Code Reviewer **approved** the change without loading the page.

**Zero-trust check:** Whenever you touch `web/static/css/*.css`, you MUST also bump the matching `?v=N` in [`web/templates/base.html`](../web/templates/base.html:1) or [`web/templates/admin/base.html`](../web/templates/admin/base.html:1), then `curl` the page to confirm.

### Jinja2-Entity Bug
*[Source: [`lessonsLearned.md` "Jinja2 Auto-Escaping"](../docs/memory/shared/lessonsLearned.md:134)]*

`{{ '&#x2713;' }}` rendered as literal text `&#x2713;` because Jinja2 escaped the `&` to `&amp;`. The whole API Usage page showed broken-looking entity codes instead of checkmarks.

**Zero-trust check:** Never put `&#x...` HTML entities inside `{{ }}` expressions. Use the actual Unicode character (`✓`, `✗`, `📊`). After any template change, `grep` the rendered HTML for `&#x` to confirm none leaked through.

### Silent Env-Var Failure
*[Source: [`lessonsLearned.md` "Silent Failure Pattern"](../docs/memory/shared/lessonsLearned.md:38)]*

`RAPIDAPI_KEY` was unset after a server restart. The scraper returned `[]` every run with no error. Nobody noticed for 5 days.

**Zero-trust check:** When testing anything that depends on env vars or external credentials, FIRST verify the credential is loaded (System Health panel, log line, manual `printenv`). Don't assume "it ran without error" means "it worked."

---

## Integration with Other Skills

- **Pairs with** [`skill-self-reflection.md`](skill-self-reflection.md:1) — REAR's "Evaluate" step uses zero-trust principles to grade your own work.
- **Pairs with** [`skill-code-review.md`](skill-code-review.md:1) — Reviewer applies "never assume another agent's output is correct" to Code's submissions.
- **Pairs with** [`skill-root-cause-analysis.md`](skill-root-cause-analysis.md:1) — Debug mode uses zero-trust before forming hypotheses.

## Quick Checklist (apply to every task)

- [ ] Stated the goal back in my own words
- [ ] Read the relevant wiki + actual files before editing
- [ ] Smallest reversible step planned first
- [ ] Verified each step's output before moving on
- [ ] Have not retried any operation more than 2 times
- [ ] No assumption from the list of 7 was relied upon without evidence
<<<FILE_END>>>

---

## 2. CREATE `.roo/skill-root-cause-analysis.md`

Tier 2 — loaded by Debug mode when investigating.

<<<FILE_START>>>
# Skill: Root Cause Analysis

> **Tier 2 — loaded by Debug mode when investigating an issue.** Pairs with [`skill-zero-trust-execution.md`](skill-zero-trust-execution.md:1) (apply zero-trust principles before forming any hypothesis).

## Purpose
Find the *true* root cause of a bug, not the first plausible-looking explanation. Stop the Debug mode from "fixing" a symptom and declaring victory.

## When to Use
- Any bug investigation lasting >5 minutes
- Production-impact issue (scraper silent, notifications missing, web 500s)
- Recurring bug ("we fixed this last week, why is it back?")

---

## The 5 Whys (with a SunnyNest worked example)

Ask "why?" until you hit a root cause that's **actionable** (not "because the universe is hard").

**Symptom:** The Zillow scraper returns 0 listings on the daily run.

| # | Why? | Answer |
|---|------|--------|
| 1 | Why does the scraper return 0 listings? | The HTTP response body is `{"message": "You are not subscribed to this API."}`. |
| 2 | Why is the API rejecting us? | Status code is `401 Unauthorized`. |
| 3 | Why are we unauthorized? | The `X-RapidAPI-Key` header was set to an expired token. |
| 4 | Why is the token expired? | RapidAPI rotated keys; we never refreshed. |
| 5 | Why didn't we refresh? | We assumed the key was long-lived and built no refresh path / no expiry monitoring. |

**Root cause:** Missing key-rotation/monitoring assumption. **Fix:** Add a startup health check that pings the API; alert if 401. (Not "set the new key and move on.")

> **Stop condition:** Stop at the first "why" whose answer is a fixable design/process gap. If you keep going, you'll end up at "because we don't have unlimited engineers," which isn't useful.

---

## Hypothesis-Then-Evidence Pattern

Before touching any code or config:

1. **Form ≤3 candidate hypotheses** for what's causing the symptom. (More than 3 = you're guessing; narrow the symptom first by reading logs.)
2. For each hypothesis, write **what evidence would confirm it** and **what evidence would refute it**.
3. **Then** go gather that evidence — read logs, query DB, curl endpoint.
4. Only after the evidence is in do you pick the winning hypothesis.

This prevents the common Debug failure mode: latching onto the first hypothesis, "fixing" it, finding the bug still happens, latching onto the next, and so on (the "shotgun debugging" anti-pattern).

---

## Differential Diagnosis Table (template)

Use this when ≥2 hypotheses are plausible. Fill it in BEFORE touching code.

| Symptom | Hypothesis | Evidence For | Evidence Against | Verdict |
|---------|-----------|--------------|------------------|---------|
| 0 listings returned | Expired API key | 401 in logs, recent RapidAPI billing email | Health check passes locally | **Likely** — verify by curl with current key |
| 0 listings returned | Search filter too narrow | Recent change to `config.yaml` filters | Other scrapers also returned 0 | **Unlikely** — would only affect Zillow |
| 0 listings returned | Network/DNS issue | Run is from launchd at 06:00 (off-hours) | Other HTTP calls succeed | **Unlikely** — but check `ping rapidapi.com` |

A row marked "Likely" with strong evidence-for and weak evidence-against → investigate first. "Unlikely" → keep in back pocket; don't waste time yet.

---

## Stop-the-Bleed-First Rule

> **For any production-impact issue, stabilize BEFORE deep RCA.**

Examples in SunnyNest terms:

| Symptom | Stop-the-bleed (do FIRST) | Then RCA |
|---------|----------------------------|----------|
| Notifications spamming user 50× per hour | Disable notification scheduler plist (`launchctl unload com.sunnynest.notify-am.plist`) | Why did anti-spam guard not trigger? |
| Web app crashing on every request | Restart with last-known-good commit | Why did this commit break it? |
| DB locked, all writes failing | Kill orphan Python processes (`pkill -f sunnynest`) | What spawned the orphan? |

The "stop the bleed" step should be reversible and well-known — never invent a novel mitigation under pressure. If you can't think of one, escalate to the user immediately.

---

## Handoff to Code Mode

Debug mode does **not** write production code. When RCA is complete:

1. Write up the diagnosis: file path, line numbers, hypothesis, proposed fix.
2. Tell the user: *"Root cause identified at `path/to/file.py:42`. Recommended fix: [1-2 lines]. Please delegate to Code mode via `new_task(mode: 'code', ...)` to apply the fix and trigger the mandatory review cycle."*
3. Do **not** call `attempt_completion` with the fix already applied — that bypasses the Code → Review cycle defined in [`AGENTS.md`](../AGENTS.md:1).

---

## Quick Checklist

- [ ] Symptom is precisely stated (file, line, error message, when it started)
- [ ] 5 Whys done, stopped at an actionable root cause
- [ ] ≤3 hypotheses formed with explicit confirm/refute evidence
- [ ] Evidence gathered BEFORE proposing a fix
- [ ] If production-impact: stop-the-bleed step applied first
- [ ] Handoff written for Code mode (no code edits attempted by Debug)
<<<FILE_END>>>

---

## 3. CREATE `.roo/skill-log-analysis-patterns.md`

Tier 2 — loaded by Debug mode when reading logs.

<<<FILE_START>>>
# Skill: Log Analysis Patterns (SunnyNest)

> **Tier 2 — loaded by Debug mode when reading logs.** Knowing where logs live and what common errors look like is half the battle.

## Purpose
Reduce time-to-first-clue when investigating issues. SunnyNest has multiple processes (scraper, notify, web, scheduler) writing to multiple files — knowing the layout saves minutes.

---

## Where SunnyNest Logs Live

All launchd-managed services write to `/tmp/sunnynest/` (NOT `~/Documents/zillow/logs/` — TCC blocks writes there; see [`lessonsLearned.md`](../docs/memory/shared/lessonsLearned.md:17)).

| Source | File | Plist | Purpose |
|--------|------|-------|---------|
| Scraper (daily 06:00) | `/tmp/sunnynest/scraper.log` | [`com.sunnynest.scraper.plist`](../com.sunnynest.scraper.plist:1) | Output of [`scripts/run-scraper.py`](../scripts/run-scraper.py:1) |
| Notify AM (daily 08:00) | `/tmp/sunnynest/notify-am.log` | [`com.sunnynest.notify-am.plist`](../com.sunnynest.notify-am.plist:1) | Email/WhatsApp notifications |
| Notify PM (daily 18:00) | `/tmp/sunnynest/notify-pm.log` | [`com.sunnynest.notify-pm.plist`](../com.sunnynest.notify-pm.plist:1) | Email/WhatsApp notifications |
| Dashboard (FastAPI/web) | `/tmp/sunnynest/dashboard.log` | [`com.sunnynest.dashboard.plist`](../com.sunnynest.dashboard.plist:1) | [`web/main.py`](../web/main.py:1) — uvicorn output |
| Backoffice (Streamlit) | `/tmp/sunnynest/backoffice.log` | [`com.sunnynest.backoffice.plist`](../com.sunnynest.backoffice.plist:1) | [`backoffice.py`](../backoffice.py:1) |
| Log rotation (weekly) | `/tmp/sunnynest/log-rotate.log` | [`com.sunnynest.log-rotate.plist`](../com.sunnynest.log-rotate.plist:1) | [`scripts/rotate-logs.sh`](../scripts/rotate-logs.sh:1) |

Archived rotations are gzipped alongside the live log: `*.log.YYYYMMDD-HHMMSS.gz` (kept 30 days).

---

## The Triage Pattern (do these in order)

### Step 1: Tail recent activity
```bash
tail -n 100 /tmp/sunnynest/scraper.log
```
Look at the last ~100 lines first. The freshest entries are usually the most relevant.

### Step 2: Grep for errors
```bash
grep -E "ERROR|WARN|Exception|Traceback" /tmp/sunnynest/scraper.log | tail -n 50
```
Filters noise. `tail` again because old errors aren't this run's problem.

### Step 3: Expand context around the error
```bash
grep -n "ERROR" /tmp/sunnynest/scraper.log | tail -n 5   # find line numbers
grep -B 5 -A 10 "ERROR" /tmp/sunnynest/scraper.log | less
```
Context above (`-B`) often shows the trigger; context below (`-A`) shows the impact / stack trace.

### Step 4: Stream live (if reproducing)
```bash
tail -F /tmp/sunnynest/scraper.log
# in another terminal:
.venv/bin/python scripts/run-scraper.py
```

---

## Common SunnyNest Error Signatures

| Signature in logs | Likely cause | Where to look next |
|-------------------|--------------|--------------------|
| `geopy.exc.GeocoderTimedOut` or `429 Too Many Requests` | Geocoder rate-limited (Nominatim 1 req/sec) | [`src/geocoder.py`](../src/geocoder.py:1) — check circuit breaker state |
| `401 Unauthorized` on RapidAPI | Expired/missing `RAPIDAPI_KEY` | `.env` file; [`lessonsLearned.md` "Silent Failure"](../docs/memory/shared/lessonsLearned.md:38) |
| `database is locked` | Concurrent writers to SQLite | Orphan process? `pgrep -fl sunnynest`; ensure only one scheduler running |
| `Run time was missed` (APScheduler) | Should NOT appear post-launchd migration | If present, an old APScheduler instance is still running — kill it |
| `Exit code: 78` (launchd) | TCC denied — log path under `~/Documents` | Check `StandardOutPath` / `StandardErrorPath` in plist; should be `/tmp/sunnynest/` |
| `[errno 8] nodename nor servname provided` | DNS / network down | `ping 8.8.8.8`; check VPN |
| `smtplib.SMTPAuthenticationError` | Bad / missing `SMTP_PASSWORD` | `.env`; admin dashboard System Health panel |
| Python `ModuleNotFoundError` from launchd run | Wrong Python or missing `PYTHONPATH` | Plist must use `.venv/bin/python` (or full Homebrew path); see [`lessonsLearned.md` macOS Python notes](../docs/memory/shared/lessonsLearned.md:71) |
| Empty log + service "exited" status | Process crashed before opening log; or wrong `WorkingDirectory` | `launchctl list \| grep sunnynest`; inspect `LastExitStatus` |

---

## Useful Commands (macOS-specific)

| Command | What it does |
|---------|--------------|
| `tail -F /tmp/sunnynest/scraper.log` | Follow log, including across truncation/rotation |
| `grep -B 5 -A 10 "ERROR" file.log` | 5 lines before, 10 after each match |
| `grep -c "ERROR" file.log` | Count of error lines |
| `awk 'NR > 1000' file.log` | Skip first 1000 lines (when log is huge) |
| `launchctl list \| grep sunnynest` | Status of all SunnyNest launchd services |
| `launchctl print gui/$(id -u)/com.sunnynest.scraper` | Detailed status of one service (last exit code, run count) |
| `log show --predicate 'process == "python3.14"' --last 1h` | macOS unified log (NOT `journalctl` — that's Linux) — useful when launchd never wrote any output |
| `pgrep -fl sunnynest` | List any running SunnyNest processes (find orphans) |

---

## Anti-Patterns (avoid)

- ❌ `cat large.log` — floods terminal, scrolls past actual error
- ❌ `grep ERROR | head` — `head` shows oldest, you want newest (`| tail`)
- ❌ Reading log without checking the timestamp range — you might be looking at yesterday's failure
- ❌ Stopping at the first `ERROR` line — the **last** error before silence is usually the cause; earlier errors may be downstream effects

---

## Quick Checklist

- [ ] Identified which log file matches the failing service
- [ ] Tailed recent lines, then greped for ERROR/WARN
- [ ] Expanded context (`-B`/`-A`) around the relevant match
- [ ] Cross-referenced the error signature against the table above
- [ ] If signature unknown, captured the exact error text for handoff to Code mode
<<<FILE_END>>>

---

## 4. CREATE `.roo/skill-receiving-code-review.md`

Tier 2 — loaded by Code mode when receiving review feedback.

<<<FILE_START>>>
# Skill: Receiving a Code Review

> **Tier 2 — loaded by Code mode when responding to feedback from `dev-reviewer`.** Don't dive into individual comments before reading the whole review. Don't accept every suggestion uncritically.

## Purpose
Code mode often gets a list of issues from the Code Reviewer. The natural urge is to start fixing the first comment immediately. That leads to:
- Conflicting fixes (fixing comment 1 invalidates comment 5)
- Accepting a wrong suggestion that would introduce a new bug
- Missing the bigger pattern across multiple comments

This skill enforces a structured response cycle.

---

## Hard Rule: Read EVERYTHING Before Acting

> **Read the entire review end-to-end before responding to any individual comment.**

Why: a P3 style comment at the bottom may be the same root issue as a P1 correctness comment at the top. A "minor" suggestion may conflict with another reviewer recommendation. You can only see the pattern by reading all of it first.

---

## Categorize Each Piece of Feedback

| Icon | Category | Examples | Response Priority |
|------|----------|----------|-------------------|
| 🔴 | **Correctness** | Logic bug, security flaw, data loss risk, broken build, race condition | **MUST fix** before re-review (P1 territory) |
| 🟠 | **Design** | Wrong abstraction, leaky module boundary, scalability concern | **SHOULD fix** before re-review (P2 territory) |
| 🟡 | **Maintainability** | Misleading name, missing docstring, duplicated logic | **SHOULD fix** if cheap; defer to follow-up if not |
| 🟢 | **Style** | Formatting, comment wording, import ordering | **MAY fix**; reviewer's call |
| 🔵 | **Question** | "Why this approach?" | **MUST respond** (with explanation, not necessarily code change) |

Process all 🔴 first, then 🟠, then 🟡, then 🟢. **Never** start with 🟢 — you'll waste time you may need on 🔴.

---

## Verification Checklist (per accepted suggestion)

Before applying ANY suggestion, ask all 5 questions. If any answer is "no" or "not sure," push back instead of applying.

1. **Does it actually fix the issue?** — Re-read the issue description, then trace the suggested fix. Does it remove the root cause or just paper over the symptom?
2. **Does it introduce new problems?** — New edge cases? New dependencies? New performance regression?
3. **Is it consistent with the rest of the codebase?** — Does it follow existing patterns? Or is it a one-off that increases maintenance burden?
4. **Is it aligned with architectural decisions?** — Check [`docs/memory/wiki/concepts/`](../docs/memory/wiki/concepts/) and relevant entity pages. Does the suggestion contradict an existing pattern (e.g., adapter pattern, app isolation)?
5. **Have I verified it works?** — Tested or traced through? "Looks right" is not "works right."

---

## When to Push Back

You **should** push back when:

- The suggestion is technically incorrect (would introduce a bug)
- The suggestion contradicts a documented architectural decision
- The suggestion is style preference disguised as correctness (e.g., "use `Optional[X]` instead of `X | None`" when the project uses `|` syntax everywhere)
- The reviewer misread the code (it already does what they're asking)

How to push back:

1. Quote the exact code line(s) that demonstrate why the suggestion is wrong.
2. Cite the file and line: `[path/to/file.py:42]`
3. Reference the contradicting pattern (wiki concept, sibling file, lessons-learned entry).
4. Propose an alternative if applicable, OR explain why the current code is already correct.
5. Stay technical and brief — no defensiveness.

---

## Response Format Template

Use this format when posting your response back to `dev-reviewer` (via the Orchestrator):

```
## Response to Code Review

### Issues Fixed (🔴 / 🟠)
- [path/to/file.py:line] <issue title> — Fixed by <one-line summary of fix>. Diff: <commit/branch ref>.
- ...

### Issues Deferred (🟡 / 🟢)
- [path/to/file.py:line] <issue title> — Deferring as <reason: out-of-scope, follow-up ticket #N, etc.>.

### Issues Disputed (push back)
- [path/to/file.py:line] <issue title> — I disagree because <evidence>. Cited: [other/file.py:line]. Proposing instead: <alternative or "leave as-is">.

### Questions Answered (🔵)
- "<reviewer's question>" — <your answer, 1-2 sentences>.

### Re-review Requested
- All 🔴 issues addressed. Ready for re-review.
```

End the response with a clear ASK: "Re-review please" OR "These deferrals OK?" — never leave it ambiguous whether you expect another round.

---

## Integration With Other Skills

- **Pairs with** [`skill-zero-trust-execution.md`](skill-zero-trust-execution.md:1) — Principle #7: never assume another agent's output is correct (applies to reviewers too).
- **Triggered by** [`skill-code-review.md`](skill-code-review.md:1) — that skill produces the review you'll receive.
- **Honors** [`AGENTS.md` review-cycle rule](../AGENTS.md:1) — only the Orchestrator's `dev-reviewer` round-trip can mark a code task complete.

## Quick Checklist

- [ ] Read the entire review before fixing anything
- [ ] Categorized each comment (🔴/🟠/🟡/🟢/🔵)
- [ ] Processed 🔴 → 🟠 → 🟡 → 🟢 in that order
- [ ] Ran 5-question verification on each accepted suggestion
- [ ] Pushed back on incorrect suggestions with cited evidence
- [ ] Posted response in the standard template
- [ ] Explicit re-review request at the end
<<<FILE_END>>>

---

## 5. CREATE `.roo/skill-architect-design-review.md`

Tier 1 — Architect mode default skill.

<<<FILE_START>>>
# Skill: Architect Design Review (ADR + Diagram Standards)

> **Tier 1 — Architect mode default skill.** Defines the ADR template, diagram standards, and plan-freshness tagging used in [`plans/`](../plans/) and [`docs/`](../docs/).

## Purpose
Bring rigor to architectural decisions:
- Every significant decision gets an ADR (Architecture Decision Record).
- Every plan diagram follows the same Mermaid conventions.
- Old plans are explicitly tagged so future readers know what's still authoritative.

---

## ADR Template

File location: `plans/adr-NNN-<short-slug>.md` (e.g., `plans/adr-001-launchd-over-apscheduler.md`).

```markdown
# ADR-NNN: <Decision in active voice>

**Status:** Proposed | Accepted | Deprecated | Superseded by [ADR-MMM](adr-MMM-...)
**Date:** YYYY-MM-DD
**Deciders:** <names / roles>
**Tags:** <e.g., scheduling, scraping, notifications>

## Context
<2-4 paragraphs: what problem are we solving? What are the constraints? What's the current state? Cite wiki entities (e.g., [Scheduler (launchd)](../docs/memory/wiki/entities/scheduler-launchd.md)).>

## Options Considered
We evaluated ≥2 options.

### Option A: <name>
- **Pros:** ...
- **Cons:** ...
- **Cost:** <effort, $, risk>

### Option B: <name>
- **Pros:** ...
- **Cons:** ...
- **Cost:** ...

### Option C (if applicable): <name>
- ...

## Decision
We chose **Option <X>**.

## Rationale
<Why X over Y/Z. Reference the constraints from Context. Be explicit about which trade-offs we accepted.>

## Consequences
**Positive:**
- ...

**Negative:** *(MANDATORY — see anti-patterns below)*
- ...

**Neutral:**
- ...

## Dependencies
- Blocks: ADR-NNN, ticket #N
- Blocked by: ADR-MMM
- Related entities: [Entity A](../docs/memory/wiki/entities/a.md), [Entity B](...)

## Review
- **Next review date:** YYYY-MM-DD (typically +180 days)
- **Triggers for early review:** <e.g., "if monthly Zillow API calls exceed 400">
```

---

## ADR Anti-Patterns (avoid these)

| # | Anti-pattern | Why it's bad | SunnyNest fix |
|---|--------------|--------------|---------------|
| 1 | **Single option presented** ("we will use X") | No evidence the decision was actually a decision | Always document ≥2 options, even if one is "do nothing" |
| 2 | **Consequences section all positive** | Every architectural choice has trade-offs; hiding them = future debt | List ≥1 negative consequence; "we accept X cost in exchange for Y benefit" |
| 3 | **Vague status** ("In progress", "Maybe?") | Future readers can't tell if this is authoritative | Use only the 4 statuses: Proposed / Accepted / Deprecated / Superseded |
| 4 | **No review date** | Decisions ossify; nobody re-evaluates | Always include `Next review date` (default +180d) |
| 5 | **Hand-wavy rationale** ("seems best", "industry standard") | Unfalsifiable; can't be challenged | Tie rationale to specific Context constraints |

> Real example: [`plans/cloud-scheduler.md`](../plans/cloud-scheduler.md:1) properly evaluated multiple options (GitHub Actions, Cloud Run, etc.) before recommending GitHub Actions + git-committed DB. Use it as a template for option-comparison structure.

---

## Mermaid Diagram Standards

### ✅ Approved Diagram Types
| Type | Use For | Example |
|------|---------|---------|
| `flowchart TD` | Pipelines, decision trees | Scrape → Normalize → Geocode → Upsert |
| `flowchart LR` | Wide horizontal flows | Source → Adapter → Orchestrator → DB |
| `sequenceDiagram` | Cross-service request flow | User → Web → DB → Render |
| `erDiagram` | DB schema | Listing ⟷ PriceHistory |
| `stateDiagram-v2` | Lifecycle | Listing: Active → Inactive → Deleted |
| `graph LR` | Simple dependency graphs | Module imports |

### ❌ Avoid
- **>15 nodes per diagram** — split into multiple linked diagrams instead
- **Unlabeled edges** — every arrow must say what passes over it (e.g., `JSON`, `listing[]`, `event`)
- **Color-only differentiation** — fails accessibility; pair color with shape or text label
- `gantt`, `pie`, `mindmap` — usually wrong tool; rewrite as a table or flowchart
- Fancy themes / custom CSS — use Mermaid defaults; consistency > prettiness

### Diagram Quality Checklist
- [ ] ≤15 nodes
- [ ] Every edge labeled (data type or trigger)
- [ ] Direction is consistent (TD or LR — don't mix in one diagram)
- [ ] Node names match real code/entity names (not abstract "Service A")
- [ ] If color used, shape or text also conveys the distinction (a11y)
- [ ] Cross-referenced from at least one wiki page or plan
- [ ] Renders correctly in GitHub preview (test before committing)

---

## Plan Freshness Tagging

Files in [`plans/`](../plans/) have a long shelf-life and silently rot. Tag every plan in [`docs/memory/wiki/index.md`](../docs/memory/wiki/index.md:1) with a freshness indicator:

| Tag | Age (since last update) | Action |
|-----|--------------------------|--------|
| 🟢 **Fresh** | <60 days | Trust as authoritative |
| 🟡 **Aging** | 60–180 days | Spot-check against current state before relying on it |
| 🔴 **Expired** | >180 days | Do NOT trust without re-validation. Either: (a) refresh and re-tag, (b) mark `SUPERSEDED`, or (c) move to `plans/archive/` |

Run a freshness audit during quarterly wiki lint per [`skill-wiki-lint.md`](skill-wiki-lint.md:1). Re-tag in the index table.

---

## Design-Bible Cross-Reference

For ANY ADR involving UI/UX or visual design, cross-reference [`docs/design/design-bible.md`](../docs/design/design-bible.md:1):

- Color, typography, spacing decisions → must align with Design Bible tokens, OR explicitly propose updating the Bible.
- Layout decisions (split-pane, card grid, etc.) → check Design Bible's layout patterns first.
- If your ADR proposes a Design Bible change, list "Updates Design Bible: §<section>" under Dependencies.

The UX Designer mode owns the Design Bible. Architect proposes; UX Designer ratifies (via a follow-up task).

---

## Wiki Impact Section (mandatory in every plan)

Every architecture plan MUST end with a Wiki Impact section per [Architect mode rules in `.roomodes`](../.roomodes:246):

```markdown
## Wiki Impact
- **New entities:** <list, or "None">
- **Updated entities:** <list>
- **New concepts:** <list, or "None">
```

This drives the Orchestrator's wiki-sync step after the plan is accepted.

---

## Quick Checklist (before publishing an ADR)

- [ ] ≥2 options evaluated, each with pros/cons/cost
- [ ] Consequences section has ≥1 negative item
- [ ] Status is one of the 4 standard values
- [ ] Review date set
- [ ] Rationale ties back to specific Context constraints
- [ ] All diagrams pass the Diagram Quality Checklist
- [ ] Wiki Impact section included
- [ ] Cross-referenced from [`plans/architecture.md`](../plans/architecture.md:1) (or note why not)
- [ ] If UI/UX-related: Design Bible alignment confirmed
<<<FILE_END>>>

---

## 6. EDIT `.roo/skill-code-review.md` — Output Format section

**Surgical edit.** In the existing file [`.roo/skill-code-review.md`](.roo/skill-code-review.md:40), find the section starting at line 40:

```
## Output Format
- Passed: [what's good]
- Issues: [prioritized list with severity P0-P3]
- Suggestions: [specific improvements with code examples]
```

…and **replace it entirely** with the block below. Keep lines 1–39 (Purpose, When to Use, Review Dimensions 1–5) unchanged.

<<<REPLACEMENT_START>>>
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
<<<REPLACEMENT_END>>>

---

## 7. EDIT `.roo/rules-ux-designer.md` — insert Hard Stop §0

**Surgical edit.** In [`.roo/rules-ux-designer.md`](.roo/rules-ux-designer.md:16), find the line:

```
## ⛔ Hard Stops

### 1. DESIGN SYSTEM COMPLIANCE
```

…and **insert the following new `### 0.` block immediately AFTER `## ⛔ Hard Stops` and BEFORE `### 1. DESIGN SYSTEM COMPLIANCE`**. Do NOT renumber the existing `### 1.` / `### 2.` / `### 3.` / `### 4.` headings — they stay as-is. (The `### 0.` numbering is intentional: it conveys "this runs before everything else.")

<<<INSERTION_START>>>
### 0. READ-WIKI-AND-TEMPLATE-FIRST (Hard Stop)
Before mocking ANY component that already exists in the live SunnyNest app, you MUST:
1. Read the corresponding wiki entity page (e.g., [`docs/memory/wiki/entities/listing-card.md`](../docs/memory/wiki/entities/listing-card.md:1))
2. Read the actual production template (e.g., [`web/templates/partials/listing-card.html`](../web/templates/partials/listing-card.html:1))
3. Read the actual CSS file (e.g., [`web/static/css/style.css`](../web/static/css/style.css:1)) for any tokens already in use

This prevents the recurring problem of mockups proposing fields, layouts, or
data shapes that don't match what's actually rendered. If the mockup intentionally
diverges from current production, that's fine — but the divergence MUST be called
out explicitly in the design notes ("Changing X from Y to Z because…").

**Exception:** Greenfield components that don't yet exist may skip this rule.

<<<INSERTION_END>>>

---

## End of Phase 1 content

After the user has copied/applied sections 1–7 above, Phase 1b can begin: Code mode applies the YAML spec from [`docs/temp/debug-mode-spec.md`](docs/temp/debug-mode-spec.md:1) to [`.roomodes`](.roomodes:1), then the new `debug` mode is live.
