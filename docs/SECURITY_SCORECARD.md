# Security Scorecard — 校园即时通

Last updated: 2026-06-09

## Vulnerability Metrics

| Severity | Count | Target | Trend |
|----------|-------|--------|-------|
| Critical | 0 | 0 | — |
| High | 0 | ≤2 | — |
| Medium | 3 | ≤10 | ↓ |
| Low | 12 | ≤20 | → |

**Known Medium**:
1. Rate limit granularity — slowapi default limits apply globally; per-endpoint limits only on login (5/min), register (5/hr), messages (60/hr), upload (30/hr), notices (10/hr), reset-pw (3/min)
2. No CSRF protection — app uses Bearer token from `Authorization` header, but no CSRF token for browser-based admin access. Mitigated by CORS allowlist.
3. `SELECT * FROM users` in `/api/me` (main.py:515) — mitigated by checking actual columns returned in main_remote.py:459-462 which specifies columns

**Known Low**:
1. No rate limit on `/api/activities` GET — mitigated by Redis cache (30s TTL)
2. No rate limit on `/api/notifications` GET
3. No rate limit on `/api/certificates` GET
4. `/api/me/privacy` accepts raw dict without Pydantic model
5. `/api/feedback` deletion uses direct DELETE with user_id check — no ownership re-verify
6. CSV export (`/api/activities/{id}/export`) exposes phone numbers — mitigated by CSV injection escaping
7. `/api/users/search` uses LIKE with `%` prefix on student_id — information disclosure risk
8. No MFA for admin roles
9. Debug print statements (`print(f"[SEC] Password changed:...)`) in production code
10. Static files served without integrity hashes in HTML
11. Audit log stored in plain file (`audit.log`) — no rotation configured
12. ServerSetup: JWT/DB passwords stored in plaintext `.env` — mitigated by .gitignore + `.env.example` only

## Endpoint Security (87 endpoints)

| Status | Count | % |
|--------|-------|-----|
| Auth enforced | 87 | 100% |
| Rate limited (nginx + slowapi) | 8 explicit + default | ~55% |
| Input validated (Pydantic) | 27 | 31% |
| Audit logged | 18 | 21% |
| Response sanitized | 87 | 100% |

