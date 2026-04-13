# Skill: Concurrent Edit Lock Protocol

**Purpose:** Prevent write-write conflicts when multiple ProDex Agent windows are open simultaneously editing shared configuration files.
**When to Use:** Before editing shared config files when multiple VS Code windows are open.
**Key Capabilities:** Lock file spec, 5-step protocol, conflict resolution, verification, stale lock handling.

## Lock File Specification

- **Path:** `docs/memory/shared/.prodex-lock`
- **Format (JSON, one line):**
  ```json
  {"agent":"ProDex Agent","window":"<window-hint>","file":"<target-file>","started":"<ISO-timestamp>","expires":"<ISO-timestamp>","pid":<pid-or-0>}
  ```
- **TTL:** 5 minutes from `started` — any lock older than 5 minutes is considered **stale** and MUST be overwritten
- **Gitignore:** This file MUST be gitignored (ephemeral, not committed)
- **Scope:** One lock covers ONE file edit session

## Shared Files Requiring the Lock

- `.clinerules`, `.roomodes`, `AGENTS.md`
- Any file in `.roo/` (skills, rules, tools)
- `README.md`, `INSTALLATION.md`, `QUICKSTART.md`

## Protocol Steps (MANDATORY)

**Step 1 — CHECK for existing lock:**
```
file_operations(operation="exists", path="docs/memory/shared/.prodex-lock")
```
- If file does NOT exist → proceed to Step 2 (acquire lock)
- If file EXISTS → read it and go to Step 3 (evaluate lock)

**Step 2 — ACQUIRE the lock:**
Write the lock file immediately with your window context, then proceed with the edit. Release when done (Step 5).

**Step 3 — EVALUATE existing lock:**
- **Is `expires` in the past?** → Lock is **stale**. Overwrite it (go to Step 2). Log the stale lock.
- **Is `expires` in the future AND `file` matches your target?** → Lock is **active on same file**. Go to Step 4 (wait).
- **Is `expires` in the future AND `file` is DIFFERENT?** → Different file is locked. You may proceed for your file.

**Step 4 — WAIT and RETRY (active lock on same file):**
1. Report to the user: "Another ProDex Agent window is currently editing `<file>`. Waiting 60 seconds before retrying..."
2. Wait 60 seconds (do other non-conflicting work if possible)
3. Re-check the lock file (go back to Step 1)
4. If lock is still active after **3 retries** (3 minutes total): escalate to user
5. If user confirms the other window is done: treat lock as stale and overwrite (Step 2)

**Step 5 — RELEASE the lock:**
After completing ALL edits and committing:
```
file_operations(operation="write", path="docs/memory/shared/.prodex-lock", content="")
```

## Lock Verification (after acquiring)
After writing the lock file, immediately re-read it to confirm you hold it. If content is different → another instance won the race. Go to Step 4 (wait).

## Stale Lock Logging
When overwriting a stale lock, log it in `docs/memory/shared/systemPatterns.md`:
```markdown
## 🔒 Stale Lock Log
- [YYYY-MM-DD HH:MM] [@ProDex Agent]: Overrode stale lock from window="<window>" on file="<file>" (expired <ISO-timestamp>)
```

## Fast Path (Single Window — No Contention)
If you are the ONLY active ProDex Agent window (user confirms no other windows are open): **Skip the lock protocol entirely** for this session.

## What NOT to Lock
- `docs/memory/tasks/<task-name>/` files — task-specific, one window per task
- `docs/knowledge/` files — read-mostly, conflicts are low-risk
- `docs/plans/` files — read-mostly
- `docs/features/` PRD files — owned by one agent at a time

## Gitignore Setup
Ensure `.gitignore` contains:
```
docs/memory/shared/.prodex-lock
```
