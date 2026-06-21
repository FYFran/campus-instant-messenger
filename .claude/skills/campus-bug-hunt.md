---
name: campus-bug-hunt
description: 系统化 Bug 排查引擎。零依赖内核(TIER1 Read+Grep)为主，外部工具(TIER2 codegraph/SSH/firecrawl)可选升级。7步门控→根因定位→手术修复→回归验证。触发：bug/fix/not working/error/crash/broken/报错/不工作。
---

# Campus Bug Hunt

## CONSTITUTION（不可被 skill-lab 编辑）

**核心功能：** 系统化 Bug 排查：证据→追踪→根因→手术修复→验证→报告。不修症状。
**安全约束：** 绝不未复现就修。3+失败=质疑架构。绝不只修一个后端（Python+Go 同时查）。
**触发：** bug / fix / error / crash / broken / 报错 / 不工作 / not working

---

## PREFLIGHT（每次必跑）

```powershell
$cap = @{}
$cap.codegraph = [bool](Get-Command codegraph -ErrorAction SilentlyContinue)
$cap.rg = [bool](Get-Command rg -ErrorAction SilentlyContinue)
$cap.ssh = Test-Path "$env:USERPROFILE\.ssh\id_*"
$cap.python = [bool](Get-Command python -ErrorAction SilentlyContinue)
$cap.go = [bool](Get-Command go -ErrorAction SilentlyContinue)
$cap.os = if ($IsLinux) { 'linux' } elseif ($IsMacOS) { 'mac' } else { 'windows' }
Write-Host "CAPABILITY: $($cap | ConvertTo-Json -Compress)"
```
TIER1 命令自动适配：Windows=`Select-String`，Linux/Mac=`grep -rnE`，rg 可用时优先 `rg -n`。

每步标注：`[TIER1]` 零依赖 / `[TIER2]` 外部工具 / `[SKIP]` 两层都不可用。

---

## Quick Reference

| 模式 | 触发 | 步骤 | 收敛 | 门控 |
|------|------|------|------|------|
| **full** | `fix {bug}` | Step 0→7 | 2 pass 零新发现 | 全 CHECKPOINT |
| **quick** | `quick check` | Step 1→4 | 1 pass | Step 1 only |
| **safe** | auth/security bug | full | 2 pass | Step 5 强制确认 |

---

## Process

### Step 0 — 三源搜索

**TIER1:** (1) 读 `f:/ClaudeFiles/bug-patterns.md` — 以前修过？(2) `rg -n "<keyword>" --type-add 'code:*.{py,go,dart}' -t code`
**TIER2:** firecrawl_search + firecrawl_research_search_papers

门控：至少 1 来源有结果或确认 bug-patterns 无匹配 → CONTINUE。

### Step 1 — 收集证据

**TIER1:** `python f:/ClaudeFiles/campus_check.py 2>&1` + `curl -s http://139.196.50.134/api/health`
**TIER2:** `ssh root@139.196.50.134 "journalctl -u campus-app --no-pager -n 100"` + audit/nginx 日志

🔴 **CHECKPOINT:** 无法复现 bug → **BLOCK**。必须用户提供复现步骤。可复现 → PASS。

### Step 2 — 追踪代码路径

**TIER1:** `rg -n "<function|endpoint|error>" -t py -t go -t dart` → Read 关键文件 → 手动追踪调用链
**TIER2:** codegraph_context → codegraph_trace → codegraph_callers → codegraph_impact

🔴 **CHECKPOINT:** 未追踪完数据流就提方案 → Red Flag，回 Step 2。追踪完成 → PASS。

### Step 3 — 双后端检查

| 后端 | 关键文件 | 部署 |
|------|---------|------|
| Python | `campus_app/server/main_remote.py` | → `/app/main.py` |
| Go | `campus_go/main.go` + `handlers/` | 建设中 |

**TIER1:** `rg -n "<bug_pattern>" campus_go/ -t go` 和 `campus_app/server/ -t py` 交叉搜。
门控：两个后端都检查过 → PASS。部署映射用 `deploy.py` 确认。

### Step 4 — 找根因（非症状）

1. **复现** — 精确步骤 + 期望 vs 实际
2. **隔离** — 二分法，注释一半逻辑
3. **单变量验证** — 一次改一个变量
4. **根因陈述** — 格式 `{机制} → {因果链} → {症状}`
   - ❌ "500 on signup" → ✅ "FOR UPDATE 缺失→竞态→unique violation"
   - ❌ "Page blank" → ✅ "setState after widget disposed"

