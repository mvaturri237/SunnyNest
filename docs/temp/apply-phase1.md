# Phase 1b — Apply IDEX adoption file changes

> **Purpose:** Run-anywhere script that applies the 7 remaining `.roo/` operations from
> [`docs/temp/idex-adoption-phase1.md`](idex-adoption-phase1.md:1). The 8th operation
> (adding `debug` mode to [`.roomodes`](../../.roomodes:1)) was already applied by Code mode.
>
> **Author:** 🪃 Orchestrator
> **Date:** 2026-05-08

---

## Quick run (one command)

From the project root (`/Users/mvaturri/Documents/zillow`):

```bash
sed -n '/^```bash$/,/^```$/p' docs/temp/apply-phase1.md \
  | sed '1d;$d' \
  | bash
```

That single pipeline:
1. Extracts the fenced bash block below
2. Strips the opening/closing ` ``` ` fence lines
3. Pipes the result to `bash` for execution

If you'd rather inspect first, just `cat docs/temp/apply-phase1.md` (or open this file
in VS Code) and copy the bash block manually.

---

## What the script does

| # | Operation | Target |
|---|-----------|--------|
| 1 | Create | [`.roo/skill-zero-trust-execution.md`](../../.roo/skill-zero-trust-execution.md:1) |
| 2 | Create | [`.roo/skill-root-cause-analysis.md`](../../.roo/skill-root-cause-analysis.md:1) |
| 3 | Create | [`.roo/skill-log-analysis-patterns.md`](../../.roo/skill-log-analysis-patterns.md:1) |
| 4 | Create | [`.roo/skill-receiving-code-review.md`](../../.roo/skill-receiving-code-review.md:1) |
| 5 | Create | [`.roo/skill-architect-design-review.md`](../../.roo/skill-architect-design-review.md:1) |
| 6 | Edit (replace `## Output Format` section) | [`.roo/skill-code-review.md`](../../.roo/skill-code-review.md:40) |
| 7 | Edit (insert Hard Stop §0) | [`.roo/rules-ux-designer.md`](../../.roo/rules-ux-designer.md:16) |

After the script:
- Backups for files 6 and 7 are saved in `docs/temp/*.bak` so you can `mv` them back if needed.
- The script runs 5 verification checks and prints the results.
- The script is **idempotent** for §0 insertion (skips if already present).

---

## The script

