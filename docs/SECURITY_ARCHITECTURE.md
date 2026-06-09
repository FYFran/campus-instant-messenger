# Security Architecture — 校园即时通

## Deployment Architecture

```ascii
                            Internet (80/443)
                                  │
                             ┌────▼────┐
                             │  Nginx  │  ← fail2ban, UFW, rate limit zones
                             │  :80    │
                             └────┬────┘
                                  │
                          ┌───────┼────────┐
                          │       │        │
                     ┌────▼──┐ ┌──▼───┐ ┌──▼──────┐
                     │ API   │ │Static│ │ Uploads │
                     │ :9500 │ │ Files│ │ (deny)  │
                     └───┬───┘ └──────┘ └─────────┘
                         │
               ┌─────────┼─────────┐
               │         │         │
          ┌────▼───┐ ┌──▼───┐ ┌───▼────┐
          │Uvicorn │ │Uvicorn│ │Uvicorn │  ← 4 workers
          │ w1     │ │ w2   │ │ w3/4   │
          └────────┘ └──────┘ └────────┘
               │         │         │
               └─────────┼─────────┘
                         │
                    ┌────▼────┐
                    │ Redis   │  ← Cache layer (127.0.0.1:6379)
                    │ (opt)   │
                    └─────────┘
                         │
                    ┌────▼────┐
                    │PostgreSQL│  ← Primary data store
                    │ :5432   │
                    └─────────┘
```

## Authentication Flow

```ascii
┌──────────┐                    ┌─────────┐                    ┌──────────┐
│  Client  │                    │  Nginx  │                    │  Server  │
│ (Flutter)│                    │  :80    │                    │  :9500   │
└────┬─────┘                    └────┬────┘                    └────┬─────┘
     │                               │                             │
     │  POST /api/login              │                             │
     │  {student_id, password}       │                             │
     │──────────────────────────────>│                             │
     │                               │  Rate limit check (10r/m)  │
     │                               │     X-Real-IP header       │
     │                               │────────────────────────────>│
     │                               │                             │
     │                               │                      ┌──────▼───────┐
     │                               │                      │  1. Find user │
     │                               │                      │     by sid    │
     │                               │                      │  2. bcrypt    │
     │                               │                      │     verify    │
     │                               │                      │  3. Generate  │
     │                               │                      │     JWT (1hr) │
     │                               │                      │  4. Generate  │
     │                               │                      │     refresh   │
     │                               │                      │     token     │
     │                               │                      │  5. Store hash │
     │                               │                      │     in DB     │
     │                               │                      └──────────────┘
     │                               │                             │
     │  200 {token, refresh_token,   │                             │
     │       user profile}           │                             │
     │<──────────────────────────────│<────────────────────────────│
     │                               │                             │
     │  Store in FlutterSecureStorage│                             │
     │  (AES-encrypted on device)    │                             │
     │                               │                             │
     │  GET /api/me                  │                             │
     │  Authorization: Bearer <jwt>  │                             │
     │──────────────────────────────>│                             │
     │                               │  Pass-through               │
     │                               │────────────────────────────>│
     │                               │                      ┌──────▼───────┐
     │                               │                      │  1. Decode   │
     │                               │                      │     JWT      │
     │                               │                      │  2. Check exp│
     │                               │                      │  3. Fetch    │
     │                               │                      │     user by  │
     │                               │                      │     user_id  │
     │                               │                      │  4. Check    │
     │                               │                      │     is_active│
     │                               │                      └──────────────┘
     │                               │                             │
     │  200 {user data}              │                             │
     │<──────────────────────────────│<────────────────────────────│
```

## Token Lifecycle

```ascii
Login
  │
  ├── access_token (JWT, HS256)
  │     payload: {user_id, exp: +1hr}
  │     storage: FlutterSecureStorage (AES)
  │     validation: verify_token() → decode + check exp
  │
  └── refresh_token (64-char hex, secrets.token_hex(32))
        storage: SHA-256 hash in DB, raw on device
        expiry: 30 days
        rotation: on every use, old hash invalidated, new pair issued

Token refresh flow:
  Client                 Server
    │                      │
    │ POST /api/token/refresh
    │ {refresh_token: raw}
    │─────────────────────>│
    │                      │  BEGIN TRANSACTION
    │                      │  SELECT ... WHERE hash=$1 AND exp>NOW() FOR UPDATE
    │                      │  IF not found → 401
    │                      │  Generate new access_token (1hr)
    │                      │  Generate new refresh_token
    │                      │  UPDATE hash, exp WHERE id=$1
    │                      │  COMMIT
    │<─────────────────────│
    │ {token, refresh_token}
```