### Step 5 — 修复 + Critic

手术式修改：最小行数修根因。

**Critic 强制挑刺:**
```
Agent: critic
审查改动。逐条列：崩溃点、简化方案、安全隐患、边界条件、异步竞态。
"没问题" = Critic 失职，重跑。
```

🔴 **CHECKPOINT:** 改动 >50 行 → 暂停确认。3+ 修复失败 → **BLOCK** (Iron Law: 质疑架构)。Critic 有未解决问题 → 修后再跑。

### Step 6 — 回归验证

```bash
python f:/ClaudeFiles/campus_check.py 2>&1 | tee /tmp/pre-fix.log
python -c "import ast; ast.parse(open('campus_app/server/main_remote.py', encoding='utf-8').read())"
cd campus_go && go build ./...
# Fix applied...
python f:/ClaudeFiles/campus_check.py 2>&1 | tee /tmp/post-fix.log
diff /tmp/pre-fix.log /tmp/post-fix.log  # 0 新增失败 = OK
rg -n "<bug_pattern>" -t py -t go -t dart  # 搜同 bug 模式
```

🔴 **CHECKPOINT:** diff 有任何新增失败 → 回 Step 5。campus_check.py 通过 ≠ 功能正确 → 手动复现确认。

### Step 7 — 报告

```markdown
## Bug Report — {title}
**Environment:** {prod/local/file} | **Mode:** {TIER1/TIER2} | **Steps:** {n}/7
**Symptom:** {用户看到的}
**Root Cause:** {根本原因，1-2 句}
**Fix:** {file:line-range} — {改动说明}
**Verified:** {check OK / flutter OK / manual OK}
**Regression:** {同模式 {n} 处 / 无}
```

---

## 门控规则

| CHECKPOINT | 条件 | 动作 |
|-----------|------|------|
| Step 1 | 无法复现 | **BLOCK** — 等用户给复现步骤 |
| Step 2 | 数据流未追踪完 | **BLOCK** — 回 Step 2 继续追踪 |
| Step 5 | 改动 >50 行 | **BLOCK** — 确认范围 |
| Step 5 | 3+ 修复失败 | **BLOCK** — Iron Law: 质疑架构 |
| Step 5 | Critic 发现未解决问题 | **BLOCK** — 修后再跑 |
| Step 6 | 回归有新失败 | **BLOCK** — 回 Step 5 |

---

## Iron Law

```
NO FIX WITHOUT ROOT CAUSE FIRST.
3+ fixes fail → STOP. Question architecture.
Micro-tuning failure → micro-tuning more = waste + new bugs.
```

## Red Flags（任一 → 停，回 Step 1）

- "快速修一下"/"试试改 X"/"大概知道原因"(未验证)
- 未追踪完数据流就提方案
- "再试一次"(已 2+ 次)
- 每次修复暴露新问题

## No-Hedge

禁止: might / could / maybe / I think / probably / try changing
每条 finding: file:line + concrete reason。不确定 → ⚪ SUSPECT，不编造。

## Convergence

重跑 Step 1→2。两轮零新发现 → DONE。最多 3 轮。同 bug 连续 2 轮重现 → severity +1, PERSISTENT。

---

## Gotchas

| # | 别做 | 替代 |
|---|------|------|
| 1 | SSH 不通就卡住 | TIER1: 本地日志 + curl。SSH 是 TIER2 |
| 2 | 信过期的 codegraph 索引 | `rg` 先验证。不一致 → 信 rg |
| 3 | 只修 Python 不查 Go | Step 3 必跑。未部署 ≠ 无 bug |
| 4 | 加 try/except 掩盖 500 | 追踪到 SQL/竞态/空指针根因 |
| 5 | campus_check.py 过 = 好了 | 手动复现。自动化覆盖有限 |
| 6 | 修完不搜同 bug | rg 搜同模式。并行代码路径 |
| 7 | 修错文件(没查 deploy.py) | 生产 `/app/main.py` ← `main_remote.py` |
| 8 | 接受 Critic "没问题" | 无效。换角度重跑 |
| 9 | 不读 bug-patterns.md | 已知模式秒解。跳过 = 重复踩坑 |
| 10 | 模糊报错直接猜 | Step 1 先收集证据 |