```bash
#!/usr/bin/env bash
# ============================================================================
# Phase 1 file application script — IDEX adoption
# ============================================================================
set -euo pipefail

SPEC="docs/temp/idex-adoption-phase1.md"

if [[ ! -f "$SPEC" ]]; then
  echo "❌ Spec file not found: $SPEC" >&2
  exit 1
fi

# extract content between the Nth pair of <<<S>>> / <<<E>>> markers in $SPEC.
# The marker lines themselves are stripped.
extract_block() {
  local s="$1" e="$2" n="$3"
  awk -v s="$s" -v e="$e" -v n="$n" '
    $0 == s { count++; if (count == n) { capture = 1; next } }
    $0 == e { if (capture) { capture = 0; exit } }
    capture { print }
  ' "$SPEC"
}

write_file() {
  local target="$1" nth="$2"
  echo "→ Writing $target"
  extract_block "<<<FILE_START>>>" "<<<FILE_END>>>" "$nth" > "$target"
  echo "  ✓ $(wc -l < "$target" | tr -d ' ') lines"
}

# ----- Files 1-5: create five new .roo/ skill files -----
echo "=== Files 1-5: create .roo/ skill files ==="
write_file ".roo/skill-zero-trust-execution.md"   1
write_file ".roo/skill-root-cause-analysis.md"    2
write_file ".roo/skill-log-analysis-patterns.md"  3
write_file ".roo/skill-receiving-code-review.md"  4
write_file ".roo/skill-architect-design-review.md" 5

# ----- File 6: REPLACE "## Output Format" section in skill-code-review.md -----
echo ""
echo "=== File 6: replace Output Format section in .roo/skill-code-review.md ==="
TARGET_6=".roo/skill-code-review.md"
BACKUP_6="docs/temp/skill-code-review.md.bak"
cp "$TARGET_6" "$BACKUP_6"
echo "  backup: $BACKUP_6"

OUTPUT_FMT_LINE=$(grep -n '^## Output Format$' "$TARGET_6" | head -1 | cut -d: -f1)
if [[ -z "$OUTPUT_FMT_LINE" ]]; then
  echo "❌ Could not find '## Output Format' heading in $TARGET_6" >&2
  echo "   Aborting; backup is at $BACKUP_6" >&2
  exit 1
fi
echo "  '## Output Format' found at line $OUTPUT_FMT_LINE"

TMP_6=$(mktemp)
head -n $((OUTPUT_FMT_LINE - 1)) "$TARGET_6" > "$TMP_6"
extract_block "<<<REPLACEMENT_START>>>" "<<<REPLACEMENT_END>>>" 1 >> "$TMP_6"
mv "$TMP_6" "$TARGET_6"
echo "  ✓ rewrote $TARGET_6 ($(wc -l < "$TARGET_6" | tr -d ' ') lines)"

# ----- File 7: INSERT Hard Stop §0 in rules-ux-designer.md -----
echo ""
echo "=== File 7: insert Hard Stop §0 in .roo/rules-ux-designer.md ==="
TARGET_7=".roo/rules-ux-designer.md"
BACKUP_7="docs/temp/rules-ux-designer.md.bak"
cp "$TARGET_7" "$BACKUP_7"
echo "  backup: $BACKUP_7"

if grep -q '^### 0\. READ-WIKI-AND-TEMPLATE-FIRST' "$TARGET_7"; then
  echo "  ⚠️  Hard Stop §0 already present — skipping (idempotent)"
else
  INSERT_AFTER=$(grep -n '^## ⛔ Hard Stops$' "$TARGET_7" | head -1 | cut -d: -f1)
  INSERT_BEFORE=$(grep -n '^### 1\. DESIGN SYSTEM COMPLIANCE$' "$TARGET_7" | head -1 | cut -d: -f1)

  if [[ -z "$INSERT_AFTER" || -z "$INSERT_BEFORE" ]]; then
    echo "❌ Could not locate insertion anchors in $TARGET_7" >&2
    echo "   '## ⛔ Hard Stops' line: '$INSERT_AFTER'" >&2
    echo "   '### 1. DESIGN SYSTEM COMPLIANCE' line: '$INSERT_BEFORE'" >&2
    echo "   Aborting; backup is at $BACKUP_7" >&2
    exit 1
  fi

  TMP_7=$(mktemp)
  head -n "$INSERT_AFTER" "$TARGET_7" > "$TMP_7"
  echo "" >> "$TMP_7"
  extract_block "<<<INSERTION_START>>>" "<<<INSERTION_END>>>" 1 >> "$TMP_7"
  tail -n +"$INSERT_BEFORE" "$TARGET_7" >> "$TMP_7"
  mv "$TMP_7" "$TARGET_7"
  echo "  ✓ inserted §0 in $TARGET_7 ($(wc -l < "$TARGET_7" | tr -d ' ') lines)"
fi

# ----- Verification -----
echo ""
echo "================================================================"
echo "VERIFICATION"
echo "================================================================"

echo ""
echo "Check 1 — All 5 new skill files exist:"
ls -la \
  .roo/skill-zero-trust-execution.md \
  .roo/skill-root-cause-analysis.md \
  .roo/skill-log-analysis-patterns.md \
  .roo/skill-receiving-code-review.md \
  .roo/skill-architect-design-review.md \
  2>&1 | sed 's/^/  /'

echo ""
echo "Check 2 — Strict format tokens in skill-code-review.md:"
for token in 'P1|P2|P3' 'APPROVED' 'CHANGES REQUESTED'; do
  if grep -q "$token" .roo/skill-code-review.md; then
    echo "  ✓ found token containing: $token"
  else
    echo "  ❌ missing token: $token"
  fi
done

echo ""
echo "Check 3 — Hard Stop §0 present in rules-ux-designer.md:"
if grep -q '^### 0\. READ-WIKI-AND-TEMPLATE-FIRST' .roo/rules-ux-designer.md; then
  echo "  ✓ found: ### 0. READ-WIKI-AND-TEMPLATE-FIRST"
else
  echo "  ❌ missing: ### 0. READ-WIKI-AND-TEMPLATE-FIRST"
fi

echo ""
echo "Check 4 — .roomodes still parses as valid YAML and has 6 modes:"
python3 -c "
import yaml
data = yaml.safe_load(open('.roomodes'))
slugs = [m['slug'] for m in data['customModes']]
print(f'  ✓ YAML OK — {len(slugs)} modes: {slugs}')
"

echo ""
echo "Check 5 — Debug mode references resolvable skill files:"
for f in \
  .roo/skill-zero-trust-execution.md \
  .roo/skill-root-cause-analysis.md \
  .roo/skill-log-analysis-patterns.md
do
  if [[ -f "$f" ]]; then
    echo "  ✓ $f exists"
  else
    echo "  ❌ $f MISSING"
  fi
done

echo ""
echo "================================================================"
echo "DONE"
echo "================================================================"
echo "Backups saved (use 'mv BACKUP TARGET' to revert if needed):"
echo "  docs/temp/skill-code-review.md.bak    →  .roo/skill-code-review.md"
echo "  docs/temp/rules-ux-designer.md.bak    →  .roo/rules-ux-designer.md"
echo ""
echo "Next: tell the Orchestrator 'Phase 1b done' so it can run Code Reviewer + wiki sync."
```

---

## If anything fails

The script aborts on first error (`set -euo pipefail`). Common failures and recovery:

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `Spec file not found` | You're not in the project root | `cd /Users/mvaturri/Documents/zillow` and re-run |
| `Could not find '## Output Format' heading` | Someone already edited [`.roo/skill-code-review.md`](../../.roo/skill-code-review.md:1) | Restore from `docs/temp/skill-code-review.md.bak`, investigate manually |
| `Could not locate insertion anchors` | Same as above for [`.roo/rules-ux-designer.md`](../../.roo/rules-ux-designer.md:1) | Restore from `docs/temp/rules-ux-designer.md.bak` |
| `awk` extracts an empty file | A `<<<FILE_START>>>` / `<<<FILE_END>>>` pair was renamed in the spec | Open [`docs/temp/idex-adoption-phase1.md`](idex-adoption-phase1.md:1) and check the markers haven't drifted |

To revert everything (incl. the `.roomodes` debug mode):

```bash
mv docs/temp/skill-code-review.md.bak  .roo/skill-code-review.md
mv docs/temp/rules-ux-designer.md.bak  .roo/rules-ux-designer.md
rm  .roo/skill-zero-trust-execution.md \
    .roo/skill-root-cause-analysis.md \
    .roo/skill-log-analysis-patterns.md \
    .roo/skill-receiving-code-review.md \
    .roo/skill-architect-design-review.md
git diff .roomodes   # then `git checkout .roomodes` if you want to revert that too
```

---

## Why a script (and not 7 `cp`/`heredoc` blocks)?

- **One copy-paste, not seven.** Less chance of skipping a section.
- **Idempotent for the §0 insertion.** Running twice doesn't double-insert.
- **Backups.** The two surgical edits make backups before touching the original.
- **Self-verifying.** Five verification checks at the end tell you whether you're ready
  for Code Reviewer or whether to roll back.
