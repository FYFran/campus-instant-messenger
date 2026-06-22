# 新对话指令

你是皮特。读 `f:\ClaudeFiles\.claude\CLAUDE.md` 了解铁律和路由表。

## 当前任务：试剑石 — 最顶级 Skill 质量基准

### 背景（这对话干了什么）

我们建了一个叫 **试剑石 (BugHuntBench)** 的东西 — 全球第一个测 Agent Skill 文本质量的基准。
不是测模型（SWE-bench 干这个），是测 .md 文件让同一个 LLM 表现更好还是更差。

**三体共生架构：**
- **铸剑炉 (forge)**: 优化 skill 文本
- **试剑石 (BugHuntBench)**: 盲测 skill 质量
- **Bug 矿场**: 从 git history 挖新 bug，持续供给

**闭环：** 铸剑炉改 skill → 试剑石测 → 发现盲区 → Bug矿场生成对应新 bug → 试剑石变难 → 铸剑炉被迫再优化

### 试剑石组件清单

| 文件 | 功能 | 状态 |
|------|------|------|
| `bughunt_harness.py` | 核心库 — bug解析/评分/结果 | ✅ |
| `auto_scorer.py` | 7维评分 + LLM judge prompt | ✅ |
| `bughunt_ci.py` | CI门禁 — 3层阈值检查 | ✅ |
| `bughunt_run.py` | 完整Runner | ✅ |
| `bughunt_final.js` | Claude Code Workflow — 全自动跑分 | ✅ 主力 |
| `bug_injection.py` | Bug注入系统 (行替换→git checkout还原) | ✅ |
| `verify_fix.py` | 执行验证引擎 | ✅ 基础版 |
| `security_gate.py` | CCV跨会话检测 + 答案审计 + trap bugs | ✅ |
| `growth_engine.py` | 6触发自动进化 + git history挖矿 | ✅ |
| `migrate_v2.py` | v1→v2 答案分离迁移 | ✅ 已执行 |
| `bughunt.ps1` | PowerShell CLI入口 | ✅ |

### Bug 库结构 (v2 答案物理分离)

```
bugset/
  B01/{desc.md, truth.md, verify.sh}    ← agent只读desc.md
  B02/{desc.md, truth.md, verify.sh}    ← 评分器读truth.md
  ...
  B10/{desc.md, truth.md, verify.sh}
  README.md
bugs_old_v1/    ← v1备份 (描述+答案同文件, 已弃用)
```

### 35个Bug覆盖 (2026-06-22 扩容: 10→35)

| ID | Type | 语言 | 注入 | 场景 |
|----|------|------|------|------|
| B01 | T0 | Go | ❌ | 空DB→500 (rows.Err缺失) |
| B02 | T1 | Go | ✅ | 并发报名重复 (ON CONFLICT移除) |
| B03 | T2 | Go | ❌ | 学院权限部分匹配 (strings.Contains) |
| B04 | T3 | Python | ❌ | 时长截断 (int vs round) |
| B05 | T4 | Go | ❌ | nginx proxy_pass错端口 |
| B06 | T5 | Go | ✅ | 状态机卡pending (NULL default) |
| B07 | T6 | Mixed | ❌ | Go版本NULL Scan差异 |
| B08 | T7 | Go | ❌ | NOT_A_BUG (产品设计) |
| B09 | T1 | Python | ❌ | missing await (coroutine未执行) |
| B10 | T3 | Go | ✅ | N+1查询 (子查询移除) |

### 缉凶 Skill 进化数据

```
版本      缉凶    裸跑    Δ       T-Type  L3-REAL  说明
v1.2    88.8%   77.5%  +11.3%   8/10    8        负面提示词→虚高
v2.0    78.8%   87.5%   -8.7%   6/10    5        答案分离+纯正面→诚实
v2.1    86.3%   81.3%   +5.0%   8/10    7        分类决策树+正面化→回升
v2.2     ??.?%   ??.?%   +?.?%   ?/10    ?        T5/T3决策流修复+CF强化 (待跑分)
```

**v2.2 改进点 (缉凶.md, 4处编辑):**
- 决策流重排: T5(卡状态) 提到 T3(无报错) 前面 — B06 误判修复
- T5 行加 "误判为 T3" 警告
- Gotchas +7,+8: T3 CF 必须含数值对比(修前=7.0 vs 修后=10.0)
- Worked Examples +T3(强CF数据对比) +T5(分类排除T3)
```

**v2.1 改进点 (缉凶.md):**
- 分类段加决策流 (症状→Type→证据)
- Gotchas 从 "别做X" 改成 "做X" (正面化)
- Red Lines 从 "违反=无效" 改成 "必须做的事+证明"
- 加了 T1/T6/T7 的 Worked Example (原来只有 T0)

**剩余弱点:**
- B01: agent被注入的 `// INJECT-B10` 注释误导 (已修 — 改名为 INJECT- 去掉 BUG 关键词)
- B06: T5→T3 误判 (状态机 vs 无报错 — 决策流还不够细)
- B04: CF 和 evidence 弱 (Judge给0分)

