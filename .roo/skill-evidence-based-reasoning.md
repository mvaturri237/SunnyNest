# Skill: Evidence-Based Reasoning

**Version:** 1.0.0
**Applies to:** All agents producing architectural claims, capability analyses, ADRs, service catalog entries, security findings
**Adopted from:** EasyPlatform ClaudeKit `shared/evidence-based-reasoning-protocol.md` (2026-03-07)

---

## Core Requirement

Every architectural claim MUST be backed by a specific source reference. This is an *output standard*, not a process protocol — it governs what you write, not how you think.

This complements Section 8.5 (Zero-Trust Execution), which governs the reasoning process. Both apply independently.

---

## Citation Format

Use the appropriate format for the source type:

| Source Type | Format | Example |
|-------------|--------|---------|
| Code | `repos/<service>/path/to/file.go:142` | `repos/cwp_vulnerability_analyzer/transport/grpc_server.go:89` |
| Config | `repos/<service>/config/settings.yaml:23` | `repos/cwp_scan_orchestrator/config/defaults.yaml:15` |
| Knowledge doc | `[Source: docs/knowledge/cwp/scanner_analysis.md, Last Updated: 2026-02-14]` | |
| Confluence | `[Source: Confluence page "Scanner Architecture", ID: 123456]` | |
| Jira | `[Source: PROJ-1234 — requirement stated in description]` | |
| Current session decision | `[Decided in this session — see decision log]` | |

Line numbers are approximate guides, not exact requirements. Cite the nearest relevant line.

---

## What Requires a Citation

- Any capability claim ("The service supports X")
- Any architectural assertion ("The system uses Y pattern")
- Any performance/scale claim ("Handles Z requests/sec")
- Any security claim ("Data is encrypted at rest")
- Any "does not exist" claim ("There is no rate limiting")
- Any dependency claim ("Service A calls Service B")

---

## What Does NOT Require a Citation

- General industry knowledge ("REST APIs use HTTP verbs")
- User-provided requirements (cite the user's message)
- Decisions made in the current session (cite the decision log)
- Widely-known framework behavior ("React re-renders on state change")

---

## Verification Standard

Before stating a claim, ask: **"Can I point to the exact line of code, config, or document that proves this?"**

- **Yes** → state the claim with citation
- **No** → do NOT state the claim. Instead write: *"I could not find evidence of X — further investigation needed."*

Never state a claim as fact when you cannot cite a source. Uncertainty is acceptable; uncited assertions are not.

---

## For Agents Without Repo Access

If you cannot access `repos/` directly, cite the knowledge doc that contains the information:
```
[Source: docs/knowledge/cwp/vulnerability_analyzer_architecture.md, Last Updated: 2026-03-08]
```
If the knowledge doc itself is stale (🔴 Expired), note this in your output.