## Authorization Model (RBAC — 4 Roles + Extensions)

```ascii
Hierarchy:
  school_admin (超管)       ← full access, all colleges
      │
  college_admin (院超管)    ← own college, can set teacher/publisher
      │
  teacher (学院老师)        ← own college, publish/approve
      │
  publisher (发布者)        ← publish activities only (student + can_publish)
      │
  student (学生)            ← basic: browse, signup, messages
      │
  volunteer (义工, is_poor) ← same as student + can see poor-specific content
```

**Enforcement points**:

1. **Decorator level**: `require_role("teacher", "college_admin", "school_admin")`
   - Used on: publish-codes CRUD, user management, notice creation, data exports
   - Covers ~20 endpoints

2. **Function level**: `get_current_user` → checks JWT, fetches user, checks `is_active`
   - Used on: all non-public endpoints (~85 endpoints)

3. **Object level**: `_can_manage_act(act, user)` — activity-specific access
   - school_admin: all activities
   - college_admin: own college + all-scope activities
   - creator: own activity
   - teacher: none without being creator (except via notification/report)

4. **Data level**: SQL scope filtering
   - Students see: `scope_type='all'` OR `scope_type='college' AND scope_value=my_college`
   - Teachers see: all activities (no scope filter)
   - Internal activities: only if joined as staff

## Data Flow

```ascii
┌─────────────────────────────────────────────────────────────────┐
│                         CLIENT                                   │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐  ┌────────────────┐  │
│  │ Activities│  │ Signups  │  │ Messages  │  │ Notices        │  │
│  └─────┬────┘  └────┬─────┘  └─────┬─────┘  └───────┬────────┘  │
│        │            │              │                 │           │
│        └────────────┴──────────────┴─────────────────┘           │
│                           │ HTTPS (planned)                       │
└───────────────────────────┼─────────────────────────────────────┘
                            │
                    ┌───────▼───────┐
                    │    Nginx       │  ← TLS termination (planned)
                    │    Security    │  ← headers, rate limits, block
                    │    headers     │     php/asp probes, bot search
                    └───────┬───────┘
                            │
                    ┌───────▼───────┐
                    │   API Server   │
                    │   (FastAPI)    │
                    │                │
                    │  Request flow: │
                    │  1. Parse JWT  │
                    │  2. Auth check │
                    │  3. Rate check │
                    │  4. Validate   │
                    │  5. Execute    │
                    │  6. Audit log  │
                    │  7. Response   │
                    └───────┬───────┘
                            │
               ┌────────────┼────────────┐
               │            │            │
        ┌──────▼────┐ ┌────▼────┐ ┌─────▼──────┐
        │ PostgreSQL│ │  Redis  │ │ Filesystem  │
        │           │ │ (cache) │ │ (uploads)   │
        │ Tables:   │ │         │ │             │
        │ users     │ │ TTL:    │ │ /static/    │
        │ activities│ │ 30s acts│ │ /static/    │
        │ signups   │ │ 30s ntc │ │   uploads/  │
        │ certs     │ │ 300s clg│ │             │
        │ feedbacks │ │ 10s act │ │ Access via  │
        │ messages  │ │         │ │ /api/uploads│
        │ tokens    │ │         │ │ with auth   │
        │ publish   │ │         │ │             │
        │ codes     │ │         │ │             │
        └───────────┘ └─────────┘ └─────────────┘
```

## Data Sensitivity Classification

