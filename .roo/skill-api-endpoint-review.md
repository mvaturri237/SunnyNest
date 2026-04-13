# Skill: API Endpoint Review

## Purpose
Systematically review an API endpoint for correctness, security, and best practices.

## When to Use
When asked to "review an API endpoint", "check my API", or "API review".

## Checklist
For each endpoint, evaluate:

### 1. HTTP Method & URL
- Correct HTTP verb (GET for reads, POST for creates, PUT/PATCH for updates, DELETE for deletes)
- RESTful URL structure (nouns, not verbs: /users/{id} not /getUser)
- Consistent naming convention

### 2. Input Validation
- All user inputs are validated (type, length, format)
- Required vs optional parameters are clearly defined
- Request body schema is documented

### 3. Authentication & Authorization
- Endpoint requires authentication (unless intentionally public)
- Authorization checks exist (user can only access their own resources)
- API keys/tokens are not logged or exposed in URLs

### 4. Error Handling
- Returns appropriate HTTP status codes (400, 401, 403, 404, 500)
- Error responses include a message but no stack traces
- Handles edge cases (empty input, duplicate entries, not found)

### 5. Response Format
- Consistent JSON structure across all endpoints
- Pagination for list endpoints
- No sensitive data leaked in responses (passwords, tokens, internal IDs)

## Output Format
Present findings as:

API Review: [METHOD] [URL]
- Passed: [list what is good]
- Warnings: [list minor issues]
- Failed: [list critical issues]
- Recommendations: [numbered list of specific fixes]
