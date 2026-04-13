# 🔍 Skill: Memory Validator

**Purpose:** Validate Memory Bank quality and ensure compliance with memory protocols.

**Owner:** IDEX Agent (can be used by all modes)

**Version:** 1.0

---

## 📋 Overview

This skill provides comprehensive validation of the IDEX Memory Bank to ensure:
1. **Completeness** - All required files exist and are populated
2. **Freshness** - Memory is current and not stale
3. **Quality** - Content is clear, concise, and actionable
4. **Compliance** - Follows memory protocols from `.clinerules` and `skill-memory-manager.md`

---

## 🎯 Validation Levels

### Level 1: File Existence

**Validates:**
- All 4 core memory files exist
- Archive directory exists
- README.md index exists
- No orphaned memory files

**Check:**
```bash
# Required files
[ -d docs/memory/tasks/ ]
[ -f docs/memory/tasks/default/activeContext.md ]
[ -f docs/memory/shared/decisionLog.md ]
[ -f docs/memory/shared/systemPatterns.md ]
[ -f docs/memory/README.md ]
[ -d docs/memory/archive ]
```

### Level 2: Freshness

**Validates:**
- Files updated recently (within 7 days for active projects)
- "Last Updated" timestamps present
- No stale information

**Check:**
```bash
# Check file modification time
find docs/memory -name "*.md" -not -path "*/archive/*" -mtime +7

# If files older than 7 days, validate reason:
# - Is project inactive? (OK)
# - Is memory stale? (NOT OK - needs update)
```

**Freshness Rules:**
- `activeContext.md`: Should be updated every task
- `progress.md`: Should be updated on milestones (at least weekly)
- `decisionLog.md`: Updated when decisions made (can be older)
- `systemPatterns.md`: Updated when patterns emerge (can be older)

### Level 3: Content Quality

**Validates:**
- Each file has required sections
- Content is concise (not exhaustive)
- No duplicate information across files
- Clear and actionable
- Proper markdown formatting

**Required Sections:**

**activeContext.md:**
- [ ] Current Focus
- [ ] Active Tasks (table format)
- [ ] Immediate Context
- [ ] Session Notes
- [ ] Last Updated timestamp

**progress.md:**
- [ ] Completed Milestones (table format)
- [ ] Ongoing Work
- [ ] Blockers (table format)
- [ ] Key Deliverables
- [ ] Last Updated timestamp

**decisionLog.md:**
- [ ] Decisions (with dates and rationale)
- [ ] Decision Patterns
- [ ] Last Updated timestamp

**systemPatterns.md:**
- [ ] Patterns (with examples)
- [ ] Conventions
- [ ] Last Updated timestamp

### Level 4: Protocol Compliance

**Validates:**
- Memory read at task start (check if protocol followed)
- Memory updated at task end (check if protocol followed)
- Auto-commit rules followed
- Archive protocol followed when needed

**Check:**
```bash
# Check git history for memory commits
git log --oneline docs/memory/ | head -10

# Verify commits follow format
git log --format="%s" docs/memory/ | grep -E "^(feat|fix|docs|refactor)\(agents\):"
```

---

## 🔧 Validation Protocol

### Step 1: Run Validation

```markdown
1. Check file existence (Level 1)
   - Verify all 4 core files exist
   - Verify README.md exists
   - Verify archive/ directory exists

2. Check freshness (Level 2)
   - Check file modification times
   - Check "Last Updated" timestamps
   - Identify stale files

3. Check content quality (Level 3)
   - Verify required sections present
   - Check content is concise
   - Look for duplicates
   - Validate markdown formatting

4. Check protocol compliance (Level 4)
   - Review git history
   - Verify commit messages
   - Check auto-commit compliance
```

### Step 2: Generate Report

```markdown
# Memory Bank Validation Report

**Date:** {timestamp}
**Validator:** {mode_name}
**Project:** IDEX

---

## 📊 Summary

**Overall Status:** {PASS|FAIL|WARNING}
**Score:** {score}/100

| Level | Status | Score | Issues |
|-------|--------|-------|--------|
| File Existence | {status} | {score}/25 | {count} |
| Freshness | {status} | {score}/25 | {count} |
| Content Quality | {status} | {score}/25 | {count} |
| Protocol Compliance | {status} | {score}/25 | {count} |

---

## 🔴 Critical Issues

{List of critical issues that MUST be fixed}

---

## ⚠️ Warnings

{List of warnings that SHOULD be addressed}

---

## ✅ Passed Checks

{List of successful validations}

---

## 🔧 Recommended Actions

{Actionable steps to improve memory quality}
```

### Step 3: Fix Issues

```markdown
IF validation score < 75:
1. Present report to user
2. Offer to fix automatically
3. Apply fixes if user approves:
   - Create missing files
   - Update stale content
   - Add missing sections
   - Fix formatting
4. Re-validate
5. Commit fixes

IF validation score >= 75:
1. Present report
2. Note any warnings
3. Continue with task
```

---

## 📊 Validation Scoring

### Scoring Formula

**Level 1: File Existence (25 points)**
```
All 4 core files exist: 15 points
README.md exists: 5 points
archive/ directory exists: 5 points
Missing files: -5 points each
```

**Level 2: Freshness (25 points)**
```
All files <7 days old: 25 points
Files 7-14 days old: 15 points
Files 14-30 days old: 10 points
Files >30 days old: 5 points
```

**Level 3: Content Quality (25 points)**
```
All required sections present: 15 points
Content is concise: 5 points
No duplicates: 5 points
Missing sections: -3 points each
```