| Category | Level | Examples | Storage | Encryption |
|----------|-------|---------|---------|------------|
| Credentials | CRITICAL | password_hash, JWT_SECRET, DB_PASSWORD | PostgreSQL, .env | bcrypt hash, `.env` not in repo |
| Auth tokens | HIGH | refresh_token_hash, JWT | PostgreSQL (hash only) | SHA-256 hash |
| PII | HIGH | name, phone, qq, student_id | PostgreSQL | Plaintext (privacy flags control display) |
| Activity data | LOW | title, description, hours | PostgreSQL | Plaintext |
| Signups | MEDIUM | user_id, activity_id, status | PostgreSQL | Plaintext |
| Messages | MEDIUM | sender, receiver, content | PostgreSQL | Plaintext |
| Feedback | MEDIUM | user_id, content | PostgreSQL | Plaintext (user_id logged for anti-abuse) |
| Audit log | HIGH | who, what, when | Filesystem (audit.log) | Plaintext, local filesystem only |
| Uploads | LOW | images | Filesystem (static/uploads/) | UUID filename, auth-gated |

## Encryption At Rest

| Layer | Status | Details |
|-------|--------|---------|
| PostgreSQL | ❌ Not enabled | No TDE; file permissions restrict access |
| Redis | ❌ Not enabled | Bound to 127.0.0.1, protected-mode enabled |
| Filesystem | ❌ Not enabled | No filesystem-level encryption |
| Client storage | ✅ AES-256 | FlutterSecureStorage on Android/iOS |
| .env secrets | 🟡 Partial | File permissions 600 recommended (not enforced) |

## Encryption In Transit

| Path | Status | Details |
|------|--------|---------|
| Client → Nginx | ❌ Not encrypted | HTTP only; TLS planned but domain not resolved |
| Nginx → Uvicorn | ✅ HTTP (127.0.0.1) | Loopback, no external exposure |
| Uvicorn → PostgreSQL | ❌ Not encrypted | Same host, no SSL; isolated by ufw |
| Uvicorn → Redis | ✅ Loopback | 127.0.0.1 only, protected-mode yes |

## Threat Model

### Assets to Protect
1. User accounts and credentials
2. Activity participation data (hours, certificates)
3. Personal information (name, phone, QQ, class)
4. Auth tokens and sessions
5. Uploaded images
6. Server infrastructure

### Trust Boundaries
1. **Client ↔ Internet**: Untrusted. HTTPS missing (planned).
2. **Internet ↔ Nginx**: First line of defense. Rate limits, security headers, bot blocking.
3. **Nginx ↔ Application**: Trusted (loopback). Forward real IP via X-Real-IP.
4. **Application ↔ Database**: Trusted (loopback). SQL injection prevented by parameterized queries.
5. **Application ↔ Redis**: Trusted (loopback). Redis protected-mode, no auth (127.0.0.1 binding).

### Attack Tree — Compromise User Account

```
Compromise Student Account
├── 1. Brute force login
│   ├── Mitigation: slowapi 5/min per IP
│   └── Residual: distributed attack across IPs
├── 2. Steal JWT from device
│   ├── Mitigation: FlutterSecureStorage (AES)
│   └── Residual: rooted device
├── 3. Steal refresh token from DB
│   ├── Mitigation: SHA-256 hash only, not plaintext
│   └── Residual: DB server compromise
├── 4. Forge JWT
│   ├── Mitigation: JWT_SECRET in env, strong entropy
│   └── Residual: HS256 secret crackable if weak
├── 5. Social engineering via notice/activity
│   ├── Mitigation: impersonation prefix filter
│   └── Residual: clever wording without prefixes
└── 6. Self-service password reset
    ├── Mitigation: requires name + phone + student_id match
    └── Residual: attacker knows all three
```

### Attack Tree — Privilege Escalation

```
Escalate from Student to Admin
├── 1. Forge role in JWT
│   ├── Mitigation: JWT only stores user_id, role from DB
│   └── Status: Not feasible (role not in token)
├── 2. IDOR on role-change endpoint
│   ├── Mitigation: require_role("college_admin", "school_admin")
│   └── Status: Blocked at decorator level
├── 3. SQL injection to modify role
│   ├── Mitigation: parameterized queries everywhere
│   └── Status: Blocked
├── 4. Exploit register with super_code
│   ├── Mitigation: super_code = os.urandom(16).hex() default
│   └── Status: Not feasible unless admin leaks the code
└── 5. Use another college_admin's session
    ├── Mitigation: college_admin scoped to own college
    └── Status: Attack limited
```