### 试剑石评分体系 (8分制)

| 维度 | 分值 | 评分方式 |
|------|------|---------|
| T-Type | 1 | 规则 (精确匹配) |
| 链完整 | 1 | 规则 (7步非空) |
| 证据 | 1 | LLM Judge (Sonnet) |
| 根因 | 2 | LLM Judge |
| CF | 1 | LLM Judge |
| 修复 | 1 | 规则 (长度+关键词) |
| 轨迹 | 1 | 规则 |
| L3定性 | — | REAL/REAL*/TEMPLATE/WRONG |

### 2026 大佬研究精华（我们学的）

1. **Guardrails Beat Guidance (arXiv:2604.11088)**: 负面约束>正面指令。提示词里说"禁止读XX"=告诉agent XX存在。→ 答案隔离靠物理手段，不靠提示词。
2. **Compliance Gap (arXiv:2605.01771)**: LLM口头答应10/10，执行0/10。→ L3防骗标注。
3. **SWE-bench死了**: 2026.02被OpenAI弃用 — 静态题库3年必死。→ 成长引擎+持续挖矿。
4. **CCV (2026.03)**: 跨会话检测背答案 — 输出完全一致=污染。→ security_gate.py。
5. **AgentBeats (2026)**: 把benchmark做成agent，A2A+MCP协议。→ 我们的Judge Agent模式。
6. **Goodhart's Law**: 当度量成为目标，就不再是好度量。→ 评分公式不公开 + trap bugs。
7. **Co-evolution trap**: 铸剑炉和试剑石在封闭系统里共同进化 → 局部最优。→ hold-out验证集 + 跨项目泛化。
8. **经济可持续**: HAL跑一次$40K。→ 分层管线 (quick$0/full$0.5/verify$3/audit$20)。

### 试剑石独有优势（没人做过）

- 测 Skill 文本质量，不是模型 — 品类开创
- 三体共生闭环 — 持续自我进化
- 6 触发成长引擎 — SWE-bench 没有这个
- 跨模型 Judge — Sonnet评DeepSeek，避免同家族偏见

### 还差什么（优先级排序）

1. ~~**扩容 Bug 库**~~ — ✅ 35 bugs (B01-B35), T0-T7全覆盖, Go/Python/Dart/Mixed
2. **多项目支持** — tokenline/ 目录, generic-go/ 目录 (B27/B28已是tokenline bug)
3. **跨项目泛化检测** — hold-out验证集, OVERFIT_PROJECT告警
4. **执行验证 (worktree隔离)** — agent fix → git worktree → apply → 跑真实测试
5. **多轮跑积累数据** — 成长引擎的6触发才有足够信号
6. **缉凶再优化** — B06 T5识别 + B04 CF/evidence加强
7. **多 Skill 排行榜** — 缉凶 vs 铁壁 vs 火眼 vs 裸跑

### 跑 Workflow 的命令

```powershell
# 清理注入
cd f:/ClaudeFiles; git checkout -- campus_go/internal/handlers/activities.go

# 跑 benchmark (Claude Code 内)
Workflow({scriptPath: "f:/ClaudeFiles/.claude/benchmarks/bughunt/bughunt_final.js"})
```

### 关键设计原则（别推翻）

- 答案物理分离 — 不是提示词约束
- 纯正面提示词 — 不出现"禁止"、"不要"
- 注入用行替换 + git checkout还原 — 不用git patch
- 跨模型Judge — Sonnet评DeepSeek
- ≤4处修改 per skill optimization round
- skill <200行 / <3000 token
- 评分公式不公开细节

### 项目骨架回顾

```
f:/ClaudeFiles/              → 皮特主项目
.claude/skills/缉凶.md        → 缉凶 v2.1 (187行, 分类决策树)
.claude/skills/forge/    → 铸剑炉 v0.3
.claude/benchmarks/bughunt/  → 试剑石 (本对话全部产出)
campus_go/                   → Go后端 (bug来源)
campus_app/                  → Flutter+Python (bug来源)
.fixes/                      → 历史修复记录
bug-patterns.md              → Bug模式库
```

## 新对话第一步

读 `f:\ClaudeFiles\.claude\benchmarks\bughunt\DESIGN_v2.md` 了解完整设计蓝图。
然后读 bugset/README.md 了解 bug 库结构。
Bug 库已扩容至 35 bugs (2026-06-22)。从"多项目支持"或"缉凶再优化"开始。
