# Skill: Prompt Engineering Patterns

**Purpose:** Design high-quality prompts for agent roleDefinitions, skill trigger descriptions, customInstructions, and LLM interactions  
**When to Use:** This skill should be used when designing agent system prompts, writing skill trigger descriptions, optimizing roleDefinition quality, debugging inconsistent agent behavior, or writing skill body instructions. Use this skill whenever an agent or skill needs to be created, improved, or debugged — even if the user doesn't explicitly ask for "prompt engineering."  
**Owner:** @ProDex Agent  
**Created:** 2026-03-10  
**Version:** 1.0  
**Source:** Adapted from `wshobson/prompt-engineering-patterns` (Smithery) + IDEX patterns

---

## Overview

Prompt engineering is the discipline of designing inputs to LLMs that reliably produce high-quality outputs. In IDEX, this applies to:

- **`roleDefinition`** in `.roomodes` — the system prompt that defines agent behavior
- **`customInstructions`** in `.roomodes` — task-specific behavioral rules
- **Skill trigger descriptions** — what causes an agent to load a skill
- **Skill body instructions** — how agents execute workflows

**Core principle:** Vague prompts produce inconsistent results. Specific, structured prompts produce reliable behavior.

---

## Pattern 1: System Prompt Design (roleDefinition)

A well-structured `roleDefinition` has four components in this order:

```
1. ROLE DECLARATION
   "You are [role] specializing in [domain]."
   → Be specific. "You are a Principal Product Manager" > "You are helpful"

2. CORE RESPONSIBILITIES (numbered list, implies priority order)
   "Your Core Responsibilities:
   1. [Primary responsibility]
   2. [Secondary responsibility]"

3. BEHAVIORAL CONSTRAINTS (reserve for non-negotiable rules only)
   "You MUST / NEVER / ALWAYS [constraint]"
   → Overuse dilutes impact. Max ~10 MUST/NEVER rules per agent.

4. OUTPUT FORMAT (define structure explicitly)
   "Provide results in this format: [template]"
   → Agents default to prose without explicit format guidance.
```

**Anti-patterns to avoid:**
- ❌ "Be helpful and accurate" — too vague, no behavioral guidance
- ❌ 20+ MUST/NEVER rules — agents ignore rules past ~10
- ❌ First-person ("I will...") — use second-person ("You are...")
- ❌ Contradictory constraints — agents pick one arbitrarily

---

## Pattern 2: Trigger Description Design (Skill Descriptions)

Skill trigger descriptions determine when an agent loads a skill. Research shows agents **undertrigger** — they don't load skills when they should. The fix is "pushy third-person" format.

**Recommended format:**
```
This skill should be used when the user asks to "[exact phrase 1]", 
"[exact phrase 2]", "[exact phrase 3]", or mentions [concept]. 
Make sure to use this skill whenever [broader trigger condition], 
even if the user doesn't explicitly ask for it.
```

**Good trigger description (IDEX example):**
```
This skill should be used when the user asks to "create a PRD", 
"write product requirements", "document a feature", or mentions 
"user stories", "acceptance criteria", or "product spec". 
Use this skill whenever a new feature needs formal documentation, 
even if the user just says "let's plan this feature".
```

**Bad trigger description:**
```
Use this skill for PRD creation.  ← Too vague, no specific phrases
```

**Coverage checklist for trigger descriptions:**
- [ ] Includes 3-5 specific user phrases in quotes
- [ ] Includes broader concept triggers (not just exact phrases)
- [ ] Uses third-person ("This skill should be used when...")
- [ ] Has a "even if not explicitly asked" clause for proactive triggering
- [ ] Avoids overlap with other skills' triggers

**Scope guard:** Add "Do NOT trigger for [adjacent context]" when a skill might conflict with another.

---

## Pattern 3: Few-Shot Examples in Instructions

When agents need to produce a specific format, examples outperform descriptions.

**Format:**
```markdown
## Output Format

ALWAYS use this exact structure:

**Example:**
Input: [sample input]
Output:
[exact output format with all required fields]
```

**When to use few-shot:**
- Output has a rigid structure (tables, JSON, specific markdown)
- The format is non-obvious from description alone
- Agents consistently produce wrong format despite instructions

**When NOT to use few-shot:**
- Simple, obvious formats (bullet lists, paragraphs)
- When examples would consume too much context window
- When the task is highly variable (examples may over-constrain)

---

## Pattern 4: Chain-of-Thought for Complex Reasoning

For tasks requiring multi-step reasoning, instruct the agent to show its work.

**Template:**
```
Before providing your answer:
1. Identify the key constraints and requirements
2. Consider 2-3 alternative approaches
3. Evaluate trade-offs for each approach
4. Select the best approach and explain why
5. Then provide your recommendation

Format:
## Analysis
[steps 1-4]

## Recommendation
[step 5]
```

**IDEX applications:**
- Architecture decisions (ADRs) — always use CoT
- Security risk assessments — show reasoning chain
- Feature prioritization — explicit trade-off analysis
- Compliance determinations — cite evidence at each step

---

## Pattern 5: Structured Output Enforcement

When agents must produce parseable output (JSON, YAML, tables), enforce structure explicitly.

**Techniques:**
1. **Schema in prompt:** Include the exact JSON schema or table headers
2. **Example output:** Show a complete filled-in example
3. **Validation instruction:** "If your output doesn't match this schema, revise before responding"
4. **Error recovery:** "If you cannot determine a value, use `null` — never omit the field"

**IDEX application — memory updates:**
```
Update activeContext.md with this exact structure:
## Task Summary
[1-2 sentences]

## Key Decisions
- [decision 1]

## 🪞 Self-Reflection
[REAR cycle output]
```

---

## Token Efficiency

Concise prompts reduce cost and improve focus.

| Bloated | Concise | Savings |
|---|---|---|
| "I would like you to please take the following text and provide me with a comprehensive summary..." | "Summarize key points:" | ~80% |
| "You must always remember to never forget to..." | "Always [rule]." | ~60% |
| Repeating the same constraint 3 ways | State it once, clearly | ~50% |

**Prompt caching (Anthropic):** For long system prompts repeated across many calls, use `cache_control: ephemeral` on the system prompt block. Reduces cost by ~90% on cached tokens.

---

## Debugging Inconsistent Agent Behavior

When an agent produces inconsistent outputs:

1. **Check trigger description** — is the skill loading when expected?
2. **Check constraint count** — more than 10 MUST/NEVER rules? Trim to top 5
3. **Check for contradictions** — do any rules conflict?
4. **Add few-shot examples** — if format is wrong, show the right format
5. **Add CoT instruction** — if reasoning is wrong, make the agent show its work
6. **Check context window** — is the roleDefinition too long? (>2000 tokens = risk)

---

## IDEX-Specific Applications

| Task | Pattern to Apply |
|---|---|
| Writing a new agent `roleDefinition` | Pattern 1 (System Prompt Design) |
| Writing a skill trigger description | Pattern 2 (Pushy Third-Person) |
| Defining skill output format | Pattern 3 (Few-Shot Examples) |
| Writing ADR or security review skill | Pattern 4 (Chain-of-Thought) |
| Writing memory update instructions | Pattern 5 (Structured Output) |
| Agent produces wrong format consistently | Pattern 3 + Pattern 5 combined |
| Agent undertriggers (doesn't load skill) | Pattern 2 (add "even if not explicitly asked") |
