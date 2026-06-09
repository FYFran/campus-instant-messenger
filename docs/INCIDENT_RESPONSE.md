# Incident Response Playbook — 校园即时通

## Severity Levels

| Level | Label | Examples | SLA |
|-------|-------|----------|-----|
| **P0** | Critical | Data breach, server down, DB compromised | 15min detect, 1hr contain |
| **P1** | High | Auth bypass, privilege escalation, token leak | 30min detect, 2hr contain |
| **P2** | Medium | XSS, SQL injection (non-auth), rate limit bypass | 4hr detect, 24hr fix |
| **P3** | Low | Info disclosure (non-sensitive), missing header, log leak | 7d fix |

## Roles & Contact

| Role | Who | Responsibility |
|------|-----|---------------|
| **IC (Incident Commander)** | 皮特 (pete_service.pyw) | Coordinate response, declare severity, communicate |
| **Technical Lead** | 一凡 (王一凡) | Execute fixes, rollback, verify patches |
| **DevOps** | 皮特 (auto) | Restart services, check logs, block IPs |
| **Communications** | 皮特 + 一凡 | Notify users, admin, stakeholders |
| **Security SME** | 皮特 + LLM agents | Root cause analysis, semgrep/gitleaks review |

## P0 — Critical Incident (Data Breach / Server Down)

### Detection
- **Alerts**: Health check (`/api/health`) returns non-200 or `database: error`
- **Anomaly**: Audit log shows unusual pattern (mass token refresh, mass password reset)
- **User report**: App unreachable for >5 min
- **Automated**: `pete_doctor.py` detects service down, alerts via Telegram

### Response Timeline

**T+0-15min — Triage & Contain**

1. **IC** — Verify severity: check `/api/health`, DB pool stats, Redis ping
2. **IC** — If DB compromise: immediately rotate `DB_PASSWORD` in `.env`, restart campus.service
3. **IC** — If token leak: invalidate all refresh tokens by truncating `refresh_token_hash` column
4. **Tech Lead** — If server compromise: isolate the instance, block all non-VPN inbound traffic in ufw

```
# Emergency DB password rotation
sudo systemctl stop campus
sudo sed -i 's/DB_PASSWORD=.*/DB_PASSWORD=<new-secret>/' /app/.env
sudo -u postgres psql -c "ALTER USER campus_admin WITH PASSWORD '<new-secret>'"
sudo systemctl start campus
```

5. **Tech Lead** — If access token leak suspected: force all users to re-login

```
# Invalidate all sessions
sudo -u postgres psql -d campus_app -c "UPDATE users SET refresh_token_hash='', refresh_token_exp=NOW()"
```

**T+15-60min — Investigation**

6. **Security SME** — Pull audit.log, nginx access.log, gitleaks report, semgrep findings
7. **Security SME** — Run `python campus_security_audit.py` to scan for exposed secrets or misconfig
8. **IC** — Determine root cause: misconfig, zero-day, credential leak, supply chain

**T+60-120min — Recovery**

9. **Tech Lead** — Apply hotfix, deploy from last known good state
10. **Tech Lead** — Verify: `/api/health` returns OK, DB pool healthy, audit log clean
11. **IC** — Declare incident contained, begin post-mortem

### Communication Templates

**To Users (app notification)**:
```
系统安全维护已完成。为保障账号安全，请重新登录。如有异常请联系管理员。
```

**To Admin (telegram/email)**:
```
[P0 INCIDENT] 严重: {incident_type}
时间: {timestamp}
影响: {affected_users} 用户受影响
根因: {root_cause}
已采取: {actions_taken}
后续: {next_steps}
```

**To External (if data breach)**:
```
[机密] 安全事件通告
平台: 校园即时通
事件时间: {timestamp}
事件类型: {type}
受影响数据: {data_categories}
当前状态: {status}
负责人: 王一凡 (泰州学院)
```

## P1 — High Incident (Auth Bypass)

### Common Scenarios
- JWT secret leaked → attacker forges tokens
- Refresh token rotation broken → replay attack
- Role check missing on an endpoint → privilege escalation
- `get_current_user` returns stale user → access after account disabled

