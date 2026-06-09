# Code Review Checklist — 校园即时通

Use this checklist for every code change. Each item maps to a real vulnerability class in `SECURITY_KB.md`.

## 1. Authentication (AUTH)

- [ ] Every new endpoint has `user: dict = Depends(get_current_user)`?
- [ ] If the endpoint should be public — is it truly read-only and non-sensitive? (like `/api/health` or `/api/version`)
- [ ] `get_current_user` checks `is_active` before returning the user?
- [ ] Auth exception raised with 401 status (not 403 or 500)?
- [ ] Token validation catches both expired and malformed tokens?

```python
# Correct pattern:
@app.get("/api/new-endpoint")
async def new_endpoint(user: dict = Depends(get_current_user)):
    if user["role"] not in ("teacher", "school_admin"):
        raise HTTPException(403, "权限不足")
    return {"data": "sensitive"}
```

## 2. Authorization (RBAC)

- [ ] Uses `require_role(*roles)` decorator for admin functions?
- [ ] Uses `_can_manage_act()` for activity-level access?
- [ ] Checks `created_by == user["id"]` before modifying resources?
- [ ] `college_admin` restricted to own college scope?
- [ ] Role assignment endpoint checks hierarchy — college_admin cannot set school_admin?
- [ ] Publisher code revocation checks `created_by=$2` (only code creator can revoke)?

```python
# Role hierarchy check (must be in set-role endpoint)
if user["role"] == "college_admin" and req.role not in ("student", "teacher", "publisher"):
    raise HTTPException(403)
if req.role in ("college_admin", "school_admin") and user["role"] != "school_admin":
    raise HTTPException(403)
```

## 3. Input Validation

- [ ] Pydantic model with `Field(min_length=..., max_length=...)` used instead of raw `dict = Body(...)`?
- [ ] All string inputs bounded by max_length?
- [ ] All numeric inputs bounded by `ge=` and `le=`?
- [ ] File uploads validated by content-type (not extension)?
- [ ] File uploads size-limited?
- [ ] Regular expressions checked for ReDoS (no nested quantifiers)?
- [ ] Integer IDs cast to `int` before DB query?
- [ ] Student ID validated as 9-digit for student role?

```python
# Good — Pydantic model with constraints
class ActivityCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)
    max_participants: int = Field(default=0, ge=0)

# Bad — raw dict, no validation
@app.post("/api/endpoint")
async def bad_endpoint(req: dict = Body(...)):
    title = req.get("title")  # may be None, may be 10MB string
```

## 4. SQL Injection

- [ ] All queries use parameterized `$1, $2, $3` syntax?
- [ ] No f-string `f"SELECT ... {variable}"` anywhere in db.py or main.py?
- [ ] Dynamic column names in `UPDATE` come from Pydantic model keys, not user input?
- [ ] `ORDER BY` and `LIMIT` values parameterized (not concatenated)?
- [ ] Pattern: `await pool.execute("SQL $1", value)` — never `await pool.execute(f"SQL {value}")`

```python
# CORRECT — parameterized
await pool.execute("UPDATE users SET password_hash=$1 WHERE id=$2", new_hash, user_id)

# WRONG — injection risk
await pool.execute(f"UPDATE users SET password_hash='{new_hash}' WHERE id={user_id}")
```

## 5. Output / Data Exposure

- [ ] `SELECT *` avoided in user-facing endpoints (specify columns explicitly)?
- [ ] Password hash, refresh token hash, and other secrets excluded from response?
- [ ] Phone/QQ data gated behind `show_phone`/`show_qq` privacy flags?
- [ ] CSV export escapes formula injection characters (`=`, `+`, `-`, `@`)?
- [ ] Feedback endpoint does not expose real `user_id` in response?
- [ ] Error responses generic (no internal paths, no field-level validation details)?

```python
# CORRECT — explicit columns
user = await pool.fetchrow("SELECT id, name, role FROM users WHERE id=$1", uid)

# WRONG — may expose password_hash, refresh_token_hash
user = await pool.fetchrow("SELECT * FROM users WHERE id=$1", uid)
```

## 6. Rate Limiting

- [ ] Login endpoint has `@limiter.limit("5/minute")`?
- [ ] Registration endpoint has `@limiter.limit("5/hour")`?
- [ ] Password reset has `@limiter.limit("3/minute")`?
- [ ] Message sending has `@limiter.limit("60/hour")`?
- [ ] Any new POST/PUT/DELETE endpoint has rate limiting?
- [ ] nginx `limit_req` zones added for new endpoints that accept file uploads?

## 7. Error Handling

