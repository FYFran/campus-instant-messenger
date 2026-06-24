# Skill 统一模板 v1.0

> 基于 2026 研究：Guardrails Beat Guidance (arXiv 2604.11088) + GEPA (ICLR 2026) + Skill Shadowing (arXiv 2605.24050) + Skill Drift (arXiv 2605.10990) + Library Drift (arXiv 2605.19576) + senpAI (XP 2026)

## 铁律

1. **负面约束 > 正面指令。** 写"不要X"，不写"你要Y"
2. **Gotchas 是最有价值的。** 来自真实失败，不是理论
3. **简短。** 核心内容 ≤80 行。细节放 references/
4. **可成长。** 每次使用后记录学到了什么

## 模板

```markdown
---
name: <skill-name>
description: <一句话 + 触发关键词。给模型看的，不是给人看的>
model: <适用模型>  # 不同模型效果不同 (arXiv 2605.30723)
conflicts: [<已知冲突的skill>]  # Skill Shadowing 预防
lifecycle: active  # active | stale(30天不用) | archived(90天)
created: <YYYY-MM-DD>
updated: <YYYY-MM-DD>
review_after: <YYYY-MM-DD>  # 强制重审日期
---

# <Skill 名称> — <一句话描述>

## CONSTITUTION（不可被 forge 编辑）

### 核心功能
- [这个 skill 做什么，1-2 句话]

### 红线（绝对不能做的事）
- [负面约束 1]
- [负面约束 2]
- [负面约束 3]

### 边界
- **该用我的时候：** [触发场景]
- **不该用我的时候：** [排除场景]
- **模型依赖：** [哪个模型上验证过，换模型要重评]

---

## Gotchas（来自真实失败 — 最高信号密度）

> 每一条来自实际出过的事。不是理论。

| # | 症状 | 根因 | 教训 |
|---|------|------|------|
| 1 | <你看到什么> | <真正原因> | <以后怎么防止> |
| 2 | ... | ... | ... |

---

## 核心行为

<简短的行为描述，负面约束格式。≤20 行。>

---

## 可成长性（每次使用后执行）

修复/任务完成后，问自己：
1. 「本次有没有合同未覆盖的误判模式或质量陷阱？」
2. 「有什么我以为是常识但 agent 不知道的？」
3. 「Gotchas 表要不要加一条？」

→ YES → 写 `.fixes/{date}-pattern-candidate.md`（描述模式+症状信号+建议改进）
→ forge 下次 evolve 循环自动采集提案
→ 你来确认要不要注入

---

## 验证

每次改完，跑：
```
BugHuntBench quick {skill-name}  →  <30s，零成本
BugHuntBench full {skill-name}   →  ~$0.15，确认没降分
```

---

## 参考

- 详细规则 → `references/`
- 历史失败 → `.fixes/`
- 评分记录 → `.claude/benchmarks/bughunt/scores/`
```

## 各 Skill 状态

| Skill | 当前 | Phase 0 动作 |
|-------|------|------------|
| 缉凶 | v2.8.1 封版 | 精简到模板格式，补 lifecycle 元数据 |
| 铁壁 | 通用，Phase 5 未完成 | 精简+补 Gotchas+补 lifecycle |
| code-review | campus 绑定 | **去 campus 化** + 精简 |
| deploy | campus 绑定 | **去 campus 化** + 精简 |
| quality-gate | campus 绑定 | **去 campus 化** + 精简 |
| red-team | campus 绑定 | **去 campus 化** + 精简 |
| forge | 通用 | 补 Gotchas+lifecycle，加 GEPA 风格 |
| 火眼 | 通用，0 评分 | 按模板重建 |
