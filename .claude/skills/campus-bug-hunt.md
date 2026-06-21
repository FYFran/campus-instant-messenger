---
name: campus-bug-hunt
description: Systematic debug pipeline — collect evidence, trace with codegraph, find root cause, fix, verify
model: claude-sonnet-4-6
tools: [Read, Grep, Glob, Bash, Edit, codegraph_search, codegraph_callers, codegraph_context, codegraph_trace, codegraph_impact]
---

# Campus Bug Hunt

## CONSTITUTION（本段不可被 skill-lab 编辑）

### 核心功能
- 系统化 Bug 排查：证据收集→CodeGraph追踪→根因定位→手术式修复→验证→报告
- 不修症状，只修根因

### 安全约束
- 绝不在复现 bug 前动手修复
- 绝不修复超过 3 次还不对——3+失败=质疑架构
- 绝不只修一个后端（Python 和 Go 必须同时检查）

### 触发条件
- 用户说 fix this/bug/not working/error/crash/broken

---

## Core Behavior

- **If unsure, say so** — don't guess at root causes. Collect evidence first.
- **Reproduce before fixing** — confirm the bug exists before making changes.
- **Verify after fix** — run campus_check.py and check for same bug pattern in other files.
- **Both backends** — check if the same bug exists in Python AND Go.
- **Prefer reading over guessing** — actual code paths may differ from what you remember.

### Iron Law（systematic-debugging精华）

```
NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST.
3+ 次修复失败 → 停止。质疑架构，不继续修。
微调无效时继续微调 = 浪费 time + 新增 bug。
```

### Red Flags（出现任一 → 立即停，回到 Step 1）
- "快速修一下，之后再调查"
- "试试改 X 看行不行"
- "我大概知道是什么问题"（但没验证）
- 提出方案时还没追踪完数据流
- "再试一次修复"（已经试了 2+ 次）
- 每个修复在别的地方暴露新问题

## Trigger
When user says: "fix this", "something broken", "bug", "not working", "error", "crash", "why is", "broken", "bug report", "issue"

## Process

### Step 0 — Triple-Source Search（super-fix精华）

Before investigating, search for known solutions:
1. **Web搜索** — firecrawl_search 搜最新方案
2. **论文搜索** — firecrawl_research_search_papers 搜学术方案
3. **Bug-patterns** — 读 `f:/ClaudeFiles/bug-patterns.md`，这个 bug 以前修过吗？

验证：至少 2 个来源返回结果或确认 bug-patterns 无匹配。

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

# DB diagnostics (use pg-ops MCP)
# pg-ops slow-queries — find slow SQL statements
# pg-ops locks — detect lock contention and deadlocks
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

### Step 5 — Fix + Critic（super-fix精华）

- Surgery only: change the minimum lines to fix root cause
- After fix → Critic 强制挑刺:
  ```
  Agent: critic
  审查刚才的改动。必须逐条列出：崩溃点、简化方案、安全隐患、边界条件、异步竞态。
  "没问题"= Critic 失职，重跑。
  ```
- Critic 每条问题：修或说明为什么不需要修
- If fix touches auth/security: add semgrep rule to prevent regression
- If fix touches DB: verify migration doesn't break existing data

### Step 6 — Verify（回归基线对比，super-fix精华）

```bash
# 1. Pre-fix baseline (recorded in Step 1)
python f:/ClaudeFiles/campus_check.py 2>&1 | tee /tmp/pre-fix.log

# 2. Syntax check
python -c "import ast; ast.parse(open('campus_app/server/main_remote.py', encoding='utf-8').read())"
cd campus_go && go build ./...

# 3. Post-fix verification
python f:/ClaudeFiles/campus_check.py 2>&1 | tee /tmp/post-fix.log

# 4. Regression comparison
diff /tmp/pre-fix.log /tmp/post-fix.log
# Rule: 0 new failures → OK. Any new failure → back to Step 5.

# 5. Search for same bug pattern in other files
rg -n "<bug_pattern>" --type-add 'code:*.{py,dart,go}' -t code

# 6. If Flutter: flutter analyze  # 0 errors
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