- [ ] Exceptions caught in `try/except` log the error (not silently swallow)?
- [ ] Validation errors return generic message (not field-level details)?
- [ ] 404 raised for missing resources (not 500 or 200 with empty body)?
- [ ] 403 for authorization failure (not 401 which triggers re-login)?
- [ ] Rate limit exceeded returns 429 (not 500)?
- [ ] DB connection errors return "service degraded" (not crash dump)?

```python
# CORRECT — generic error
except Exception as e:
    logger.error(f"auto_process error: {e}")  # log real error
    # return generic message to user
    raise HTTPException(500, "系统繁忙")

# WRONG — stack trace leak
except Exception:
    raise  # FastAPI will render full traceback
```

## 8. Audit Logging

- [ ] Security-sensitive actions logged to `audit_logger`?
- [ ] Actions that MUST be logged: role change, password reset (both self and admin), activity completion (for hours), signup approval, publish code creation/revocation
- [ ] Audit log includes: who did it, what they did, when, target ID?
- [ ] Actions that COULD be logged: login failure, rate limit hit

```python
# Log pattern
audit_logger.info(f"AUDIT: action={action} by={user['id']} target={target_id} time={datetime.now().isoformat()}")
```

## 9. Race Conditions

- [ ] Concurrent writes protected by `FOR UPDATE` in transaction?
- [ ] Signup with max_participants check has `FOR UPDATE` on activity row?
- [ ] Refresh token rotation has `SELECT ... FOR UPDATE` inside transaction?
- [ ] Substitute student operation has `FOR UPDATE` on both signup rows?
- [ ] Pattern:

```python
async with pool.acquire() as conn:
    async with conn.transaction():
        row = await conn.fetchrow("SELECT ... FOR UPDATE", ...)
        # read and write within the transaction
```

## 10. XSS / Injection Prevention

- [ ] Title/description content scanned for impersonation prefixes (`【系统】`, `【官方】`, etc.)?
- [ ] Notice content scanned for bare URLs without context keywords?
- [ ] Activity creation has same impersonation check as notices?
- [ ] All user-submitted text either escaped on output or filtered on input?
- [ ] CSP headers set in nginx (`script-src 'self'`)?

## 11. Password & Token Security

- [ ] Passwords hashed with bcrypt (not MD5, SHA-1, or plaintext)?
- [ ] Minimum password length 6 characters?
- [ ] JWT secret from `os.environ`, not hardcoded?
- [ ] JWT expiry ≤1 hour?
- [ ] Refresh token stored as SHA-256 hash, never plaintext?
- [ ] Refresh token rotated on each use (new token invalidates old)?
- [ ] Server crashes at startup if `JWT_SECRET` missing?

## 12. Dependency & Supply Chain

- [ ] New dependencies added? Check CVEs first: `pip-audit`, `gitleaks detect`
- [ ] Known vulnerabilities in existing deps? (`flutter_secure_storage` CVE)
- [ ] New Python package? Check `pip show` for maintainer, downloads
- [ ] New Dart package? Check pub.dev score, popularity

## 13. Deployment & Config

- [ ] Secrets (`DB_PASSWORD`, `JWT_SECRET`) in `.env`, not in code?
- [ ] `.env` in `.gitignore` (never committed)?
- [ ] nginx config: `server_tokens off`, security headers present?
- [ ] ufw enabled with only 22/80/443 open?
- [ ] fail2ban enabled for SSH and nginx?
- [ ] Redis bound to 127.0.0.1 only?

## Quick Ref: Common Anti-patterns

| Anti-pattern | Fix | KB Ref |
|---|---|---|
| `f"SELECT ... {var}"` | `SELECT ... $1`, var | KB-1 |
| `SELECT * FROM users` | Select specific columns | KB-6 |
| `dict = Body(...)` w/o model | Pydantic `BaseModel` with `Field()` | KB-3 |
| No `Depends(get_current_user)` | Add auth dependency | KB-12 |
| `except: pass` | Log and raise | KB-7 |
| No rate limit on auth | `@limiter.limit(...)` | KB-4 |
| `csv += f"...{val}..."` | `csv += f"...{_csv_escape(val)}..."` | KB-15 |
| Title includes `【系统】` | Block impersonation prefixes | KB-13 |
| Plaintext password storage | `bcrypt.hashpw()` | KB-9 |
| No `FOR UPDATE` on concurrent write | Wrap in transaction + `FOR UPDATE` | KB-8 |

## Review Outcome Template

```
## Code Review: {PR/commit description}

### Auth: ✅ / ❌ — {comments}
### Input: ✅ / ❌ — {comments}
### Output: ✅ / ❌ — {comments}
### DB: ✅ / ❌ — {comments}
### Errors: ✅ / ❌ — {comments}
### Logging: ✅ / ❌ — {comments}
### Rate Limit: ✅ / ❌ — {comments}
### Race: ✅ / ❌ — {comments}

### Verdict: {APPROVED / CHANGES NEEDED / BLOCKED}
```
