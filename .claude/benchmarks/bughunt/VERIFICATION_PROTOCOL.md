# v2.5.1 验证协议 — 人类智慧 × AI 智慧

> 目标：用最少钱，得最可靠结论。每步有理由，每钱有回报。

## 哲学

人类智慧 = 设计实验、判结果、知边界
AI 智慧 = 执行一致、算统计、找模式
结合 = 人设计 what/why，AI 执行 how，人验证 so-what

---

## Phase 1: Per-Bug 基准 ($0)

**做什么：** 跑 v2.5.1 × 10 bugs × per-bug 详细评分。

**为什么：** 现在只有 v2.1 per-bug 数据。v2.5 只知总分 (95.4%)，不知哪个 bug 丢分。无法定向改进。

**执行：** 修改 bughunt_t2.js → 输出 per-bug 7维评分到 per_bug_results.tsv。

**成功标准：** 每个 bug 有 score_class/chain/evidence/root/cf/fix 6维数据。

**人类角色：** 审 per-bug 结果，标注 "AI对/错/部分对"。

**成本：** $0 (改脚本)。

---

## Phase 2: v2.5.1 T2 3-Run 验证 ($1.50)

**做什么：** v2.5.1 × T2 × 3 次，测方差。

**为什么：** v2.5.1 = v2.5 + F6。必须证明 F6 没有退化。

**H0 假设：** v2.5.1 ≥ v2.5 (μ≥95.4%)。H1: v2.5.1 < v2.5。

**决策规则：**
- v2.5.1 ≥ 93% 且 gap vs v2.5 < 3pp → 保留 F6，封版 v2.5.1
- v2.5.1 在 90-93% → F6 可疑，跑 ablation (v2.5 再跑 3 次确认基线)
- v2.5.1 < 90% → 回滚 v2.5，标记 F6 FAILED

**人类角色：** 最终裁决。AI 只提供数据。

**成本：** 3 × $0.50 = $1.50。

---

## Phase 3: Hold-Out 差距 ($0.50)

**做什么：** v2.5.1 × 10 hold-out bugs × 1 次。

**为什么：** 10 个最难 bug (B16,B18,B25,B28,B31,B33,B36,B38,M05,T03) 从未跑过 T2。必须测过拟合。

**决策规则：**
- hold-out gap < 5pp → 健康
- hold-out gap 5-10pp → 警告，加 diverse 训练案例
- hold-out gap > 10pp → OVERFIT，强制重选 hold-out + 泛化

**人类角色：** 审 hold-out 失败 case，判断是 "skill 过拟合" 还是 "hold-out 真更难"。

**成本：** 1 × $0.50 = $0.50。

---

## Phase 4: Cross-Model Judge ($1.00)

**做什么：** 同一次 v2.5.1 run → 分别用 deepseek、sonnet、opus 打分。

**为什么：** 现在 judge 和 agent 同模型 (deepseek) → 系统性偏见。独立 judge 揭露盲区。

**成功标准：** 三模型 judge 分数差距 <5pp → judge 可靠。差距 >10pp → judge 有 bias。

**人类角色：** 审三模型分歧最大的 bug，判定谁对。

**成本：** 2 次额外 judge × $0.50 = $1.00。

---

## Phase 5: Human Baseline ($0 但需要时间)

**做什么：** 凡哥手动做 3-5 个 bug (选 T0/T3/T4/T7 各一 + 一个 trap)。

**为什么：** 不知道 95.4% 对人类是什么水平。可能是 80% (AI 已超人类) 也可能是 99% (AI 还有路要走)。

**协议：**
1. 给凡哥 bug 描述 + campus_go 代码
2. 不限时，不限工具
3. 记录：分类 / 根因 / conf / 时间
4. AI 用同样 7 维评分

**人类角色：** 执行者 + 参照系提供者。

**成本：** $0。但需要 1-2 小时专注时间。

---

## 总成本

| Phase | 内容 | 成本 | 必需? |
|-------|------|------|-------|
| P1 | Per-bug 基准 | $0 | ✅ 必需 |
| P2 | T2 3-run | $1.50 | ✅ 必需 |
| P3 | Hold-out | $0.50 | ✅ 必需 |
| P4 | Cross-model | $1.00 | 🟡 建议 |
| P5 | Human baseline | $0 + 时间 | 🟡 建议 |
| **Total** | | **$3.00** | |

---

## 快速决策树

```
T2 3-run ≥93%?
  ├ YES → P3 hold-out
  │   ├ gap <5pp → ✅ 封版 v2.5.1, 跑 P4 cross-model
  │   └ gap ≥5pp → ⚠ OVERFIT, 跑 P5 human baseline 对照
  └ NO (<93%)
      ├ ≥90% → 跑 ablation (v2.5 vs v2.5.1 各 3 次, $3)
      └ <90% → ❌ 回滚 v2.5, F6 单独验证
```

---

## 人类智慧检查点（每 Phase 完后问自己）

1. "这个结果有没有反直觉的地方？"
2. "如果我是 agent，我会犯同样的错吗？"
3. "这个改进真的让 skill 更好，还是只是拟合了 benchmark？"
4. "有没有我们没测但应该测的？"