**Level 4: Protocol Compliance (25 points)**
```
Read protocol followed: 10 points
Write protocol followed: 10 points
Auto-commit followed: 5 points
```

**Total: 100 points**

### Score Interpretation

| Score | Status | Action |
|-------|--------|--------|
| 90-100 | ✅ EXCELLENT | No action needed |
| 75-89 | ✅ GOOD | Minor improvements recommended |
| 60-74 | ⚠️ NEEDS IMPROVEMENT | Address issues soon |
| <60 | 🔴 CRITICAL | Fix immediately |

---

## 🚨 Common Issues & Fixes

### Issue 1: Stale Memory (>7 days old)

**Detection:**
```bash
find docs/memory -name "*.md" -not -path "*/archive/*" -mtime +7
```

**Fix:**
```markdown
1. Review current project status
2. Update activeContext.md with current focus
3. Update progress.md with recent milestones
4. Add "Last Updated" timestamp
5. Commit changes
```

### Issue 2: Missing Required Sections

**Detection:**
```markdown
Read file, check for required sections
```

**Fix:**
```markdown
Add missing sections with template:

## {Section Name}

{Content}
```

### Issue 3: Duplicate Information

**Detection:**
```markdown
Search for same content across files
```

**Fix:**
```markdown
Keep information in ONE file:
- Decisions → decisionLog.md
- Progress → progress.md
- Current work → activeContext.md
- Patterns → systemPatterns.md
```

### Issue 4: Verbose Content

**Detection:**
```bash
wc -l docs/memory/*.md
# If activeContext.md >200 lines, too verbose
```

**Fix:**
```markdown
1. Archive old content
2. Keep only current/relevant information
3. Summarize if needed
```

### Issue 5: Missing Timestamps

**Detection:**
```bash
grep -L "Last Updated" docs/memory/*.md
```

**Fix:**
```markdown
Add to end of each file:

---

**Last Updated:** $(date +%Y-%m-%d)
```

---

## 🛠️ Usage Examples

### Example 1: Daily Validation

```markdown
**User:** "Validate memory bank"

**IDEX Agent:**
1. Run all 4 validation levels
2. Generate validation report
3. Present report to user
4. Score: 95/100 (EXCELLENT)
5. Note: No issues found
```

### Example 2: Fix Stale Memory

```markdown
**User:** "Validate memory bank"

**IDEX Agent:**
1. Run validation
2. Find: activeContext.md is 15 days old
3. Score: 65/100 (NEEDS IMPROVEMENT)
4. Offer: "Memory is stale. Update now?"
5. User: "Yes"
6. Update activeContext.md with current focus
7. Re-validate: 95/100 (EXCELLENT)
8. Commit changes
```

### Example 3: Pre-Commit Check

```markdown
**IDEX Agent (before committing):**
1. Run validation
2. IF score < 75:
   - DO NOT commit
   - Fix issues first
   - Re-validate
3. IF score >= 75:
   - Proceed with commit
   - Include validation score in commit message
```

---

## 📋 Validation Checklist

Use this checklist for manual validation:

### File Existence
- [ ] `docs/memory/tasks/` directory exists
- [ ] `docs/memory/tasks/default/activeContext.md` exists
- [ ] `docs/memory/shared/decisionLog.md` exists
- [ ] `docs/memory/shared/systemPatterns.md` exists
- [ ] `docs/memory/README.md` exists
- [ ] `docs/memory/archive/` directory exists

### Freshness
- [ ] `activeContext.md` updated in last 7 days (or project inactive)
- [ ] `progress.md` updated in last 7 days (or no progress)
- [ ] All files have "Last Updated" timestamp
- [ ] Timestamps are accurate

### Content Quality
- [ ] `activeContext.md` has all required sections
- [ ] `progress.md` has all required sections
- [ ] `decisionLog.md` has all required sections
- [ ] `systemPatterns.md` has all required sections
- [ ] Content is concise (not exhaustive)
- [ ] No duplicate information across files
- [ ] Markdown formatting is correct

### Protocol Compliance
- [ ] Memory read at task start (per `.clinerules`)
- [ ] Memory updated at task end (per `.clinerules`)
- [ ] Changes committed (per auto-commit rules)
- [ ] Commit messages follow format
- [ ] Archive protocol followed when needed

---

## 🎯 Validation Workflow

### When to Validate

**Daily:**
- Quick check during task start (part of read protocol)
- Verify files exist and are recent

**Weekly:**
- Full validation using this skill
- Generate health report
- Fix any issues found

**Monthly:**
- Deep review and archiving
- Check for cleanup needs
- Update protocols if needed

**Before Major Milestones:**
- Full validation
- Ensure memory is current
- Archive if needed

### Validation Commands

```bash
# Quick existence check
ls -la docs/memory/*.md

# Check freshness
find docs/memory -name "*.md" -not -path "*/archive/*" -mtime +7

# Check file sizes (verbose if >200 lines)
wc -l docs/memory/*.md

# Check git history
git log --oneline docs/memory/ | head -10

# Validate markdown
markdownlint docs/memory/*.md
```

---

## 📖 References

- **Memory Manager:** [`.roo/skill-memory-manager.md`](../../.roo/skill-memory-manager.md)
- **Memory Index:** [`docs/memory/README.md`](../../docs/memory/README.md)
- **Global Rules:** [`.clinerules`](../../.clinerules:98-110) Section 7
- **Agent Context:** [`AGENTS.md`](../../AGENTS.md:7-11)
- **Advanced Features:** [`docs/plans/advanced_memory_features_analysis.md`](../advanced_memory_features_analysis.md)

---

**Last Updated:** 2026-02-12  
**Maintained By:** IDEX Agent
