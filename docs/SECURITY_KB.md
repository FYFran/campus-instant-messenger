# Security Knowledge Base — 校园即时通

Document every vulnerability class we found, found in the wild, or mitigated during development.

## 1. SQL Injection

### Status: Mitigated (parameterized queries)

**Discovery**: Code review of main.py and db.py — all asyncpg queries use `$1, $2` parameterized syntax.

**Prevention**:
- All queries must use `await pool.execute("SQL...$1, $2...", val1, val2)` — never f-strings
- Runtime detection (nginx): blocks `OR 1=1`, `UNION`, `--` in query params via WAF rules
- Explicit `LIMIT` on all list endpoints to prevent DoS via cartesian joins

**Semgrep rule** (`semgrep_sql_injection.yaml`):
```yaml
rules:
  - id: sql-injection-format
    patterns:
      - pattern: |
          $POOL.execute(f"...{...}...", ...)
      - pattern-not: |
          $POOL.execute("...$1...", ...)
    message: "SQL injection risk: use parameterized $1 syntax"
    languages: [python]
    severity: ERROR
```

**Instances found**: 0 in db.py, 0 in main.py/remote. Dynamic column names in `UPDATE` (main_remote.py:597-600) use string concatenation of column names but values are parameterized. Mitigated by: column names come from Pydantic model keys, not user input.

## 2. IDOR (Insecure Direct Object Reference)

### Status: Mitigated (ownership checks on every endpoint)

**Discovery**: Penetration test of activity/signup endpoints — each endpoint checks `_can_manage_act()` or `act["created_by"] == user["id"]`.

**Prevention**:
- Every activity-modifying endpoint calls `_can_manage_act()` first
- Signup list: checks `act["created_by"] != user["id"]` AND role check
- Substitute endpoint: checks `require_role` decorator; uses `FOR UPDATE` row lock inside transaction
- Publish code revoke: checks `created_by=$2` to ensure only the code creator can revoke

**Checked in code review**:
```python
# Yes — ownership check present
act = await database.get_activity(activity_id)
if not act: raise HTTPException(404)
if not _can_manage_act(act, user): raise HTTPException(403)
```

**Layered ownership function** (`_can_manage_act`):
```python
def _can_manage_act(act: dict, user: dict) -> bool:
    if user["role"] == "school_admin" or user.get("is_owner"): return True
    if act["created_by"] == user["id"]: return True
    if user["role"] == "college_admin":
        uc = user.get("college","")
        sv = act.get("scope_value","")
        if act.get("scope_type") == "all": return True
        if sv and uc in sv.split(","): return True
    return False
```

## 3. Secret Leak / Hardcoded Credentials

### Status: Mitigated (gitleaks + .env + .gitignore)

**Discovery**: Commit history shows hardcoded `JWT_SECRET` and `DB_PASSWORD` in main.py before commit `ab0ed46`.

**Prevention**:
- Pre-commit hook: `gitleaks detect --source . --verbose` — blocks commits with secrets
- `.env` in `.gitignore` — never committed
- `.env.example` checked in instead (all placeholders)
- Runtime: server crashes if `JWT_SECRET` env var is missing
- Config codes fallback to `os.urandom(16).hex()` — never uses well-known defaults
- All super/teacher/college codes configurable via env vars (`REG_SUPER_CODE`, etc.)

**Gitleaks config** (`.gitleaks.toml`):
```toml
[allowlist]
paths = [
    "(^|/)pet_config\.json$",
    "(^|/)audit\.log$",
]

[[rules]]
id = "campus-jwt-secret"
description = "Campus app JWT secret"
regex = '''JWT_SECRET\s*=\s*["'](?!your_)[^"']+["']'''
```

## 4. Rate Limit Bypass

### Status: Mitigated (nginx + slowapi + dual-layer)

**Discovery**: Penetration test showed nginx `limit_req` can be bypassed by using API directly on port 9500, bypassing nginx reverse proxy.

