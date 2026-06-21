---
name: campus-bug-hunt
description: 系统化 Bug 排查引擎。零依赖内核(TIER1 Read+Grep)为主，外部工具(TIER2 codegraph/SSH/firecrawl)可选升级。7步门控→根因定位→手术修复→回归验证。触发：bug/fix/not working/error/crash/broken/报错/不工作。
---

# Campus Bug Hunt — 系统化 Bug 排查

## CONSTITUTION（不可被 skill-lab 编辑）

**核心功能：** 系统化 Bug 排查：证据收集→追踪→根因定位→手术修复→验证→报告。不修症状只修根因。
**安全约束：** 绝不未复现就修。3+失败=质疑架构。绝不只修一个后端（Python+Go 必须同时检查）。
**触发：** bug / fix / not working / error / crash / broken / 报错 / 不工作 / bug report / issue

---

## PREFLIGHT（每次必跑，零依赖）

```powershell
# 检测可用工具 + OS
$tools = @{}
$tools.codegraph = [bool](Get-Command codegraph -ErrorAction SilentlyContinue)  # MCP tool
$tools.rg = [bool](Get-Command rg -ErrorAction SilentlyContinue)
$tools.ssh = Test-Path "$env:USERPROFILE\.ssh\id_*"
$tools.firecrawl = $true  # MCP tool, always available in this environment
$tools.python = [bool](Get-Command python -ErrorAction SilentlyContinue)
$tools.go = [bool](Get-Command go -ErrorAction SilentlyContinue)
$tools.flutter = [bool](Get-Command flutter -ErrorAction SilentlyContinue)
$tools.os = if ($IsLinux) { 'linux' } elseif ($IsMacOS) { 'mac' } else { 'windows' }
Write-Host "CAPABILITY: $($tools | ConvertTo-Json -Compress)"
```

每步标注来源层级：`[TIER1]` = 零依赖原生命令 / `[TIER2]` = 外部工具升级 / `[SKIP]` = 两层都不可用则跳过并标记 PARTIAL。

TIER1 命令自动适配：
- **Windows:** `Get-ChildItem -Recurse ... | Select-String ...`
- **Linux/Mac:** `grep -rnE 'pattern' --include='*.py' --include='*.go' .`
- **通用（rg 可用时优先）：** `rg -n 'pattern' -t py -t go`

---

## Quick Reference

| 模式 | 触发 | 步骤 | 收敛 |
|------|------|------|------|
| **full** | `fix {bug}` (默认) | Step 0→1→2→3→4→5→6→7 | 2 pass 零新发现=停 |
| **quick** | `quick check {bug}` | Step 1→4 only | 1 pass |
| **safe** | 安全/权限/auth相关 bug | full 流程，Step 5 前强制 CHECKPOINT | 2 pass |

---

## Process

### Step 0 — 三源搜索 [TIER1/TIER2]

**TIER1（零依赖）：**
1. 读 `f:/ClaudeFiles/bug-patterns.md` — 这个 bug 以前修过吗？
2. `rg -n "<error_keyword>" --type-add 'code:*.{py,go,dart}' -t code` — 项目内搜相似错误

**TIER2（可选升级）：**
1. `firecrawl_search` 搜最新方案
2. `firecrawl_research_search_papers` 搜学术方案

至少 1 个来源返回结果或确认 bug-patterns 无匹配。

### Step 1 — 收集证据 [TIER1/TIER2]

**TIER1（零依赖）：**
```bash
# 本地日志（如存在）
cat f:/ClaudeFiles/campus_app/server/logs/*.log 2>$null || echo "no local logs"

# campus_check.py 诊断
python f:/ClaudeFiles/campus_check.py 2>&1

# API health（curl 几乎永远可用）
curl -s http://139.196.50.134/api/health 2>$null || echo "server unreachable"
```

**TIER2（SSH 可选）：**
```bash
ssh root@139.196.50.134 "journalctl -u campus-app --no-pager -n 100"
ssh root@139.196.50.134 "tail -50 /app/audit.log"
ssh root@139.196.50.134 "tail -50 /var/log/nginx/error.log"
```

🔴 **CHECKPOINT:** 无法复现 bug → BLOCK，不继续。要求提供复现步骤。

### Step 2 — 追踪代码路径 [TIER1/TIER2]

**TIER1（零依赖，永远可用）：**
```bash
# 从症状关键词开始，逐层追踪
rg -n "function_name\|endpoint_path\|error_message" --type-add 'code:*.{py,go,dart}' -t code
# Read 关键文件，手动追踪调用链
```

**TIER2（codegraph 升级）：**
1. `codegraph_context("<module>")` — 理解功能模块
2. `codegraph_trace("<from>", "<to>")` — 追踪完整调用路径
3. `codegraph_callers("<function>")` — 找所有调用者
4. `codegraph_impact("<symbol>")` — 改动影响面

追踪链示例：
```
Bug: "报名活动 500"
→ rg -n "signup\|报名\|activity" → 定位 handler
→ Read handler → 追踪到 SQL query
→ Step 4 分析根因
```

🔴 **CHECKPOINT:** 没追踪完数据流就提方案 → Red Flag，回 Step 2。

### Step 3 — 双后端检查 [TIER1]

本项目 Python（生产）+ Go（建设中）必须同时检查：

| 后端 | 文件 | 状态 |
|------|------|------|
| Python | `campus_app/server/main_remote.py` | 生产 `/app/main.py` |
| Go | `campus_go/main.go` + `handlers/` | 建设中 |

**TIER1（零依赖）：**
```bash
# 在 Python 中找到 bug 模式后，搜 Go 中相同模式
rg -n "<bug_pattern>" campus_go/ --type go
# 反之亦然
rg -n "<bug_pattern>" campus_app/server/ --type py
```

