# Skill: Deliverable Quality Scoring

**Purpose:** Enable agents to score their own output against a rubric before delivering it — catching quality gaps before they reach the user  
**When to Use:** This skill should be used before calling attempt_completion on any quality-critical deliverable: PRDs, ADRs, knowledge docs, security reviews, skill files, release notes, or any output that will be published or acted upon. Use this skill whenever an agent wants to verify its output meets quality standards — even if the user does not explicitly ask for a quality check.  
**Owner:** @ProDex Agent  
**Created:** 2026-03-10  
**Version:** 1.0  
**Source:** Adapted from github/agentic-eval (Smithery) + IDEX REAR framework

---

> **Distinction from @Product QA:** @Product QA performs human-level strategic review of PRDs and specs — evaluating business fit, edge cases, and acceptance criteria quality. This skill adds automated pre-delivery scoring that any agent applies to its OWN output before claiming done. Self-scoring is a prerequisite; @Product QA review is a separate, higher-level gate.

---

## When to Apply

Apply this skill BEFORE attempt_completion when producing:

| Output Type | Minimum Score Required |
|---|---|
| PRD / Feature Spec | 0.8 |
| ADR / Architecture Doc | 0.8 |
| Security Review | 0.85 |
| Knowledge Doc | 0.75 |
| Skill File | 0.8 |
| Release Notes | 0.75 |
| Confluence Page | 0.75 |

---

## Standard Rubric

Score each dimension 1-5, then calculate weighted score:

| Dimension | Weight | What to Evaluate |
|---|---|---|
| **Accuracy** | 0.4 | Is the content factually correct? Are claims supported by evidence? Are there no hallucinations? |
| **Completeness** | 0.3 | Are all required sections present? Are edge cases addressed? Is nothing important missing? |
| **Clarity** | 0.3 | Is it understandable to the target audience? Is the structure logical? Is language precise? |

**Weighted score = (accuracy_score x 0.4 + completeness_score x 0.3 + clarity_score x 0.3) / 5**

**Threshold:** Score >= 0.8 = acceptable quality. Score < 0.8 = refine before delivering.

---

## Scoring Process

### Step 1: Define Criteria Before Generating

Before writing the deliverable, define what "good" looks like:

```
Criteria for this [PRD / ADR / etc.]:
- [ ] [Specific criterion 1]
- [ ] [Specific criterion 2]
- [ ] [Specific criterion 3]
```

Defining criteria BEFORE generating prevents post-hoc rationalization.

### Step 2: Score Against Rubric

After generating, score each dimension:

```
Accuracy (1-5): [score]
Evidence: [what supports this score]

Completeness (1-5): [score]
Evidence: [what supports this score]

Clarity (1-5): [score]
Evidence: [what supports this score]

Weighted score: [calculation]
```

### Step 3: Identify Failing Dimensions

If score < 0.8, identify which dimensions are below 3/5 and why.

### Step 4: Refine Only Failing Sections

Do NOT regenerate the entire output. Refine only the sections that caused the failing dimensions.

### Step 5: Re-score and Check Convergence

Re-score after refinement. If score does not improve by >= 0.05 between iterations, stop — further iteration is unlikely to help. Report the best version with remaining gaps noted.

**Max iterations:** 3 (prevent infinite loops)

---

## LLM-as-Judge (for High-Stakes Outputs)

For outputs that will be published to Confluence, presented to stakeholders, or used as the basis for engineering decisions, use a fresh-context evaluation:

1. Start a new context (or use a sub-agent via new_task)
2. Provide only the deliverable and the evaluation criteria — no generation context
3. Ask the judge to score and identify gaps
4. The judge has no bias from having generated the content

**When to use LLM-as-judge:**
- PRDs that will be published to Confluence
- ADRs that will be committed to the knowledge base
- Security reviews that will be acted upon by engineering

---

## Integration with REAR Framework

This skill extends the E (Evaluate) step of the REAR self-reflection cycle:

- **R (Review):** What was the task? What approach did I take?
- **E (Evaluate):** Apply this rubric. Score accuracy, completeness, clarity. (This skill)
- **A (Adapt):** Refine failing sections based on score
- **R (Report):** Document score and any remaining gaps in self-reflection

The REAR cycle's E step previously relied on qualitative judgment. This skill adds quantitative scoring to make evaluation more consistent and actionable.

---

## Per-Agent Application Guide

| Agent | When to Apply | Key Criteria |
|---|---|---|
| @Product Manager | Before publishing PRD to Confluence | Measurable success criteria, non-goals, user stories with AC |
| @Product QA | As structured review lens (not replacement for strategic judgment) | Completeness of acceptance criteria, edge case coverage |
| @ProDex Agent | Before deploying new skill files | Trigger description quality, content completeness, size discipline |
| @Outpost/CWP/Platform Architects | Before committing ADRs or knowledge docs | Technical accuracy, trade-off analysis, evidence citations |
| @Product Marketing | Before publishing release notes or blog posts | Accuracy of feature descriptions, clarity for target audience |
| @Security Guardian | Before delivering security reviews | Coverage of attack surface, severity accuracy, actionability |

---

## Quick Checklist

Before attempt_completion on a quality-critical deliverable:

- [ ] Scored against accuracy/completeness/clarity rubric
- [ ] Weighted score >= threshold for this output type
- [ ] If score < threshold: refined failing sections and re-scored
- [ ] If high-stakes: used LLM-as-judge with fresh context
- [ ] Remaining gaps (if any) noted in self-reflection
