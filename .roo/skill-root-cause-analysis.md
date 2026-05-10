# Skill: Root Cause Analysis

> **Tier 2 — loaded by Debug mode when investigating an issue.** Pairs with [`skill-zero-trust-execution.md`](skill-zero-trust-execution.md:1) (apply zero-trust principles before forming any hypothesis).

## Purpose
Find the *true* root cause of a bug, not the first plausible-looking explanation. Stop the Debug mode from "fixing" a symptom and declaring victory.

## When to Use
- Any bug investigation lasting >5 minutes
- Production-impact issue (scraper silent, notifications missing, web 500s)
- Recurring bug ("we fixed this last week, why is it back?")

---

---

## Pattern: Live Re-Invocation First (Silent Failures & No-Ops)

> **Default first move when the symptom is shaped "feature X didn't do Y to data Z" (silent failure, no-op bug):** BEFORE running forensic queries on the result-state Z, instrument logging on X and **re-invoke X against Z inside a `session.rollback()`-guarded REPL**. The resulting log trace pinpoints the failure path in one shot.

### Why this beats forensic-first

Forensic queries on the post-failure state tell you **scope** ("how many rows are stuck?"), but rarely **cause** ("why did the merge no-op?"). The cause is encoded in control-flow you can't see from data alone — `try`/`except` swallow points, early-return guards, conditional branches that didn't fire. A live re-invocation with INFO/DEBUG logging surfaces the missing log line in one round.

### The 5-step pattern

1. **Read the production code path** that *should* have done the thing. Identify the function name and entry point.
2. **Build a minimal rollback-guarded invocation** of that path against the actual production data:
   ```python
   from src.database import session_scope
   from src.dedup import find_and_merge_duplicate
   import logging; logging.basicConfig(level=logging.DEBUG)

   with session_scope() as s:
       try:
           result = find_and_merge_duplicate(s, listing_id=12345)
           print("RESULT:", result)
       finally:
           s.rollback()  # never commit during diagnosis
   ```
3. **Enable INFO/DEBUG logging** on the relevant logger(s). Do this BEFORE the invocation so the very first call is captured.
4. **Read the trace top-down.** The log line *immediately preceding the silent failure* is almost always the cause — usually a logged-but-swallowed exception or a conditional that returned early.
5. **Only then** run forensic queries on the result-state to assess scope ("how many other rows are affected?") — now that you know the cause, scope queries take seconds.

### Worked example: 2026-05-08 cross-source dedup `IntegrityError` silent no-op

**Symptom:** Cross-source dedup scoring correctly identified duplicates, but **zero merges had occurred for ~6 weeks**. No errors in logs. `notification_log` showed no failures.

**Anti-pattern that wasted ~$0.80 / ~4 user clicks / ~3-4 min** (rounds 2, 5, 6 of the 7-round investigation): Debug ran SQL queries against `listings` + `listing_sources` + `dedup_decision_log` looking for the missing merge rows. Found nothing — because the merges had been silently rolled back, leaving no trace.

**The one-shot fix that actually worked** (round 7): Debug invoked `find_and_merge_duplicate(session, listing_id=...)` inside a `session.rollback()`-guarded REPL with `logger.setLevel(DEBUG)`. The trace immediately surfaced:

```
DEBUG src.dedup  Inserting ListingSource(listing_id=42, source='craigslist', external_id='cl-7891') ...
WARNING src.dedup  possible race condition during merge: (sqlite3.IntegrityError) UNIQUE constraint failed: ...uq_ls_source_external_id
```

That single DEBUG -> WARNING transition pinpointed the broad `except IntegrityError` block in `_merge_duplicate()` that was masking the bug as a fake race condition. **Total time from REPL start to root cause: ~30 seconds.** Fix was 9 production lines.

### When to skip this pattern

- Symptom is a **crash with stack trace** — read the stack, no re-invocation needed.
- Symptom is **"feature X is slow"** — profile, don't re-invoke.
- Symptom is **a UI rendering bug** — `curl` the page; the rendered HTML is your evidence.
- The data Z required to reproduce X **doesn't exist anymore** (DB pruned, log rotated). Then forensic-first is the only option.

For everything else shaped "X didn't do Y to Z," default to live re-invocation first.


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
