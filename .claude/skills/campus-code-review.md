---
name: campus-code-review
description: 13-category pre-commit code review — auth, RBAC, input validation, SQL injection, rate limiting, race conditions, XSS
model: claude-sonnet-4-6
tools: [Read, Grep, Glob, codegraph_search, codegraph_callers, codegraph_context, codegraph_explore]
---

# Campus Code Review

## Core Behavior

- **If unsure, say so** — don't guess about code patterns. Read the actual code.
- **Read before reviewing** — always Read the target files before marking categories PASS/FAIL.
- **Check both backends** — Python and Go may have diverged on the same feature.
- **Don't skip small changes** — one-liners cause the worst bugs.
- **Prefer reading over guessing** — function signatures, decorators, and import paths change.

## Trigger
When user says: "review this", "check my code", "review", "code review", "is this correct", before committing code

## Process

Run through ALL 13 categories below. If ANY category fails, the review verdict is CHANGES NEEDED.

### 1. Authentication (AUTH)
- [ ] New endpoint has `user: dict = Depends(get_current_user)`?
- [ ] Public endpoints are truly read-only and non-sensitive? (only `/api/health`, `/api/version`)
- [ ] `get_current_user` checks `is_active` before returning the user?
- [ ] Auth exceptions return 401 (not 403 or 500)?
- [ ] Go backend checks role from DB each request (not just from JWT claims)?

**Check command**: `rg -n "async def " f:/ClaudeFiles/campus_app/server/main_remote.py | rg -v "get_current_user|Depends"`

### 2. Authorization (RBAC)
- [ ] Uses `require_role(*roles)` for admin functions?
- [ ] Activity-modifying endpoints call `_can_manage_act()`?
- [ ] `created_by == user["id"]` checked before modifying owned resources?
- [ ] `college_admin` restricted to own college scope?
- [ ] Role assignment: college_admin cannot set school_admin?
- [ ] Publisher code revocation checks `created_by=$2`?

### 3. Input Validation
- [ ] Pydantic `BaseModel` with `Field(min_length=..., max_length=...)` used — not raw `dict = Body(...)`?
- [ ] All string inputs bounded by `max_length`?
- [ ] All numeric inputs bounded by `ge=` and `le=`?
- [ ] File uploads validated by content-type (MIME), not extension?
- [ ] File uploads size-limited to 10MB?
- [ ] Regex patterns checked for ReDoS (no nested quantifiers)?
- [ ] Student ID validated as 9-digit where appropriate?

### 4. SQL Injection
- [ ] All queries use parameterized `$1, $2, $3` syntax?
- [ ] No `f"SELECT ... {variable}"` anywhere?
- [ ] Dynamic column names in UPDATE come from Pydantic model keys, not user input?
- [ ] ORDER BY / LIMIT values parameterized (not concatenated)?

**Check command**: `rg -n 'f".*SELECT.*{' f:/ClaudeFiles/campus_app/server/`

### 5. Output / Data Exposure
- [ ] No `SELECT *` in user-facing endpoints — columns specified explicitly?
- [ ] Password hash, refresh token hash excluded from response?
- [ ] Phone/QQ gated behind `show_phone`/`show_qq` privacy flags?
- [ ] CSV export uses `_csv_escape()` on every cell?
- [ ] Feedback endpoint does not expose real `user_id`?
- [ ] Error responses generic (no internal paths, no Pydantic field-level details)?

### 6. Rate Limiting
- [ ] Login: `@limiter.limit("5/minute")`?
- [ ] Register: `@limiter.limit("5/hour")`?
- [ ] Password reset: `@limiter.limit("3/minute")`?
- [ ] Messages: `@limiter.limit("60/hour")`?
- [ ] Any new POST/PUT/DELETE has rate limiting?

### 7. Error Handling
- [ ] Exceptions caught log the error (no bare `except: pass`)?
- [ ] Validation errors return generic message (not field-level)?
- [ ] 404 for missing resources (not 500 or 200 with empty body)?
- [ ] 403 for authorization failure (not 401 triggering re-login)?
- [ ] Rate limit exceeded returns 429 (not 500)?
- [ ] DB errors return "system busy" (not crash dump)?

### 8. Audit Logging
- [ ] Security-sensitive actions logged: role change, password reset, activity completion, signup approval, publish code creation/revocation?
- [ ] Format: `AUDIT: action={action} by={user['id']} target={target_id} time=...`?

### 9. Race Conditions
- [ ] Concurrent writes protected by `FOR UPDATE` in transaction?
- [ ] Signup with `max_participants` check has `FOR UPDATE` on activity row?
- [ ] Refresh token rotation has `SELECT ... FOR UPDATE` inside transaction?
- [ ] Substitute operation has `FOR UPDATE` on both signup rows?
- [ ] Pattern: `async with pool.acquire() as conn: async with conn.transaction(): await conn.fetchrow("SELECT ... FOR UPDATE", ...)`

### 10. XSS / Injection
- [ ] Title scanned for impersonation prefixes (`【系统】`, `【官方】`, `【教务】`, `【学工】`, `【学生】`, `【财务】`, `【学校】`)?
- [ ] Notice content scanned for bare URLs without context keywords?
- [ ] Activity creation has same impersonation check?
- [ ] CSP headers set in nginx? (`script-src 'self'`)

### 11. Password & Token
- [ ] Passwords hashed with bcrypt (not MD5, SHA-1, or plaintext)?
- [ ] Minimum password length 6?
- [ ] JWT secret from `os.environ`, not hardcoded?
- [ ] JWT expiry <= 1 hour?
- [ ] Refresh token stored as SHA-256 hash (not plaintext)?
- [ ] Refresh token rotated on each use?

### 12. Dependencies
- [ ] New dependencies added in this change? Check CVEs: `pip-audit`
- [ ] Go dependency added? Check: `go list -u -m all`

### 13. Flutter-Specific
- [ ] `mounted` checked before `setState`?
- [ ] `dispose` calls `super.dispose()`?
- [ ] Streams/subscriptions cancelled in `dispose`?
- [ ] No `BuildContext` used across async gaps without checking `mounted`?

## Review Outcome Template
```
## Code Review: {commit/feature name}

Auth: {PASS|FAIL} — {details}
AuthZ: {PASS|FAIL} — {details}
Input: {PASS|FAIL} — {details}
Output: {PASS|FAIL} — {details}
DB: {PASS|FAIL} — {details}
Errors: {PASS|FAIL} — {details}
Logging: {PASS|FAIL} — {details}
Rate Limit: {PASS|FAIL} — {details}
Race: {PASS|FAIL} — {details}

Verdict: {APPROVED / CHANGES NEEDED / BLOCKED}
```

## References
- `f:\ClaudeFiles\docs\CODE_REVIEW.md` — full checklist with code examples
- `f:\ClaudeFiles\docs\SECURITY_KB.md` — 15 vulnerability categories with exploit paths
- `f:\ClaudeFiles\.claude\skills\campus-security-audit.md` — deeper security checks
- `f:\ClaudeFiles\.semgrep\python.yml` — automated SAST rules that catch common antipatterns

## Anti-patterns
- DO NOT skip review on "small changes" — one-liners cause the worst bugs
- DO NOT accept code that passes the "happy path" only — check error paths
- DO NOT approve without checking BOTH backends — Python and Go may diverge
- DO NOT leave review comments without actionable fixes
- DO NOT approve code that adds new endpoints without rate limits