### Attack Tree — Data Exfiltration

```
Exfiltrate User Data
├── 1. Direct DB access
│   ├── Mitigation: UFW port 22/80/443 only; DB not exposed
│   └── Status: Requires server compromise
├── 2. SQL injection
│   ├── Mitigation: Parameterized queries, semgrep rule
│   └── Status: Blocked
├── 3. School_admin account compromise
│   ├── Mitigation: /api/users has SELECT only; audit log
│   └── Residual: school_admin can see all names/IDs
├── 4. CSV export abuse
│   ├── Mitigation: Role-gated (teacher+), CSV injection escaped
│   └── Residual: Teacher exports student data externally
└── 5. MITM (HTTP → intercept responses)
    ├── Mitigation: None (HTTPS not implemented)
    └── Status: HIGH RISK — priority #1 for TLS
```

### Accepted Risks

| Risk | Rationale | Accept Date |
|------|-----------|-------------|
| No HTTPS | Domain not yet resolved; temp HTTP with security headers | 2026-05 |
| No TLS for DB | DB on same host, loopback only | 2026-05 |
| No account lockout | Small campus (<1000 users), avoid support overhead | 2026-05 |
| Plaintext phone/QQ | Needed for event contact; display controlled by privacy flags | 2026-05 |
| No 2FA/MFA | Too complex for current deployment scale | 2026-05 |
| Server-tokens revealed | nginx `server_tokens off` already set | 2026-05 |

### Security Controls Summary

| Control | Type | Where | Status |
|---------|------|-------|--------|
| Authentication (JWT) | Preventive | Application | Active |
| Refresh token rotation | Preventive | Application | Active |
| Authorization (RBAC) | Preventive | Application | Active |
| Input validation (Pydantic) | Preventive | Application | Active |
| Rate limiting (slowapi) | Preventive | Application | Active |
| Rate limiting (nginx) | Preventive | Network | Active |
| SQL injection prevention | Preventive | Application | Active |
| XSS prevention (CSP) | Preventive | Network | Active |
| Impersonation filter | Preventive | Application | Active |
| CSV injection escape | Preventive | Application | Active |
| File upload validation | Preventive | Application | Active |
| Audit logging | Detective | Application | Active |
| fail2ban | Detective/Preventive | Network | Active |
| UFW firewall | Preventive | Network | Active |
| Secret scanning (gitleaks) | Detective | CI | Active |
| SAST (semgrep) | Detective | CI | Active |
| Secret rotation | Corrective | Process | Manual |
| Backup/restore test | Corrective | Process | ❌ Not done |
| HTTPS/TLS | Preventive | Network | ❌ Planned |

## Appendix: Configuration Files

### `.env` (required)

```env
DB_HOST=localhost
DB_PORT=5432
DB_USER=campus_admin
DB_PASSWORD=<64-char-random>
DB_NAME=campus_app
JWT_SECRET=<64-char-random>
REG_SUPER_CODE=<optional, override default>
REG_COLLEGE_ADMIN_CODE=<optional>
REG_TEACHER_CODE=<optional>
REG_STUDENT_CODE=student2026
```

### nginx security-relevant directives

```nginx
# Security headers
add_header X-Frame-Options "DENY" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none';" always;

# Block malware probes
location ~* \.(php|asp|aspx|jsp|cgi)$ { return 444; }
location ~* (/wp-admin|/wp-login|/xmlrpc\.php) { return 444; }
server_tokens off;

# Protection zones
limit_req_zone $binary_remote_addr zone=login:10m rate=10r/m;
limit_req_zone $binary_remote_addr zone=api:10m rate=30r/s;
limit_conn_zone $binary_remote_addr zone=addr:10m;
limit_conn addr 100;
```

## Appendix: Generating Secrets

```bash
# Generate JWT secret (64 hex chars)
python3 -c "import secrets; print(secrets.token_hex(32))"

# Generate DB password
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# Generate registration codes (override defaults)
python3 -c "import secrets; print('SUPER:', secrets.token_hex(16))"
python3 -c "import secrets; print('COLLEGE_ADMIN:', secrets.token_hex(16))"
python3 -c "import secrets; print('TEACHER:', secrets.token_hex(16))"
```