`deploy.py` 映射 `main_remote.py` → `/app/main.py` — 确认服务器实际运行的文件。

### Step 4 — 找根因（非症状）

1. **复现** — 精确步骤 + 输入 + 期望 vs 实际输出
2. **隔离** — 二分法：注释一半逻辑，bug 还在吗？
3. **单变量验证** — 一次改一个变量，重测
4. **根因陈述** — 根本原因，非近因触发器。格式：`{机制} → {因果链} → {症状}`

示例：
- ❌ "500 on signup" → ✅ "FOR UPDATE 缺失导致竞态，unique constraint violation"
- ❌ "Can't login" → ✅ "refresh token hash 列 NULL after migration, JWT verify 失败"
- ❌ "Page blank" → ✅ "setState after widget disposed, Flutter 生命周期 bug"

### Step 5 — 修复 + Critic 挑刺

手术式修改：只改修根因的最小行数。

**修复后 Critic 强制挑刺（super-fix 模式）：**
```
Agent: critic
审查刚才的改动。逐条列出：崩溃点、简化方案、安全隐患、边界条件、异步竞态。
"没问题" = Critic 失职，重跑。
```

Critic 每条问题：修或说明为什么不需要修。
- 涉及 auth/security → 加 semgrep 规则防回归
- 涉及 DB → 验证 migration 不破坏已有数据

🔴 **CHECKPOINT Step 5:** 改动超 50 行 → 暂停确认。3+ 次修复失败 → Iron Law: 停止，质疑架构。

### Step 6 — 回归验证

```bash
# 1. Pre-fix baseline（Step 1 已记录）
python f:/ClaudeFiles/campus_check.py 2>&1 | tee /tmp/pre-fix.log

# 2. Syntax check
python -c "import ast; ast.parse(open('campus_app/server/main_remote.py', encoding='utf-8').read())"
cd campus_go && go build ./... 2>&1

# 3. Post-fix
python f:/ClaudeFiles/campus_check.py 2>&1 | tee /tmp/post-fix.log

# 4. Regression diff — 0 新增失败 = OK
diff /tmp/pre-fix.log /tmp/post-fix.log

# 5. 搜同 bug 模式
rg -n "<bug_pattern>" --type-add 'code:*.{py,go,dart}' -t code

# 6. Flutter（如有改动）
cd campus_app && flutter analyze 2>&1
```

🔴 **CHECKPOINT:** 回归 diff 有任何新增失败 → 回 Step 5。campus_check.py 通过 ≠ 功能正确 — 手动复现确认。

### Step 7 — 报告

```markdown
## Bug Report — {title}

**Environment:** {production/local/file}
**Symptom:** {用户看到的}
**Root Cause:** {1-2 句，根本原因}
**Fix:** {file:line-range} — {1 句改动说明}
**Verified:** {campus_check.py OK / flutter analyze OK / manual test OK}
**Regression check:** {同模式发现 {n} 处 / 无其他实例}
**Mode:** {TIER1/TIER2} | **Steps completed:** {n}/7
```

---

## Convergence Loop

完成后重跑 Step 1→2（证据收集+追踪）。两轮零新发现 → DONE。最多 3 轮。
同 bug 连续 2 轮重现 → severity +1，标记 PERSISTENT。

---

## Iron Law（systematic-debugging 精华）

```
NO FIX WITHOUT ROOT CAUSE FIRST.
3+ fixes fail → STOP. Question architecture, don't keep patching.
Micro-tuning when micro-tuning doesn't work = waste time + add bugs.
```

## Red Flags（任一出现 → 停，回 Step 1）

- "快速修一下，之后再调查"
- "试试改 X 看行不行"
- "我大概知道什么原因"（但没验证）
- 没追踪完数据流就提方案
- "再试一次修复"（已 2+ 次）
- 每次修复暴露新问题

## No-Hedge Rule

禁止：might / could consider / maybe / possibly / I think / probably / likely / try changing
每条 finding 必须有 file:line + concrete reason。不确定 → 标记 ⚪ SUSPECT，不编造。

---

## Gotchas（真实踩坑 — 排查前对照）

| # | 别做 | 替代 |
|---|------|------|
| 1 | SSH 不通就卡住 | TIER1: 读本地日志 + curl health。SSH 是 TIER2 升级 |
| 2 | codegraph 索引过期还用 | 先 `rg` 验证 codegraph 结果。不一致 → 信 rg |
| 3 | 只修 Python 不查 Go | Step 3 必跑。Go 未部署 ≠ 无 bug |
| 4 | 修症状不修根因 | "500 error" → 不加 try/except，追踪到 SQL/竞态/空指针 |
| 5 | campus_check.py 过了就以为 OK | 手动复现确认。自动化测试覆盖有限 |
| 6 | 修完不搜同 bug | rg 搜同模式。项目有并行代码路径 |
| 7 | deploy.py 映射搞错 | 生产 `/app/main.py` ← `main_remote.py`。别修错文件 |
| 8 | Critic 说"没问题" | 无效评估。换角度重跑 Critic |
| 9 | 不读 bug-patterns.md 就动手 | 已知模式秒解。跳过 = 重复踩坑 |
| 10 | 模糊报错直接猜 | Step 1 收集证据。不猜，不假设 |

---

## References

- `f:/ClaudeFiles/bug-patterns.md` — 已知 bug 模式库
- `f:/ClaudeFiles/campus_check.py` — 功能回归验证
- `f:/ClaudeFiles/.claude/skills/campus-code-review.md` — 修复后审查
- `f:/ClaudeFiles/CLAUDE.md` — Agent 路由表
