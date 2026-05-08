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