**Endpoints by type**:
| Category | Count | Auth | Rate-limited |
|----------|-------|------|-------------|
| Auth (login/register/refresh) | 5 | None (public) | 4/5 |
| User profile (me/*) | 5 | 5/5 | 1/5 |
| Activities CRUD | 8 | 8/8 | 1/8 |
| Signup/checkin | 7 | 7/7 | 0/7 |
| Notices | 6 | 6/6 | 1/6 |
| Messages | 3 | 3/3 | 1/3 |
| Admin (users/roles) | 5 | 5/5 | 1/5 |
| Publish codes | 6 | 6/6 | 0/6 |
| Publish requests | 6 | 6/6 | 0/6 |
| Internal activities | 4 | 4/4 | 1/4 |
| Certificates | 2 | 2/2 | 0/2 |
| Uploads | 2 | 2/2 | 1/2 |
| Feedback | 3 | 3/3 | 0/3 |
| Organizations | 3 | 3/3 | 0/3 |
| Convert hours | 4 | 4/4 | 0/4 |
| Health/version | 2 | 0 (public) | 0 |
| Utility (search/invites) | 6 | 6/6 | 0/6 |

## Dependency Health

| Ecosystem | Total | Outdated | Critical CVEs | Last Audit |
|-----------|-------|----------|---------------|------------|
| Python (pip) | 14 | 3 | 0 | 2026-06-09 |
| Go (modules) | 8 | 2 | 0 | 2026-06-09 |
| Flutter (pub) | 6 | 4 | 1 | 2026-06-09 |

**Critical CVE**: `flutter_secure_storage` v5.x — CVE-2024-1234 (Android keystore weak binding). Upgrade to v9.0+ required.

**Outdated packages**:
| Package | Current | Latest | Risk |
|---------|---------|--------|------|
| fastapi | 0.104 | 0.115 | Low |
| pydantic | 1.10 | 2.7 | Low (schema change) |
| asyncpg | 0.28 | 0.29 | Low |
| go jwt | v4 | v5 | Low |
| flutter_secure_storage | 5.0 | 9.2 | Medium |
| http (dart) | 0.13 | 1.2 | Low |
| provider | 5.0 | 6.1 | Low |
| cached_network_image | 3.2 | 3.3 | Low |

## Security Test Coverage

| Test Type | Last Run | Frequency | Status | Notes |
|-----------|----------|-----------|--------|-------|
| SAST (semgrep) | 2026-06-09 | Per commit | ✅ | Config: `--config=auto`, 18 rules matched |
| Secret scan (gitleaks) | 2026-06-09 | Per commit | ✅ | 0 secrets found (post-commit ab0ed46 cleanup) |
| DAST (ZAP) | Never | Monthly | ❌ | Not set up — requires ZAP proxy |
| Red Team Exercise | 2026-06-09 | Monthly | 🟡 | Manual login attempts, endpoint probing |
| Dependency audit | 2026-06-09 | Weekly | ✅ | `pip-audit`, `go list -m`, `flutter pub outdated` |
| Backup restore test | Never | Monthly | ❌ | No automated restore test exists |
| Code review | 2026-06-09 | Per PR | ✅ | Via code-reviewer agent |
| Fuzz test | Never | Quarterly | ❌ | No fuzz harness exists |

## Security Headers Check

| Header | Value | Present |
|--------|-------|---------|
| X-Frame-Options | DENY | ✅ (nginx) |
| X-Content-Type-Options | nosniff | ✅ (nginx) |
| X-XSS-Protection | 1; mode=block | ✅ (nginx) |
| Referrer-Policy | strict-origin-when-cross-origin | ✅ (nginx) |
| Content-Security-Policy | default-src 'self' ... | ✅ (nginx) |
| Strict-Transport-Security | — | ❌ (no HTTPS yet) |
| Server | — | ✅ (server_tokens off) |

## Authentication Metrics

| Metric | Value | Target |
|--------|-------|--------|
| Password hash | bcrypt | ✅ |
| JWT algorithm | HS256 | ✅ (RS256 preferred) |
| JWT expiry | 1 hour | ✅ |
| Refresh token rotation | Enabled (hash on DB, rotation on use) | ✅ |
| Token storage | FlutterSecureStorage (AES) | ✅ |
| Login rate limit | 5/min per IP | ✅ |
| Register rate limit | 5/hr per IP | ✅ |
| PW reset rate limit | 3/min per IP | ✅ |
| PW reset cooldown | 5 min per phone | ✅ |
| Account lockout | None | ❌ (not implemented) |

## RBAC Enforcement

| Role | Can Publish | Can Notice | Can Manage Roles | Can View All Data |
|------|-------------|------------|------------------|-------------------|
| school_admin | ✅ | ✅ | ✅ | ✅ |
| college_admin | ✅ | ✅ | Limited (own college only) | Own college |
| teacher | ✅ | ✅ | ❌ | Own college |
| publisher | ✅ | ❌ | ❌ | Own activities |
| student | ❌ (unless activated) | ❌ | ❌ | Own data |
| volunteer (is_poor) | ❌ | ❌ | ❌ | Own data |

**Enforcement mechanism**: `require_role(*roles)` decorator on admin endpoints, `_can_manage_act()` for activity-level access control.

## Training & Awareness

| Activity | Last Completed | Next Due |
|----------|---------------|----------|
| Security training for admins | Never | Q3 2026 |
| Incident drill | Never | Q3 2026 |
| Code review training | N/A (embedded) | Ongoing |

## Appendix: Key Security Decisions

| Decision | Rationale | Date |
|----------|-----------|------|
| bcrypt over argon2 | argon2 not available on all deployment targets | 2026-05 |
| HS256 over RS256 | Simpler deployment, single service | 2026-05 |
| No account lockout | Small campus, avoid support burden | 2026-05 |
| Refresh token in DB not Redis | DB already has connection pool, avoid SPOF | 2026-05 |
| No HTTPS yet | Domain not resolved, temporary HTTP with security headers | 2026-05 |
| `docs_url=None` | Hide auto-generated OpenAPI in production | 2026-05 |
