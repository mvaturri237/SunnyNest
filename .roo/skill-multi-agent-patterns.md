# Skill: Multi-Agent Architecture Patterns

**Purpose:** Guide all agents on WHEN and HOW to use multi-agent patterns — when to delegate, which pattern to use, and how to avoid common failure modes  
**When to Use:** This skill should be used when deciding whether to delegate a task to another agent, designing a multi-step workflow involving multiple agents, debugging coordination failures, or when a task exceeds single-agent context limits. Use this skill whenever delegation decisions are non-obvious — even if the user does not explicitly ask about "multi-agent patterns."  
**Owner:** @ProDex Agent  
**Applies To:** ALL agents  
**Created:** 2026-03-10  
**Version:** 1.0  
**Source:** Adapted from neolabhq/multi-agent-patterns (Smithery) + IDEX delegation patterns

---

## Core Insight: Why Multi-Agent?

Multi-agent architectures address three single-agent limitations:

1. **Context bottleneck** — context windows fill with accumulated history, degrading performance
2. **Sequential bottleneck** — tasks with parallelizable subtasks must execute one at a time
3. **Specialization** — different tasks benefit from different agent configurations

**Critical design principle:** Sub-agents exist primarily to isolate context, not to simulate organizational roles. The question is not "which role should do this?" but "which context partition enables the best result?"

**When NOT to use multi-agent:**
- Task fits in a single context window — handle inline
- Coordination overhead exceeds parallelization benefit — handle inline
- Simple, well-defined task — handle inline
- Start simple. Add multi-agent complexity only when single-agent approaches fail.

---

## Pattern 1: Supervisor/Orchestrator

**Structure:** Central agent decomposes task, delegates to specialists, synthesizes results.

IDEX implementation: @Orchestrator routes via new_task to specialized agents. Each agent writes results to memory files. @Orchestrator synthesizes.

**When to use:**
- Complex tasks with clear decomposition
- Tasks requiring coordination across domains
- Tasks where human oversight is important

**Failure mode — The Telephone Game Problem:**
Supervisors paraphrase sub-agent responses incorrectly, losing fidelity.

**Fix:** Let sub-agents write directly to shared files (memory, docs/temp/) rather than having the supervisor rewrite everything. The supervisor reads the files, not the agent summary.

---

## Pattern 2: Peer-to-Peer / Sequential Handoff

**Structure:** Agent A completes its work, writes to shared file, Agent B reads and continues.

IDEX implementation: Use new_task with explicit context passing. Each agent reads the previous agent output from memory or docs/temp/.

**When to use:**
- Tasks with clear sequential dependencies
- Tasks where each stage requires different expertise
- Tasks where context from stage N is needed for stage N+1

**Example:** @Product Manager writes PRD, then @CWP Architect reviews technical feasibility, then @Security Guardian reviews security implications.

---

## Pattern 3: Parallel Execution

**Structure:** Multiple agents work simultaneously on independent subtasks, results aggregated.

IDEX implementation: Use multiple new_task calls in the same turn. Each agent writes to a separate file. Coordinator reads all files and synthesizes.

**When to use:**
- Subtasks are independent (no dependencies between them)
- Total time approaches the longest subtask (not the sum)
- Different domains need simultaneous analysis

**Example:** Security review of a new feature — @CWP Architect analyzes code, @Outpost Architect analyzes infrastructure, @Security Guardian analyzes compliance — all in parallel.

---

## Context Isolation Mechanisms

Choose the right mechanism for the task:

- **Instruction passing** — Simple, well-defined subtasks. Maintains isolation; limits sub-agent flexibility.
- **File system memory** — Complex tasks requiring shared state. Transparent, debuggable; requires consistency management.
- **Full context delegation** — Sub-agent needs complete understanding. Maximum capability; defeats purpose of context isolation.

**IDEX default:** File system memory (docs/memory/tasks/name/, docs/temp/). Agents communicate through markdown files, not through supervisor rewrites.

---

## Failure Modes and Mitigations

**Supervisor bottleneck:** Supervisor context saturates; quality degrades.
Mitigation: Workers return distilled summaries; use file-based checkpointing.

**Coordination overhead:** Agent communication consumes more tokens than the task saves.
Mitigation: Minimize communication; batch results; use structured file formats.

**Divergence:** Agents pursue different goals without central coordination.
Mitigation: Define clear objective boundaries; implement convergence checks; use iteration limits.

**Error propagation:** Errors in one agent output cascade to downstream agents.
Mitigation: Validate agent outputs before passing to consumers; implement retry logic.

**Telephone game:** Supervisor paraphrases sub-agent responses incorrectly.
Mitigation: Let sub-agents write directly to shared files.

---

## IDEX Agent Delegation Decision Tree

Is the task within a single agent expertise?
- YES: Handle inline (no delegation needed)
- NO: Does it require multiple domains?
  - YES: Which pattern?
    - Sequential dependencies: Pattern 2 (Handoff)
    - Independent subtasks: Pattern 3 (Parallel)
    - Complex coordination: Pattern 1 (Supervisor)
  - NO: Is context window the bottleneck?
    - YES: Pattern 2 (Handoff with file-based memory)
    - NO: Handle inline

**IDEX tool mapping:**
- new_task: spawn independent sub-agent (Patterns 1, 2, 3)
- switch_mode: sequential consultation for simple questions (not full delegation)

---

## Memory Patterns for Multi-Agent

**Handoff files:** Agent A writes state, Agent B reads and continues.
Implementation: docs/memory/tasks/name/activeContext.md

**Result aggregation:** Multiple agents write to separate files, coordinator reads all.
Implementation: docs/temp/task-agent.md per agent

**Progress tracking:** Shared task list updated by all agents.
Implementation: docs/memory/tasks/name/progress.md

**Knowledge accumulation:** Agents append findings to shared knowledge files.
Implementation: docs/knowledge/domain/

**Rule:** Use the simplest memory mechanism that meets your needs. File-based memory is transparent, debuggable, and requires no infrastructure.

---

## Per-Agent Application Guide

**@Orchestrator:** Routing decisions: which pattern? which agents? avoid telephone game.

**@ProDex Agent:** Designing new delegation patterns; new_task vs switch_mode decisions.

**@Product Manager:** When to delegate to @CWP Architect (code analysis) vs @Security Guardian (risk).

**@Outpost/CWP/Platform Architects:** Parallel analysis: spawn sub-agents for independent domain analysis.

**@Security Guardian:** Coordinating multi-domain security reviews across architects.

**@Product QA:** When to delegate validation subtasks vs review inline.
