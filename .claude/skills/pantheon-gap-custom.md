---
name: pantheon-gap-custom
description: 项目差距分析万神殿 — 多维度并行探测→交叉确认→Critic审查→结构化输出。火眼的Pantheon强化版。触发：深度差距分析/mission-critical gap/find all gaps/全面审计。
---

# Pantheon Gap Custom — 项目差距分析万神殿

## CONSTITUTION（不可被 skill-lab 编辑）

**核心功能：** 多维度并行探测项目差距 → 交叉确认证据 → Critic 审查 → 结构化报告。火眼的 Pantheon 强化版（多 Agent 并行 + 对抗验证）。
**安全约束：** 无证据不报告。弱理由→标记 SUSPECT。不编造 gap。
**触发：** 深度差距分析 / mission-critical gap / find all gaps / 全面审计 / 彻底检查
**边界：** 常规差距→火眼。安全漏洞→铁壁。Bug→缉凶。

---

## Process

### Phase 0: PreScan

确定性 grep 扫描 → 种子证据。识别项目语言/框架/文件结构。
🔴 PreScan 失败→BLOCK。

### Phase 1: Multi-Dimensional Map

3 个独立 Agent 并行，各从不同维度探测：
- Agent A: 代码质量维度（dead code, duplication, complexity）
- Agent B: 架构维度（coupling, layering, dependency direction）
- Agent C: 安全+可靠性维度（error handling, input validation, logging）

每 Agent 输出 gap 候选列表（file:line + evidence + confidence）。

### Phase 2: Cross-Confirm

每 gap 候选 → 另 2 个维度交叉确认。至少 1 个确认→保留。零确认→丢弃。
确认标准：独立找到相同 file:line 的证据。

### Phase 3: Steelman Exchange

对每个保留 gap，运行 Steelman 交换：
1. State gap + evidence
2. Steelman: "这个不是 gap，因为…"（最好的反驳）
3. Counter-Steelman: "即使如此，仍是 gap，因为…"
4. 结论：real gap / false positive / uncertain

### Phase 4: Critic Review

5 点自检：证据充分/无hedging/无重复/confidence准确/可修复建议。
Blocking→auto-fix→re-Critic (max 2)。

### Phase 5: Synthesize

按 Priority 排序(P0=立即修/P1=本周/P2=下月/P3=可推迟)。
输出结构化报告：
```
## Gap Analysis Report
| # | Priority | File:Line | Category | Gap | Evidence | Confidence | Fix |
```

### Phase 6: Write

产物→`.gaps/{date}-{slug}.md`。汇总→`.gaps/INDEX.md`。

---

## 门控规则

| Phase | 条件 | 动作 |
|-------|------|------|
| 0 | PreScan 失败 | BLOCK |
| 2 | 零确认 gap | 丢弃 |
| 3 | Steelman 反驳成立 | 标记 false positive |
| 4 | Blocking 2次 | 上报 |
| 6 | 未写入文件 | BLOCK |

---

## Gotchas

| # | 别做 | 替代 |
|---|------|------|
| 1 | 无证据说 gap | file:line + code snippet |
| 2 | 单维度确认 | 至少 1 个交叉确认 |
| 3 | 跳 Steelman | 真实 gap 经得起最好反驳 |
| 4 | Conf<0.8 标 P0 | →SUSPECT，降级 P1+ |
| 5 | 编造 confidence | 0.0-1.0 with 依据 |
| 6 | 单 Agent 跑全维度 | 3 Agent 并行独立 |