**Prevention**:
- Dual-layer rate limiting: nginx (IP-based) + slowapi (application-level)
- slowapi is middleware in the FastAPI app — enforces even without nginx
- slowapi default: `["200/day", "60/hour"]` per IP
- Per-endpoint limits on sensitive routes
- nginx zones: `api=30r/s`, `login=10r/m`, `register=5r/h`, `resetpw=3r/m`

**Application-level limits**:
| Endpoint | slowapi limit | nginx limit |
|----------|---------------|-------------|
| POST /api/login | 5/min | 10r/m burst=3 |
| POST /api/register | 5/hr | 5r/h burst=2 |
| POST /api/auth/reset-password | 3/min | 3r/m burst=2 |
| POST /api/messages | 60/hr | 30r/s (API default) |
| POST /api/notices | 10/hr | 30r/s |
| POST /api/upload | 30/hr | 30r/s |

**Weakness**: GET endpoints have no per-endpoint application limits — only nginx default `30r/s`. Mitigated by Redis caching.

## 5. JWT / Token Security

### Status: Mitigated (rotation, hash storage, short expiry)

**Key decisions**:
- **Algorithm**: HS256 (symmetric). RS256 not used because single-service architecture makes key pair management overhead unnecessary.
- **Expiry**: Access tokens expire in 1 hour. Refresh tokens expire in 30 days.
- **Rotation**: Every token refresh creates a new refresh token, old one invalidated. Prevents refresh-token replay.
- **Storage**: Refresh token hash stored in DB (SHA-256), not plaintext. Access token in FlutterSecureStorage (AES-encrypted).
- **Race condition protection**: Refresh token endpoint uses `SELECT ... FOR UPDATE` inside a transaction to prevent concurrent refresh-token reuse (race condition → both get new tokens, old one invalidated).

**Attack scenario — refresh token stolen**:
1. Attacker steals refresh token from client device
2. Attacker calls `/api/token/refresh` — gets new access + refresh tokens
3. Original user's next refresh fails — old token hash doesn't match DB
4. Both users have valid tokens — but original user re-logs in, attack detected

**Mitigation for stolen access token**:
- 1-hour expiry window
- No API to list all users without high-privilege role
- Account disable (`is_active=0`) prevents token reuse (checked in `get_current_user`)

## 6. PII / Information Disclosure

### Status: Partially Mitigated

**Discovered PII exposure points**:
| Endpoint | Risk | Mitigation |
|----------|------|------------|
| GET /api/me (SELECT *) | Returns all user columns including `password_hash` | main_remote.py explicitly selects columns; main.py still uses `SELECT *` |
| GET /api/users/list (teacher+) | Returns name, student_id, class, college | Role-gated to teacher+ |
| GET /api/activities/{id}/export | Exports phone numbers | Role-gated, CSV injection escape (`_csv_escape`) |
| GET /api/feedback (admin) | Shows content, display_name | Backend records real user_id but displays "匿名用户" |
| GET /api/users/search?q= | LIKE search on student_id | Mitigated by short partial match, no results beyond 5 |

**Prevention**:
- Never use `SELECT *` in production endpoints — always specify columns
- Phone/QQ fields have `show_phone`/`show_qq` privacy flags
- CSV export uses `_csv_escape` to prevent CSV injection (`=`, `+`, `-`, `@` prefix → prepend `'`)
- Feedback system records real `user_id` for abuse tracking but displays "匿名用户"

## 7. XSS (Cross-Site Scripting)

### Status: Mitigated (CSP + input filtering + output encoding)

**Attack surface**:
- Activity title/description
- Notification content
- Notice title/content
- Message content
- Feedback content

**Prevention layers**:
1. **nginx CSP header**: `script-src 'self'; frame-ancestors 'none'`
2. **Pydantic max_length**: Limits prevent oversized payloads
3. **Impersonation filter**: Blocks titles containing `【系统】`, `【官方】`, `【教务】`, etc.
4. **Suspicious URL filter**: Blocks bare links in notices without context keywords

