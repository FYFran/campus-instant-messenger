---
name: pantheon-custom
description: 高强度改动万神殿 — 3变体并行生成→任意模型对抗验证→共识合成。触发：重要/关键/mission-critical/pantheon/高强度/核心改动。
---

# Pantheon Custom — 高强度改动万神殿

## CONSTITUTION（不可被 skill-lab 编辑）

**核心功能：** Mission-critical 代码改动。3 变体并行 → 任意模型交叉对抗验证 → 共识合成最优解。
**安全约束：** 至少 2/3 变体一致才采纳。对抗验证发现分歧→回退重生成。不改 CONSTITUTION。
**触发：** 重要 / 关键 / mission-critical / pantheon / 高强度 / 核心改动 / 不能出错
**边界：** 普通改动→caveman:builder。Bug→缉凶。安全→铁壁。

---

## Iron Law

```
单模型单次生成 = 不可信。
3 变体 + 对抗验证 + 共识合成 = 才可信。
分歧不解决 → 不上线。
```

---

## Quick Reference

| full | Phase 1→6 | 3 variants → adversarial verify → synthesize |
| quick | Phase 1→3 | 2 variants only, skip verify |
| safe | Phase 1→6 | 每 Phase 人审 |

---

## Process

### Phase 1: Spec

写 spec.md：需求 + 架构取舍 + 3 个失败模式 + 测试策略。
🔴 无 spec→BLOCK。

### Phase 2: Variant Generation

生成 3 个独立变体（不同 Agent/模型，不同角度）：
- Variant A: 最小改动，最安全
- Variant B: 最优设计，中等风险
- Variant C: 最大胆重构，最高风险

每变体独立 commit。3 变体必须不同——相同→重生成。

### Phase 3: Adversarial Verify

交叉对抗：每变体由另 2 个变体的 generator 审查。
找崩溃点/安全漏洞/边界条件/竞态/性能退化。
🔴 任一变体被 2/2 否决→丢弃。2/3 否决→重生成。

### Phase 4: Consensus

至少 2/3 变体一致→采纳共识方案。
全分歧→回 Phase 2，换模型/换角度重生成。
共识方案=3 变体中最佳部分的合成。

### Phase 5: Synthesize

合并共识方案→单实现。先写测试→确认 FAIL→实现→测试 PASS。
Critic 审查(5 角度:崩溃/安全/简化/边界/竞态)→blocking→auto-fix→re-Critic (max 2)。

### Phase 6: Verify

回归测试 + campus_check + 手动验证关键路径。
🔴 新增失败→回 Phase 5。Masking→回 Phase 4。

---

## 门控规则

| Phase | 条件 | 动作 |
|-------|------|------|
| 1 | 无 spec | BLOCK |
| 2 | 3 变体雷同 | 重生成 |
| 3 | 变体被 2/2 否决 | 丢弃 |
| 3 | 2/3 变体被否决 | 重生成 |
| 4 | 全分歧 | 回 Phase 2 |
| 5 | 测试失败 | BLOCK |
| 6 | 回归新增失败 | 回 Phase 5 |

---

## Gotchas

| # | 别做 | 替代 |
|---|------|------|
| 1 | 单模型单次生成就提交 | 3 变体+对抗验证 |
| 2 | 变体雷同当不同 | 强制不同角度/模型 |
| 3 | 跳过对抗验证 | 每变体被另2个审查 |
| 4 | 分歧不解决就上线 | 共识 2/3 才采纳 |
| 5 | 合成时丢测试 | 先写测试再合成 |
