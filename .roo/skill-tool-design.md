# Skill: Tool Architecture & Design

## Purpose
Guide Architect when designing custom tool APIs, parameter schemas, error handling, and test strategies for IDEX custom tools. Tools are TypeScript files that act as deterministic APIs.

## When to Use
- Designing a new custom tool from scratch
- Planning modifications to an existing tool's API surface
- Reviewing a tool change request from ProDex Agent
- Defining test strategy for a tool before implementation

## Design Principles

### 1. Tools Are APIs
- **Parameter names:** Clear, descriptive, consistent with existing tools
- **Enums:** Every enum value MUST have a corresponding handler case
- **Required vs optional:** Minimize required params; use sensible defaults
- **Error responses:** Descriptive messages with context (what failed, why, how to fix)

### 2. Architecture Standards
- **Single Responsibility:** One tool = one domain
- **Fail Fast:** Validate inputs immediately, return clear errors before doing work
- **Loose Coupling:** Tools should not depend on other tools' internals
- **Idempotency:** Where possible, same input produces same output
- **Dependency Injection:** Accept paths/configs as params, don't hardcode

### 3. Security by Design
- **Path validation:** Tools handling file paths MUST validate against workspace root
- **Command sanitization:** Shell-executing tools MUST whitelist allowed commands
- **No secrets in code:** Credentials come from `.env` files, never hardcoded
- **Least privilege:** Tools should request minimum permissions needed

## Design Workflow

### Step 1: Define the Problem
- What operation does the user/agent need?
- What existing tools overlap? Can we extend instead of creating new?
- What is the minimal API surface that solves the problem?

### Step 2: Design the Schema
**Checklist:**
- [ ] Every enum value has a handler in the switch statement
- [ ] Parameter names are self-documenting
- [ ] Types are correct (string for paths, number for counts)
- [ ] Optional params have documented defaults
- [ ] Description field explains what the tool does

### Step 3: Design Error Handling
| Error Type | Response Pattern |
|-----------|-----------------|
| Invalid input | `ERROR: <param> is invalid. Expected: <format>` |
| File not found | `ERROR: File not found: <path>.` |
| Permission denied | `BLOCKED: <operation> not allowed on <target>.` |
| External failure | `ERROR: <service> failed. Retry or check connectivity.` |
| Unexpected | `ERROR: Unexpected error in <operation>: <message>` |

### Step 4: Design Test Strategy
| Test Category | Coverage Target | Example |
|--------------|----------------|---------|
| **Happy path** | Every operation | Valid input produces expected output |
| **Input validation** | Every required param | Missing param produces clear error |
| **Error paths** | Every error type | Invalid path produces File not found |
| **Edge cases** | Boundary values | Empty string, very long input, special chars |
| **Security** | Every constraint | Path traversal attempt is blocked |

**Test naming:** `describe('ToolName') > describe('operation') > it('should behavior')`

### Step 5: Document the Design
Produce a design document in `docs/plans/tool-<name>-design.md` with: Purpose, Operations, Schema, Error Handling, Test Plan, Breaking Changes.

**Validate:** ProDex Agent reviews and approves before Code Agent implements.

## Roo Code Tool Constraints
- **Runtime:** Node.js (esbuild-wasm, target node18)
- **Output:** Must return string
- **No ESM-only packages:** require() must work (CommonJS compat)
- **Shim:** @roo-code/types must exist in node_modules/
- **Auto-approved:** No user confirmation needed, so security is critical

## Anti-Patterns
- **No kitchen sink tools:** Don't add operations just in case (YAGNI)
- **No implicit dependencies:** Document all package requirements
- **No breaking changes without version bump:** Changing enum values breaks callers
- **No design without test plan:** Every design must include what to test

## Quality Checks
- [ ] Every enum value maps to a handler (no orphans)
- [ ] Error messages include context (what, why, how to fix)
- [ ] Test strategy covers happy path, errors, edge cases, security
- [ ] Design document exists in docs/plans/ before implementation
- [ ] Breaking changes are identified and documented