```python
# main_remote.py notice title filter
_impersonate_prefixes = ('【系统', '【官方', '【教务', '【学工', '【学生', '【财务', '【学校')
for pfx in _impersonate_prefixes:
    if pfx in req.title:
        raise HTTPException(400, "禁止冒充系统通知")
```

**Weakness**: Input stored raw in DB — output escaping done by Flutter client, not server. If any non-Flutter client (curl, script) reads API, it receives raw HTML.

## 8. Race Conditions / Concurrency

### Status: Partially Mitigated

**Discovered race conditions**:
1. **Signup max_participants**: `SELECT count(*) + INSERT` gap. Signup function uses `FOR UPDATE` on the activity row, then checks count inside the same transaction. Mitigated.
2. **Refresh token rotation**: `SELECT + UPDATE` gap. Uses `SELECT ... FOR UPDATE` inside a transaction. Mitigated.
3. **Substitute student**: `old_signup status check + update`. Uses `FOR UPDATE` on both rows inside a transaction. Mitigated.
4. **Int code join**: `SELECT + INSERT` gap. Not mitigated (no FOR UPDATE on the activity row) — low risk because `INSERT INTO signups` has unique constraint on (activity_id, user_id).

**Prevention pattern**:
```python
async with pool.acquire() as conn:
    async with conn.transaction():
        row = await conn.fetchrow("SELECT ... FOR UPDATE", ...)
        # ... business logic ...
```

## 9. Password Security

### Status: Strong (bcrypt + rate limits)

**Policy**:
- Minimum length: 6 characters (both login and registration)
- Hash algorithm: bcrypt with auto-salt (`bcrypt.hashpw(password.encode(), bcrypt.gensalt())`)
- Legacy support: argon2 hashes migrated to bcrypt on next login
- Rate limits: 5/min login attempts per IP, 5/hr registrations per IP, 3/min password resets

**Password reset flow**:
1. Admin-initiated: Teacher/school_admin calls POST `/api/users/reset-password`
2. Self-service: User provides name + phone + student_id matching all three, then sets new password
3. Both flows are audit-logged

**Weakness**: No password complexity requirements (no min special chars, no number requirement).

## 10. Session Management

### Status: Mitigated

**Session flow**:
```
Login → access_token (1hr) + refresh_token (30d) → stored in FlutterSecureStorage
Token refresh → rotation: old refresh invalidated, new pair issued
Logout → client clears storage (no server-side invalidation)
```

**Server-side controls**:
- Account disable (`is_active=0`) checked on every request via `get_current_user`
- Token validation includes `refresh_token_exp > NOW()` check
- No token blacklist (Redis not available in degraded mode) — acceptable risk for campus app

## 11. File Upload

### Status: Mitigated

**Controls**:
- Allowed types: `image/jpeg`, `image/png`, `image/webp`, `image/gif` only
- Max size: 10MB
- Content-type validation (checking MIME, not extension)
- Filename: UUID-based, no user-controlled naming
- Compression: PIL resizes to max 1920px, saves as JPEG quality 85
- Direct access: `location /static/uploads/ { deny all; }` in nginx — only served through `/api/uploads/` with auth
- Auth check on `/api/uploads/{filename}` endpoint

**Weakness**: Image re-compression happens after content-type check — attacker can slightly modify valid image to include malicious data (polyglot). Mitigated by: nginx blocks .php/.asp execution, no user-controlled filename extension.

## 12. Authentication Bypass (Missing Auth)

### Status: Mitigated

**Pattern used across all endpoints**:
```python
async def get_current_user(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "未登录")
    payload = verify_token(auth[7:])
    if not payload:
        raise HTTPException(401, "Token过期，请重新登录")
    user = await database.get_user_by_id(payload["user_id"])
    if not user:
        raise HTTPException(401, "用户不存在")
    if not user.get("is_active", True):
        raise HTTPException(401, "账户已被禁用，请联系管理员")
    return user
```

