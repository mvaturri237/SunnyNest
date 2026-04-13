> 📝 **OFM Standard:** All skill files use **Obsidian Flavored Markdown (OFM)** per [[.roo/skill-obsidian|skill-obsidian.md]]. Use `[[wikilinks]]` for cross-references, `> [!warning]` for blockers, `> [!note]` for important context.

# Skill: Context Engineering

> **When to load:** When composing a context window for a complex task, when multiple knowledge sources compete for space, when retrieval quality is uncertain, or when a task requires careful token budget management.

Context engineering is the discipline of **systematically designing what goes into an LLM's context window** — not just what prompt to write, but what memory to load, what tools to include, what documents to retrieve, and in what order. It is the primary skill that separates effective agents from ineffective ones.

---

## 1. Context Budget Framework

ProDex agents operate within an **~8,192 usable token budget** per context window. Allocate deliberately:

| Slot | Content | Target Allocation | Priority |
|------|---------|-------------------|----------|
| System prompt | `.clinerules` + `.roomodes` instructions | ~3,000 tokens | Fixed |
| Active memory | `activeContext.md` + `progress.md` | ~800 tokens | 🔴 Always load |
| Skill files | Tier 1 (always) + Tier 2 (on demand) | ~500–1,500 tokens | 🔴 Load per task |
| Knowledge docs | Domain-specific reference | ~1,000–2,000 tokens | 🟡 Load selectively |
| Tool results | Live API/search output | ~500–1,000 tokens | 🟡 Load as needed |
| Conversation history | Recent turns | ~500 tokens | 🟢 Auto-managed |
| **Reserve** | For agent output + reasoning | **~500 tokens** | Fixed |

> [!warning] **Budget Overflow Rule**
> If loading all desired sources would exceed budget: drop knowledge docs before memory, drop aging docs before fresh ones, summarize tool results before dropping them entirely. Never drop activeContext.md or progress.md.

---

## 2. Source Priority Hierarchy

When multiple sources provide information on the same topic, apply this hierarchy (highest wins):

```
1. 🔴 Active memory (activeContext.md, progress.md) — most recent, task-specific
2. 🟠 Shared memory (decisionLog.md, systemPatterns.md) — cross-task decisions
3. 🟡 Fresh knowledge docs (🟢 status) — verified, domain-specific
4. 🟢 Live tool results (jira_api, confluence_read, etc.) — real-time ground truth
5. ⚪ Aging/expired knowledge docs (🟡/🔴 status) — use with caveat
6. ⬜ Gemini Deep Research (Section 24) — last resort for unknown territory
```

> [!note] **Conflict Resolution**
> If memory says X and a live tool result says Y: **live tool result wins** (it's more recent). Log the discrepancy in activeContext.md and update the knowledge doc if it's stale.

---

## 3. Retrieval Quality Checklist (Corrective RAG)

Before using any retrieved content, evaluate quality on 4 dimensions:

```
□ FRESHNESS   — Is the knowledge doc 🟢 Fresh? (not 🟡 Aging or 🔴 Expired)
□ RELEVANCE   — Does it directly address the query, or only tangentially?
□ SUFFICIENCY — Is the detail level adequate, or does it say "see source for details"?
□ CONFLICT    — Does it contradict other retrieved content or recent memory?
```

**If ANY check fails → escalate through the fallback chain:**

| Failure | Fallback Action |
|---------|----------------|
| 🔴 Expired doc | Flag to user, use with prominent warning, trigger knowledge refresh |
| 🟡 Aging doc | Use with expiry note, recommend refresh after task |
| Low relevance | Try a different knowledge doc in the same domain |
| Insufficient detail | Supplement with live tool result (jira_api, confluence_read) |
| Conflict detected | Prefer memory > live tools > knowledge docs; log conflict |
| All sources fail | Generate Gemini Deep Research prompt (Section 24) |

> [!warning] **Never silently use stale data.** Always surface quality issues to the user when they affect the answer.

---

## 4. Context Compression Techniques

When context is too large to fit within budget:

### 4a. Selective Loading
- Load only the **sections** of a knowledge doc relevant to the current query (use file_operations with offset/limit)
- Load only the **last 20 lines** of activeContext.md for quick-reference tasks
- Skip shared/projectBrief.md and shared/techContext.md after the first session (already internalized)

### 4b. Progressive Summarization
- For long tool results: extract only the fields you need (e.g., from Jira: summary, status, assignee — skip description if not needed)
- For long knowledge docs: read the header + section headings first, then load specific sections on demand

### 4c. Context Rotation
- When conversation history grows long: summarize the last 5 turns into a single "session summary" block in activeContext.md, then drop the raw history
- Checkpoint pattern: write to memory before a long tool chain so context can be reconstructed if needed

---

## 5. Retrieval Decision Tree

Use this tree to decide **which source to query** for a given information need:

```
Need information about X?
│
├─ Is X about THIS task's current state?
│   └─ YES → Read activeContext.md + progress.md (memory)
│
├─ Is X a cross-task decision or established pattern?
│   └─ YES → Read decisionLog.md or systemPatterns.md (shared memory)
│
├─ Is X domain knowledge (CWP, Outpost, DSPM, Platform, ProDex)?
│   └─ YES → Check docs/knowledge/<domain>/ (knowledge base)
│       ├─ Doc exists + 🟢 Fresh → Use it
│       ├─ Doc exists + 🟡/🔴 → Use with caveat, flag for refresh
│       └─ No doc → Go to next branch
│
├─ Is X live data (Jira status, Confluence content, current config)?
│   └─ YES → Use jira_api / confluence_read / safe_shell (live tools)
│
├─ Is X external documentation (library API, platform docs)?
│   └─ YES → Use Context7 (mcp--Context7--context7-get-library-docs)
│
└─ Is X unknown / requires deep research?
    └─ YES → Generate Gemini Deep Research prompt (Section 24)
```

---

## 6. Context Health Checks

Run these checks when a task produces unexpected results or when context feels "off":

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Agent repeats completed work | activeContext.md not read at start | Re-read memory; add to pre-flight |
| Agent uses outdated information | 🔴 Expired knowledge doc | Flag to user; refresh doc before continuing |
| Agent contradicts a prior decision | decisionLog.md not loaded | Read shared memory; apply decision |
| Agent ignores a protocol | Skill file not loaded (Tier 2) | Load the relevant skill; re-execute |
| Context window feels "full" | Too many sources loaded | Apply Section 4 compression techniques |
| Agent hallucinates a fact | No source loaded for that domain | Load the correct knowledge doc or use live tool |

> [!note] **Context Poisoning Defense**
> If you suspect context has been corrupted, run the git integrity check (git status --porcelain docs/memory/) and compare activeContext.md against progress.md. If they conflict, progress.md is the more reliable source (it is milestone-based, not session-based).

---

## 📚 Related Skills & Protocols

- **Memory protocol:** skill-memory-manager.md — what to store and when to read
- **Knowledge freshness:** .clinerules Section 21 — freshness states and agent behavior
- **Large output protection:** skill-large-output-protection.md — output token limits
- **Gemini research:** skill-gemini-research.md — deep research fallback
- **Zero-trust execution:** skill-zero-trust-execution.md — verification before action
- **Knowledge doc:** docs/knowledge/ai-engineering/context_engineering_reference.md — market context for @Product Manager

---

**Last Updated:** 2026-03-09
**Version:** 1.0
**Inspired by:** patchy631/ai-engineering-hub (MIT) — original content by ProDex Agent
