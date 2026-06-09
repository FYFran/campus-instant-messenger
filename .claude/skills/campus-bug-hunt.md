---
name: campus-bug-hunt
description: Systematic debug pipeline — collect evidence, trace with codegraph, find root cause, fix, verify
model: claude-sonnet-4-6
tools: [Read, Grep, Glob, Bash, Edit, codegraph_search, codegraph_callers, codegraph_context, codegraph_trace, codegraph_impact]
---

# Campus Bug Hunt

## Core Behavior

- **If unsure, say so** — don't guess at root causes. Collect evidence first.
- **Reproduce before fixing** — confirm the bug exists before making changes.
- **Verify after fix** — run campus_check.py and check for same bug pattern in other files.
- **Both backends** — check if the same bug exists in Python AND Go.
- **Prefer reading over guessing** — actual code paths may differ from what you remember.

## Trigger
When user says: "fix this", "something broken", "bug", "not working", "error", "crash", "why is", "broken", "bug report", "issue"

## Process

### Step 1 — Collect Evidence
```bash
# Check service logs (SSH to server)
ssh root@139.196.50.134 "journalctl -u campus-app --no-pager -n 100"

# Check audit log for recent errors
ssh root@139.196.50.134 "tail -50 /app/audit.log"

# Check nginx errors
ssh root@139.196.50.134 "tail -50 /var/log/nginx/error.log"

# Health check
curl -s http://139.196.50.134/api/health
```
If local dev: check `f:/ClaudeFiles/campus_app/server/` logs and console output.
If local Python service: check `pete_doctor.py` diagnostic output.

### Step 2 — Trace With CodeGraph
Do NOT grep or manually read files. Use codegraph tools:

1. `codegraph_context("<module>")` — understand the feature module
2. `codegraph_trace("from", "to")` — trace the full code path from endpoint to DB
3. `codegraph_callers("<function>")` — find who calls a function
4. `codegraph_impact("<symbol>")` — what would changing this break

Trace the symptom backward to root cause. Example chain:
```
Bug: "User can't sign up for activity"
→ codegraph_context("signup") — understand signup flow
→ codegraph_trace("signup_endpoint", "database_insert") — full path
→ codegraph_callers("_can_manage_act") — check ownership logic
```

### Step 3 — Check Both Backends
The project has TWO backends that must be checked independently:

| Backend | File | Status |
|---------|------|--------|
| Python (production) | `campus_app/server/main_remote.py` | Deployed as `/app/main.py` |
| Go (future) | `campus_go/main.go` + `handlers/` | Not deployed, but being built |

- Bug in Python? Check if same logic exists in Go (bug will ship when Go replaces Python)
- Bug in Go? Check if Python has the same bug pattern
- The `deploy.py` script maps `main_remote.py` to `/app/main.py` — confirm which file is actually running on the server

### Step 4 — Find Root Cause (Not Symptom)
Apply systematic debugging:

1. **Reproduce** — Get exact steps, input, and expected vs actual output
2. **Isolate** — Binary search: comment out half the logic, see if bug persists
3. **Verify hypothesis** — Change ONE variable at a time, re-test
4. **Root cause** — The fundamental reason, not the proximate trigger. Examples:
   - Symptom: "500 error on signup" → Root cause: "FOR UPDATE query missing on activity row, race condition causes unique constraint violation"
   - Symptom: "User can't log in" → Root cause: "Refresh token hash column NULL after migration"
   - Symptom: "Page blank" → Root cause: "Flutter setState after widget disposed"

### Step 5 — Fix
- Surgery only: change the minimum lines to fix root cause
- If fix touches auth/security: add semgrep rule to prevent regression
- If fix touches DB: verify migration doesn't break existing data
- If fix touches Flutter: check `mounted` before `setState`

### Step 6 — Verify
```bash
# 1. Syntax check
python -c "import ast; ast.parse(open('campus_app/server/main_remote.py', encoding='utf-8').read())"
cd campus_go && go build ./...

# 2. Functional verification
python f:/ClaudeFiles/campus_check.py

# 3. Regression: search for same bug pattern in other files
rg -n "<bug_pattern>" --type-add 'code:*.{py,dart,go}' -t code

# 4. If Flutter: flutter analyze  # 0 errors
```

### Step 7 — Report
```
## Bug Report — {title}

**Environment**: {production/local/which file}
**Symptom**: {what the user sees}
**Root Cause**: {1-2 sentences, the fundamental reason}
**Fix**: {file:line-range} — {what changed, 1 sentence}
**Verified**: {campus_check.py OK / Flutter analyze OK / manual test OK}
**Regression check**: {same pattern found in {n} other files / no other instances}
```

## References
- `f:\ClaudeFiles\docs\CODE_REVIEW.md` — checklist for verifying fixes
- `f:\ClaudeFiles\docs\INCIDENT_RESPONSE.md` — for production incidents
- `f:\ClaudeFiles\campus_check.py` — functional verification
- `f:\ClaudeFiles\.claude\skills\campus-code-review.md` — post-fix review
- `f:\ClaudeFiles\CLAUDE.md` — agent tool mapping for debugging

## Anti-patterns
- DO NOT start fixing before reproducing the bug
- DO NOT fix symptoms — if the error is "500", the root cause isn't "add try/except"
- DO NOT fix only one backend when both have the same bug
- DO NOT skip `campus_check.py` — syntax is not the same as functionality
- DO NOT assume the deployed file is `main.py` — check `deploy.py` to see which file maps to `/app/main.py`
- DO NOT fix without searching for same bug in other files — this project has parallel code paths