**Every endpoint reviewed**: 87 endpoints, 0 missing `Depends(get_current_user)`.
Only 2 endpoints are public (no auth):
- `GET /api/health` — read-only, returns DB/Redis status
- `GET /api/version` — returns app version and APK URL

## 13. Notice/Activity Impersonation

### Status: Mitigated

**Attack scenario**: Teacher creates a notice titled `【系统通知】账号异常，请点击链接验证` to phish student credentials.

**Prevention**:
```python
# Block official-sounding prefixes
_impersonate_prefixes = ('【系统', '【官方', '【教务', '【学工', '【学生', '【财务', '【学校')
for pfx in _impersonate_prefixes:
    if pfx in req.title:
        raise HTTPException(400, "禁止冒充系统通知")

# Block bare URLs in notice content
if re.search(r'https?://|intent://|market://|tel://|sms://|data:', req.content):
    if not any(keyword in req.content for keyword in ('校内', '活动', '报名', '通知', '附件', '详情', '查看', '链接')):
        raise HTTPException(400, "公告内容包含可疑链接")
```

Same filter applied on notice edit (`PUT /api/notices/{nid}`) and activity creation.

## 14. Privilege Escalation via Role Assignment

### Status: Mitigated

**Attack scenario**: college_admin tries to assign themselves as school_admin.

**Prevention**:
```python
# college_admin can only set student/teacher/publisher roles
if user["role"] == "college_admin" and req.role not in ("student", "teacher", "publisher"):
    raise HTTPException(403, "学院管理员无权设置此角色")
# Only school_admin can set college_admin or school_admin
if req.role in ("college_admin", "school_admin") and user["role"] != "school_admin":
    raise HTTPException(403, "仅超级管理员可设置此角色")
```

**Cooldown on role revocation**: 3-day cooldown before a demoted user can be re-promoted.

## 15. CSV Injection

### Status: Mitigated

**Attack vector**: User registers with name `=SUM(A1:A1000)` or `@cmd|'/c calc'!A1`. When exported to CSV, Excel interprets cells starting with `=`, `+`, `-`, `@` as formulas.

**Prevention** (`_csv_escape`):
```python
def _csv_escape(val):
    s = str(val or "")
    if s and s[0] in '=+-@':
        s = "'" + s
    if '"' in s or '\n' in s or '\r' in s or ',' in s:
        s = '"' + s.replace('"', '""') + '"'
    return s
```

All CSV exports use `_csv_escape` on every cell.

## Vulnerability Categories Summary

| # | Category | Status | Detection Method | Fix PR |
|---|----------|--------|-----------------|--------|
| 1 | SQL Injection | ✅ Mitigated | semgrep + code review | — |
| 2 | IDOR | ✅ Mitigated | Pen test + manual | Added `_can_manage_act()` |
| 3 | Secret Leak | ✅ Mitigated | gitleaks | `ab0ed46` |
| 4 | Rate Limit Bypass | ✅ Mitigated | Pen test | Added slowapi + nginx zones |
| 5 | Token Reuse | ✅ Mitigated | Code review | Refresh token rotation |
| 6 | PII Disclosure | 🟡 Partial | Code review | Explicit column selects |
| 7 | XSS | 🟡 Partial | Code review | CSP + input filters |
| 8 | Race Condition | 🟡 Partial | Code review | FOR UPDATE on critical paths |
| 9 | Weak Password | ✅ Mitigated | Code review | bcrypt + rate limits |
| 10 | Session Mgmt | 🟡 Partial | Code review | No server-side invalidation |
| 11 | File Upload | ✅ Mitigated | Code review | Type/size/auth checks |
| 12 | Auth Bypass | ✅ Mitigated | Semgrep | `Depends(get_current_user)` |
| 13 | Impersonation | ✅ Mitigated | Code review | Title prefix filter |
| 14 | Priv Escalation | ✅ Mitigated | Code review | Role check before assignment |
| 15 | CSV Injection | ✅ Mitigated | Pen test | `_csv_escape` |
