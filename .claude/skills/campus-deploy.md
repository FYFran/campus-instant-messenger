---
name: campus-deploy
description: Full deploy pipeline — pre-flight checks, security scan, upload, migrate, reload, smoke test, rollback
model: claude-sonnet-4-6
tools: [Read, Grep, Glob, Bash, Edit]
---

# Campus Deploy

## Core Behavior

- **If unsure, say so** — don't guess about server state, deploy script config, or migration order.
- **Read deploy.py first** — it decides which file runs on production. Read it before any deploy.
- **Verify every step** — after each deploy phase, confirm the previous step succeeded.
- **Backup before destructive ops** — verify backup exists before running migrations that change schema.
- **Prefer reading over guessing** — deploy.py, nginx.conf, and service configs change. Read them.

## Trigger
When user says: "deploy", "ship", "push to server", "upload", "release", "go live", "update server"

## Process

### Pre-Flight Checklist (local)

Run ALL checks locally before touching the server:

```powershell
# 1. Python syntax (both backends)
python -c "import ast; ast.parse(open('f:/ClaudeFiles/campus_app/server/main_remote.py', encoding='utf-8').read())"
python -c "import ast; ast.parse(open('f:/ClaudeFiles/campus_app/server/main.py', encoding='utf-8').read())"
python -c "import ast; ast.parse(open('f:/ClaudeFiles/campus_app/server/db.py', encoding='utf-8').read())"
python -c "import ast; ast.parse(open('f:/ClaudeFiles/campus_app/server/migrate.py', encoding='utf-8').read())"

# 2. Go build (if Go backend changed)
cd f:/ClaudeFiles/campus_go && go build ./...
if ($LASTEXITCODE -ne 0) { Write-Error "Go build failed"; exit 1 }

# 3. Flutter analyze (if frontend changed)
cd f:/ClaudeFiles/campus_app && flutter analyze
if ($LASTEXITCODE -ne 0) { Write-Error "Flutter analyze failed"; exit 1 }

# 4. Functional check
python f:/ClaudeFiles/campus_check.py

# 5. Security scan
#   a. Gitleaks: gitleaks detect --source . --no-git
#   b. Semgrep: semgrep --config=.semgrep\ --error
cd f:/ClaudeFiles
```

### Step 1 — Full Security Scan
```bash
cd f:/ClaudeFiles && ./scripts/full_security_scan.sh
```
This runs: gitleaks → semgrep → flutter analyze → Python AST → Go build → campus_check

If ANY step fails: STOP. Fix before deploying.

### Step 2 — Upload
```powershell
# Set SSH password
$env:SSH_PASSWORD = "your_password_here"

# Run deployment script
python f:/ClaudeFiles/campus_app/server/deploy.py
```
The deploy script uploads:
- `main_remote.py` → `/app/main.py` (renamed on server)
- `db.py` → `/app/db.py`
- `migrate.py` → `/app/migrate.py`
- `nginx-campus.conf` → `/etc/nginx/sites-enabled/campus`
- `app-release.apk` → `/app/static/app-release.apk` (if exists)
- Migration SQL files → `/app/migrations/`

If `main.py` is deployed instead of `main_remote.py` (development mode), change this line in `deploy.py`:
```python
"f:/ClaudeFiles/campus_app/server/main_remote.py": "/app/main.py",
```
The CLAUDE.md rule: `deploy.py decides who is running` — check that file first.

### Step 3 — Run Migrations
```powershell
# SSH into server and run migrations
ssh root@139.196.50.134 "cd /app && python migrate.py"
```
Check migration output for errors. If migration fails, rollback:
```bash
ssh root@139.196.50.134 "cd /app && git checkout -- main.py"
```

### Step 4 — Reload Services
```powershell
# Reload nginx
ssh root@139.196.50.134 "nginx -t && systemctl reload nginx"

# Restart campus service
ssh root@139.196.50.134 "systemctl restart campus-app && systemctl status campus-app --no-pager -l"
```

### Step 5 — Health Check
```powershell
# API health
curl -s http://139.196.50.134/api/health

# Service status
ssh root@139.196.50.134 "systemctl status campus-app --no-pager -l | tail -20"

# Nginx status
ssh root@139.196.50.134 "nginx -t"
```

### Step 6 — Smoke Test
Verify the critical user paths work:

```powershell
# 1. Server responds
curl -s http://139.196.50.134/api/version

# 2. Login works
$LOGIN = curl -s -X POST http://139.196.50.134/api/login `
  -H "Content-Type: application/json" `
  -d '{"student_id":"admin","password":"test123"}'
Write-Output $LOGIN

# 3. Activities load
$TOKEN = ($LOGIN | ConvertFrom-Json).access_token
curl -s http://139.196.50.134/api/activities `
  -H "Authorization: Bearer $TOKEN"

# 4. Full check (automated)
python f:/ClaudeFiles/campus_check.py
```

## Rollback (if deploy breaks)

### Quick rollback — code only
```powershell
ssh root@139.196.50.134 @"
cd /app
git stash
git checkout HEAD~1 -- main.py db.py migrate.py
systemctl restart campus-app
systemctl status campus-app --no-pager -l | head -10
"@
```

### Full rollback — code + DB migration
```powershell
ssh root@139.196.50.134 @"
systemctl stop campus-app
cd /app
# Undo last migration (reverse the SQL in the last migration file)
psql -U campus_admin -d campus_app -c 'DROP TABLE IF EXISTS <new_tables_added>;'
git checkout HEAD~1 -- main.py db.py migrate.py
systemctl start campus-app
"@
```

## References
- `f:\ClaudeFiles\campus_app\server\deploy.py` — deployment script (check this first to know which file runs on server)
- `f:\ClaudeFiles\scripts\full_security_scan.sh` — pre-deploy security scan
- `f:\ClaudeFiles\nginx-campus.conf` — nginx config uploaded during deploy
- `f:\ClaudeFiles\campus_check.py` — post-deploy smoke tests
- `f:\ClaudeFiles\docs\INCIDENT_RESPONSE.md` — rollback and incident procedures
- `f:\ClaudeFiles\CLAUDE.md` — "改代码前先确定生产部署的是哪个文件"

## Anti-patterns
- DO NOT deploy without running `full_security_scan.sh` first
- DO NOT skip `campus_check.py` after deploy — it catches field mismatches between frontend and backend
- DO NOT assume `main.py` is deployed — `deploy.py` maps `main_remote.py` to `/app/main.py`
- DO NOT skip smoke test — deploy includes nginx reload which can break routing
- DO NOT deploy if Flutter analyze has errors — they will crash the frontend
- DO NOT forget to set `$env:SSH_PASSWORD` before running deploy.py
- DO NOT deploy during school hours (Monday-Friday 8:00-17:00) unless urgent fix