### Response Steps

1. **IC** — Rotate JWT_SECRET in `.env`, restart campus.service
2. **IC** — Add `Depends(get_current_user)` to any endpoints found missing it

```
sudo systemctl stop campus
sudo sed -i 's/JWT_SECRET=.*/JWT_SECRET=<new-64-char-hex>/' /app/.env
sudo systemctl start campus
```

3. **Tech Lead** — Run semgrep on all endpoints

```bash
cd /app && semgrep --config=auto --pattern 'def *\n    return {"ok": True}' main.py
```

4. **Tech Lead** — Verify every route in main.py has auth or is explicitly public

**Auth Required (all except)**:
- `/api/health` — public, read-only
- `/api/login` — auth endpoint
- `/api/token/refresh` — auth endpoint
- `/api/register` — auth endpoint
- `/api/auth/reset-password` — password reset (rate limited)

**Check for missing auth pattern**:
```python
# WRONG — no auth
@app.get("/api/sensitive-data")
async def leak_data():
    return await database.get_all_users()

# RIGHT — auth enforced
@app.get("/api/sensitive-data")
async def safe_data(user: dict = Depends(get_current_user)):
    if user["role"] not in ("school_admin", "college_admin"):
        raise HTTPException(403)
    return await database.get_all_users()
```

5. **IC** — After fix, audit user accounts for signs of unauthorized access

```sql
-- Check for unusual login patterns
SELECT id, student_id, role, refresh_token_exp
FROM users WHERE refresh_token_exp > NOW() + INTERVAL '30 days';
```

## P2 — Medium Incident (XSS / Injection / Rate Limit Bypass)

### Detection
- **XSS**: User reports script execution in notification/activity title
- **SQL Injection**: Error logs show `UNION`, `OR 1=1`, or syntax errors
- **Rate limit bypass**: Audit log shows >1000 requests/min from single user

### Response Steps

**For XSS:**

1. Verify input sanitization on all text fields

```python
# Check: all HTML content goes through {{ }} not {!! !!} in Jinja
# Check: all Pydantic models have max_length set
# Fix: add HTML escaping on output
import html
safe_title = html.escape(dirty_title)
```

2. Add Content-Security-Policy if missing:
```
Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'
```

3. Test with payload `<script>alert(1)</script>` in:
   - Activity title/description
   - Notification content
   - Feedback content
   - Message content

**For SQL Injection:**

1. Verify all queries use parameterized `$1`, `$2` syntax (asyncpg) — never f-strings
2. Check for dynamic column names in UPDATE/ORDER BY — these need whitelist

```python
# DANGEROUS — don't do this
await pool.execute(f"UPDATE activities SET {updates} WHERE id=$1")

# SAFE — always parameterized
await pool.execute("UPDATE activities SET title=$1, description=$2 WHERE id=$3", title, desc, aid)
```

3. Run grep for f-string SQL patterns:
```bash
rg -n 'f".*SELECT.*{.*}"' /app/main.py
rg -n 'f".*INSERT.*{.*}"' /app/main.py
rg -n 'f".*UPDATE.*{.*}"' /app/main.py
```

**For Rate Limit Bypass:**

1. Check nginx config is loading rate-limit zones
2. Verify slowapi middleware is loaded after CORS
3. Test with:

```bash
for i in {1..20}; do curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:9500/api/login -H "Content-Type: application/json" -d '{"student_id":"test","password":"test"}'; done
```

4. Expected: after 5 requests, returns 429

## P3 — Low Incident (Info Disclosure)

### Examples
- Error response exposes Pydantic validation details (fixed: hidden behind custom handler)
- `/api/me` returns `password_hash` column (SELECT * — dangerous)
- CSV export leaks phone numbers (mitigated: CSV injection escaping in place)
- Stack trace in production (fixed: `docs_url=None, redoc_url=None, openapi_url=None`)

### Response Steps

1. Check error handler:

```python
# Verify in main.py — should not expose field-level errors
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(422, {"detail": "请求参数格式错误"})
```

2. Check user endpoint doesn't return sensitive fields:

