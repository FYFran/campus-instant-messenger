# 新对话指令

你是皮特。读 `f:\ClaudeFiles\.claude\CLAUDE.md`。

## 当前任务：3 实验判定方向

### 背景

上轮深度思考发现4缺陷 → 写 CORRECTED_PLAN.md → 不用全量设计，先做3个小实验判定方向。

### 实验状态

| Exp | 内容 | 成本 | 状态 |
|-----|------|------|------|
| A | 真实bug可行性 | $0 | ✅ M01-M08已证明可行 |
| B | 螺旋vs线性对比 | $0.15 | 🔄 跑中 (B05/B07/M03) |
| C | "发现真bug"prevalence | $0.50 | 📋 脚本就绪，待跑 |

### 实验 B 判定规则

```
螺旋 > 线性 (type更准+conf更高) → 螺旋方向推进
螺旋 ≈ 线性 (type同+conf同) → 螺旋有hypothesis_chain数据=更可解释, 推进
螺旋 < 线性 (type错+conf低) → 螺旋模型退化, 保留线性链
```

### 实验 C 判定规则

```
bonus ≥3/10 → 评分系统需要bonus维度 (B03/B04是系统性模式)
bonus ≤1/10 → B03/B04是噪音, 不改评分
bonus =2/10 → borderline, 再跑1次T2确认
```

### 关键文件

```
.claude/skills/缉凶.md                → v2.5.1 (production)
.claude/skills/缉凶-v3.0-alpha.md     → 螺旋合同链 (实验)
.claude/benchmarks/bughunt/
  CORRECTED_PLAN.md                    → 修正计划
  bughunt_ab_spiral.js                 → Exp B: A/B对比脚本
  bughunt_bonus_check.js               → Exp C: bonus检测脚本
  bughunt_t2.js                        → T2 workflow (10 bugs)
  per_bug_results.tsv                  → per-bug数据
  results.tsv                          → summary数据
```

### 上次教训

1. 不先做全量设计再做实验 — 先做实验再设计
2. 不为2个样本改系统 — 先测prevalence
3. 不 6 变量一起改 — 逐项验证
4. 螺旋模型假设 LLM 能做假设追踪 — 未验证, Exp B 会回答
