# 新对话指令

你是皮特。读 `f:\ClaudeFiles\.claude\CLAUDE.md` 了解铁律和路由表。

## 当前任务：试剑石 — 继续推进

### 2026-06-22 下午成果

**缉凶 Skill: v2.1(86.3%)→v2.5(T-Type 15/15)**
- 4 轮优化，3 篇 2026 论文驱动(ContraPrompt+ForcedDepth+Guardrails Beat)
- 新增：T3 门禁(Red Line 0)、致命误判库(F1-F5)、8 个完整 Worked Example
- 文件：`.claude/skills/缉凶.md` (281 行)

**试剑石基础：**
- Bug 库：10→35 bugs (B01-B35), T0-T7 全覆盖
- 4 层管线：Tier0($0)→Tier1($0.01)→Tier2($0.50)→Tier3($5)
- 改名：`skill-lab`→`forge`(铸剑炉)
- Master Plan：`.claude/benchmarks/bughunt/MASTER_PLAN.md`

**关键发现：**
- 分类稳定：Tier1 3 次全 10/10, Hold-out 5/5
- 调查方差 20pp：DeepSeek 每次走不同代码路径
- 评分系统已修：语义匹配替代硬关键词
- 注入串行化已修：每 bug 独立周期
- Batch judge 验证：83% 一致，省 90% cost

### 打开问题

1. **T2 评分系统修复后未验证** — 刚改完，跑中被打断
2. **35 bug 全量从未跑过** — 所有优化在 10 bug 上
3. **growth_engine 挖矿未运行** — 从 .fixes/ 和 git log 挖新 bug
4. **Trap bugs 未实现** — MASTER_PLAN Ring 5
5. **过拟合自动化未做** — 需定时 hold-out 触发

### 立即开始

```
1. 跑 T1 ($0.01) → 确认 T-Type 仍是 10/10
2. 跑 T2 (已修评分) → 看新评分是否稳定
3. 跑 hold-out → 确认 5/5 仍在
4. 跑 growth_engine mine → 挖 5-10 新 bug
5. 35 bug 全量一次性跑 → 真实基线
```

### 跑 Workflow 命令

```
Workflow({scriptPath: "f:/ClaudeFiles/.claude/benchmarks/bughunt/bughunt_t1.js"})
Workflow({scriptPath: "f:/ClaudeFiles/.claude/benchmarks/bughunt/bughunt_t2.js"})
```