```python
# WRONG: SELECT * can include password_hash, refresh_token_hash
full = await pool.fetchrow("SELECT * FROM users WHERE id=$1")

# RIGHT: specify columns
full = await pool.fetchrow(
    "SELECT id, student_id, name, class, college, role, is_poor, can_publish, "
    "show_phone, show_qq, qq, phone, gender, publisher_org_id, created_at, "
    "grade, is_active, volunteer_hours FROM users WHERE id=$1", user["id"]
)
```

## Rollback Procedure

### Quick Rollback (code only)

```bash
# Assuming git-deployed
cd /app
git stash
git checkout <last-known-good-hash>
sudo systemctl restart campus
sudo systemctl status campus --no-pager -l
```

### Full Rollback (code + DB schema)

```bash
# 1. Stop server
sudo systemctl stop campus

# 2. Rollback DB migrations
sudo -u postgres psql -d campus_app -c "DROP TABLE IF EXISTS convert_applications;"
sudo -u postgres psql -d campus_app -c "DROP TABLE IF EXISTS role_changes;"
sudo -u postgres psql -d campus_app -c "DROP TABLE IF EXISTS org_hours_applications;"
# 3. Rollback code
cd /app && git checkout <last-known-good-hash>
# 4. Restart
sudo systemctl start campus
```

### Emergency Mode (no DB dependency)

```python
# Start in degraded mode — cache-only, no DB writes
# Set in .env: CAMPUS_EMERGENCY=true
if os.getenv("CAMPUS_EMERGENCY"):
    app.state.limiter = Limiter(key_func=get_remote_address, default_limits=[])
    # Only serve static pages + health check
    @app.get("/api/health")
    async def emergency_health():
        return {"status": "emergency", "message": "维护中，请稍后"}
```

## Post-Incident Root Cause Analysis (RCA)

### RCA Template

```
## 事后分析

**Incident ID**: INC-{YYYYMMDD}-{NN}
**Severity**: P0 / P1 / P2 / P3
**Date**: {date}
**Duration**: {minutes} min
**Detected by**: {alert/monitor/user report}
**ICs**: {names}

### 时间线
| Time | Event |
|------|-------|
| T+0 | Detection |
| T+{n} | Containment |
| T+{n} | Mitigation |
| T+{n} | Resolution |

### 根因
{root cause — technical, in 1-3 sentences}

### 影响
- 受影响用户数: {count}
- 受影响数据: {categories}
- 服务不可用时间: {duration}

### 修复措施
1. {fix 1} — 已有
2. {fix 2} — 已添加
3. {fix 3} — 计划

### 预防措施
- [ ] {action item} — 负责人, 截止日
- [ ] {action item} — 负责人, 截止日

### Lessons Learned
{what went well, what went wrong, what to change}
```

### Incident History Log

```sql
CREATE TABLE IF NOT EXISTS incidents (
    id SERIAL PRIMARY KEY,
    severity VARCHAR(3) NOT NULL,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    detected_at TIMESTAMP NOT NULL DEFAULT NOW(),
    contained_at TIMESTAMP,
    resolved_at TIMESTAMP,
    root_cause TEXT,
    fix_actions TEXT,
    affected_users INTEGER DEFAULT 0,
    mttr_minutes INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);
```

## Appendix: Reference Commands

### Quick Diagnostics

```bash
# Service health
curl http://127.0.0.1:9500/api/health

# Check audit log
tail -100 /app/audit.log

# Check DB connections
sudo -u postgres psql -c "SELECT count(*) FROM pg_stat_activity WHERE datname='campus_app';"

# Check Redis
redis-cli ping
redis-cli info | grep used_memory_human

# Check fail2ban status
sudo fail2ban-client status
sudo fail2ban-client status nginx-limit-req

# Last 100 nginx errors
sudo tail -100 /var/log/nginx/error.log
```

### Emergency Contacts

- **一凡 (王一凡)**: Telegram (via pete_bot)
- **皮特 automation**: pete_service.pyw on 127.0.0.1:8765
- **Server host**: 139.196.50.134 (阿里云), port 22 admin, 80/443 campus
