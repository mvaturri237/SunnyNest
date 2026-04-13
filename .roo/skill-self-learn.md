# Skill: Self-Learn — Continuous Improvement Loop

## Purpose
Enable agents to propose improvements to their own skills and rules based on lessons learned during chat sessions. All proposals require explicit user approval before being applied.

## When to Use
At the END of every chat session (after completing the user's task), the agent should evaluate whether it learned something that could improve future performance.

## How It Works

### The Self-Learn Loop
1. DETECT — During the session, notice patterns, mistakes, or missing knowledge
2. DRAFT — Write a specific, concrete improvement proposal
3. PROPOSE — Present the proposal to the user with a clear diff
4. WAIT — Do NOT apply changes until the user explicitly approves
5. APPLY — If approved, make the change and confirm

### What Triggers a Proposal

| Trigger | Example | Proposed Change |
|---------|---------|-----------------|
| Repeated mistake | Agent kept forgetting to check rate limits | Add rate limit check to skill-data-scraping.md |
| Missing knowledge | Agent didn't know the project uses Tailwind | Add "Tech stack: Tailwind CSS" to rules/shared.md |
| New pattern discovered | Found a better way to handle map clustering | Add clustering pattern to skill-map-ui.md |
| User correction | User said "we always use TypeScript, not JavaScript" | Add "Language: TypeScript (strict mode)" to rules/shared.md |
| Workflow improvement | Realized tests should run before every commit | Add pre-commit test rule to rules/shared.md |
| Missing edge case | Didn't handle the case where a listing has no images | Add "no-image fallback" to skill-code-review.md checklist |

### What Does NOT Trigger a Proposal
- One-off task-specific details (not reusable)
- User preferences that are already documented
- Temporary workarounds (not permanent improvements)
- Changes the agent is uncertain about (when in doubt, don't propose)

## Proposal Format

At the end of a session, if the agent has a learning to propose, present it like this:

---

### Improvement Proposal

**What I learned:** [1-2 sentence description of the insight]

**Why it matters:** [How this will prevent future mistakes or improve quality]

**Proposed change:**

File: [.roo/skill-xxx.md or .roo/rules/shared.md]

Section: [which section to update]

Add the following:
[exact text to add — be specific, not vague]

**Impact:** [Low/Medium/High] — affects [which agent(s)]

Type **"approve"** to apply this change, or **"skip"** to ignore it.

---

## Rules for Proposals

### DO
- Be specific: propose exact text to add, not vague suggestions
- Be minimal: one small, focused change per proposal
- Be confident: only propose changes you're sure about
- Show the exact file and section that would change
- Explain WHY the change helps (not just WHAT it is)
- Limit to 1-2 proposals per session (don't overwhelm the user)

### DON'T
- Never apply changes without explicit user approval
- Never propose removing existing content (only additions or modifications)
- Never propose changes to files outside .roo/ directory
- Never propose changes based on a single occurrence (wait for a pattern)
- Never propose vague improvements like "be more careful" — be specific
- Never batch more than 2 proposals in one message

## Tracking Proposals

### Accepted Proposals Log
When a proposal is approved and applied, append a one-line entry to the bottom of the modified skill/rule file:

[YYYY-MM-DD] Self-learn: [brief description of what was added]

This creates an audit trail of how skills evolve over time.

### Rejected Proposals
If the user rejects a proposal, do NOT re-propose the same change in future sessions. Remember the rejection in the session context.

## Integration with Agents

Add this line to any agent's customInstructions in .roomodes:

At session end, follow .roo/skill-self-learn.md to evaluate if you learned something worth proposing as a skill or rule improvement.

## Examples

### Example 1: User Correction
During session, user says: "We use Supabase for our database, not PostgreSQL directly."

Proposal:
- File: .roo/rules/shared.md
- Add to Project Context section:
  "Database: Supabase (PostgreSQL-based, use Supabase client SDK, not raw SQL)"

### Example 2: Discovered Pattern
Agent noticed that every listing card component needs a "source badge" (Zillow/Craigslist).

Proposal:
- File: .roo/skill-frontend-design.md
- Add to Component Patterns section:
  "Source Badge: Every listing card must show the data source (Zillow, Craigslist, etc.) as a colored badge in the top-left corner. Use brand colors: Zillow=#006AFF, Craigslist=#5A0096"

### Example 3: Missing Edge Case
Agent forgot to handle listings with no price (some Craigslist listings say "contact for price").

Proposal:
- File: .roo/skill-data-scraping.md
- Add to Common Data Model section:
  "Price field: nullable. When source has no price, set price=null and display 'Contact for Price' in the UI. Never default to 0."
