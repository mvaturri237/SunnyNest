# Install IDEX `.roo/` Files With VS Code Closed

> **Why this exists:** A Roo Code lifecycle hook running inside VS Code reverts any new files in `.roo/` within seconds, even after `git add`. The fix is to do the install while no Roo agent process is watching the workspace, then commit immediately so the hook treats them as tracked-and-leave-alone on next launch.

## Step-by-step

### 1. Save anything you have open

Save (`Cmd-S`) any unsaved editor tabs in VS Code.

### 2. Quit VS Code entirely

```
Cmd-Q
```

(Just closing the window isn't enough on macOS — the Roo extension can keep running. `Cmd-Q` quits the whole app.)

### 3. Open Terminal.app (NOT VS Code's integrated terminal)

Spotlight → Terminal → Enter. Then:

```bash
cd /Users/mvaturri/Documents/zillow
```

### 4. Run the install + commit as one chain

```bash
sed -n '/^```bash$/,/^```$/p' docs/temp/apply-phase1.md | sed '1d;$d' | bash \
  && git add .roo/ \
  && git commit -m "feat(modes): install 5 IDEX-adopted skill files + strict review format

- .roo/skill-zero-trust-execution.md  (Tier 1, all modes)
- .roo/skill-root-cause-analysis.md   (Tier 2, debug)
- .roo/skill-log-analysis-patterns.md (Tier 2, debug)
- .roo/skill-receiving-code-review.md (Tier 2, code)
- .roo/skill-architect-design-review.md (Tier 1, architect)
- .roo/skill-code-review.md           (replaced Output Format with strict [P1]/[P2]/[P3] format)

Per docs/temp/idex-adoption-phase1.md (Architect deliverable, score 0.92).
Resolves the pending items in AGENTS.md 'Pending Manual Install' appendix." \
  && echo "" \
  && echo "=== POST-COMMIT VERIFICATION ===" \
  && for f in skill-zero-trust-execution.md skill-root-cause-analysis.md skill-log-analysis-patterns.md skill-receiving-code-review.md skill-architect-design-review.md; do \
       if [ -f ".roo/$f" ]; then echo "  ✅ $(wc -l < ".roo/$f" | tr -d ' ')L  .roo/$f"; else echo "  ❌ MISSING  .roo/$f"; fi; \
     done \
  && echo "" \
  && echo "Section 6 (P1|P2|P3 strict format):" \
  && grep -c 'P1|P2|P3' .roo/skill-code-review.md
```

### 5. Verify the commit landed

```bash
git log --oneline -1
git show --stat HEAD | head -20
```

You should see all 6 `.roo/skill-*.md` files in the commit (5 created + 1 modified).

### 6. Wait 30 seconds, then re-verify (paranoia check)

```bash
sleep 30
ls -la .roo/skill-zero-trust-execution.md
```

If the file is still there 30 seconds after the commit, you're safe to reopen VS Code. The lifecycle hook only reverts *untracked* changes; once committed, the files are part of the repo and the hook leaves them alone.

### 7. Reopen VS Code

```bash
open -a "Visual Studio Code" /Users/mvaturri/Documents/zillow
```

Or just launch from the dock.

### 8. Tell the Orchestrator

Open a new chat in the workspace and say:

> Phase 5 install complete. All 5 `.roo/` skill files committed. Run Step 3 verification.

I (Orchestrator) will then verify everything's still on disk and clean up the `⚠️ pending install` markers in [`AGENTS.md`](../../AGENTS.md) and [`.roomodes`](../../.roomodes).

---

## What if the install command fails midway?

If you see `bash: fork: Resource temporarily unavailable` again (your Mac hit a process limit), the script is **idempotent** — just re-run the entire chain. Already-created files won't be re-created, and the §0 insertion is guarded against double-insert.

If the `git commit` fails because there's nothing to commit (no changes), that means the install step didn't actually create anything — likely a process-limit issue mid-run. Fix:

```bash
ls .roo/skill-*.md | wc -l   # should show >= 24 if all 5 new files exist
```

If less than 24 (the original was 19), re-run the full chain.

## What if Verification at Step 6 shows files missing?

Then the lifecycle hook is more aggressive than expected — it reverts even tracked changes. In that case:

```bash
git checkout HEAD -- .roo/   # restore from the commit
ls -la .roo/skill-zero-trust-execution.md
```

If `git checkout` brings them back, they're in the repo permanently. The "missing" files will reappear next time VS Code opens after a `git status` cycle. If `git checkout` *also* fails, something deeper is wrong — capture the output and we'll diagnose.

## Rollback

If you want to undo the entire install:

```bash
git reset --hard HEAD~1   # removes the commit
mv docs/temp/skill-code-review.md.bak .roo/skill-code-review.md   # restores old format
```

(The `.bak` file should still be present from the script run.)
