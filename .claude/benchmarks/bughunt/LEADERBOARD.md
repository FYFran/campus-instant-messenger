# 试剑石 Leaderboard

> 最后更新: 2026-06-22 | 49 bugs, 8 T-Types, 5 languages, 2 projects (campus_go + TokenLine)

## 缉凶 Skill

| Version | Score | T-Type | L3 REAL | Trials | SD | Date |
|---------|-------|--------|---------|--------|-----|------|
| **v2.5** | **95.4%** | **9.3/10** | **8.7/10** | **3** | **±1.9pp** | 2026-06-22 |
| v2.6 GEPA | 90.0% | 8.0/10 | 6.0/10 | 1 | — | 2026-06-22 |
| v3.0-lite | 91.7% | 9.0/10 | 7.7/10 | 3 | ±7.3pp | 2026-06-22 |
| Bare (no skill) | 89.6% | 6.7/10 | 6.0/10 | 3 | ±4.7pp | 2026-06-22 |

**结论: v2.5 封版。v2.6 GEPA 退化 -5.4pp，已回滚。v2.5.1 = v2.5 + F6(T4配置检查) 待验证。**

## v2.5.1 (F6 patch, 当前)

v2.5 + 单一改进: F6 T4 强制配置检查。改动:
- 决策流 Q9: 症状可被配置差异解释 → T4
- F6 致命误判: T4 专属配置检查通过前不许读源码
- T4 3步: config diff / port check / startup log

**待 T2 验证 (3-run)。预期: 95±2pp, T-Type 9+/10。**

## Skill Lift

| Skill | Mean | vs Bare | Verdict |
|-------|------|---------|---------|
| 缉凶 v2.5 | 95.4% | +5.8pp | ✅ Significant |
| 缉凶 v2.6 GEPA | 90.0% | +0.4pp | ❌ Regressed |
| 缉凶 v3.0-lite | 91.7% | +2.1pp | ❌ Regressed |

## GEPA 实验记录

| 改动 | 预期 | 实际 | 结论 |
|------|------|------|------|
| 合同链重排序 ([分类]→[证据] → [证据]→[分类]) | +1-2pp | -5.4pp | ❌ 破坏工作流 |
| F7 (断言前搜索) | +0.5pp | — | ❌ 过度约束 |
| F8 (跨bug RESET) | +0.5pp | — | ❌ 过度约束 |
| F6 (T4配置检查) | +0.5pp | 待验证 | ⏳ 单独保留 |

**教训: GEPA 合同链重排序是主退化源。单个 F-rule 改动安全，结构改动危险。**

## T1 Classification (49-bug)

| Method | Score | In-Sample | Hold-Out (10 hardest) | Gap | Cost |
|--------|-------|-----------|----------|-----|------|
| 1 agent batch | 32/49 (65%) | — | — | — | $0.03 |

Hold-out = B16,B18,B25,B28,B31,B33,B36,B38,M05,T03. Includes 2 traps.

## Trap Bugs

| Bug | Agent → Truth | Result |
|-----|---------------|--------|
| B36 | T1 → T7 (rate limiter NOT_A_BUG) | ✅ Deceived |
| B38 | T0 → T5 (lazy init state issue) | ✅ Deceived |

## Bug Library

| Source | Count | Types |
|--------|-------|-------|
| B01-B35 | 35 | T0-T7 campus_go |
| B36-B38 | 3 | Trap bugs |
| M01-M08 | 8 | Git-mined (real commits) |
| T01-T03 | 3 | TokenLine |
| **Total** | **49** | **2 projects, 5 languages**

## Cost Efficiency

| Tier | Cost/run | Bugs | Cost/bug | Purpose |
|------|----------|------|----------|---------|
| T0 | $0 | — | $0 | Pre-commit rule gate |
| T1 | $0.03 | 46 | $0.0007 | T-Type classification |
| T2 | $0.50 | 10 | $0.05 | Full investigation + judge |
| T3 | $5.00 | 10 | $0.50 | Cross-model + bare baseline |

## Key Findings

1. **Skills reduce variance, not just raise the ceiling.** 缉凶 SD = ±1.9pp vs Bare SD = ±4.7pp (2.5x more stable)
2. **Worked examples are load-bearing.** 砍掉 → 方差暴增 4x (v3.0 SD=±7.3pp)
3. **Structural changes > incremental F-rules.** 合同链重排序退步远大于单个 F-rule 改进
4. **GEPA reflection works for diagnosis, not for prescription.** Teacher 分析失败模式准确；但 7 项改动全应用导致退化。应逐项验证
