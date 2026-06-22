# 新对话指令

你是皮特。读 `f:\ClaudeFiles\.claude\CLAUDE.md`。

## 当前状态：v2.5.1 封版。所有实验完成。

### 最终判定

**Production skill: v2.5.1 (v2.5 + F6 T4配置检查)**
- v2.5 95.4±1.9pp (honest ~91.5%)
- 最低方差 (SD 1.9pp, 2.5x < bare)
- F6 在多种场景下有效 (B05=8/8)

### 实验总结 (3 实验, $1.65)

| Exp | 假设 | 结果 | 判定 |
|-----|------|------|------|
| A: 真实bug | 从git提取真实bug | M01-M08已可行 | ✅ 可行但不紧急 |
| B: 螺旋模型 | 螺旋>线性 | 线性3/3, 螺旋2/3 | ❌ 线性保留 |
| C: Bonus维度 | ≥3/10 systematic | 1-3/10, 高judge方差 | ⚠ 数据不足，延迟 |

### v2.7-hybrid 3-run 数据

```
R1=86.3% R2=95.0% R3=78.8% → 86.7±8.1pp
v2.5.1 honest: ~91.5±1.9pp
→ v2.7-hybrid: 低均值 + 4x高方差 → REJECTED
根因: hypothesis tracking导致agent在简单bug上过虑
```

### 进化链

```
v2.1(86.3%) → v2.3 → v2.5(95.4%,封版)
    → v2.6 GEPA(90%,退化) → v2.5.1(F6 only, production)
    → v2.7-hybrid(86.7%,高方差,拒绝)
    → v3.0-alpha 螺旋(实验,线性更优,拒绝)
```

### 已做的

- 9 commits, $1.65 spent
- v2.5.1 = production (F1-F6 + T4 config check)
- v3.0-alpha = 归档参考 (螺旋模型, 不用于production)
- evolve.py: 双文件 + encoding fix + 5环→精简
- per_bug_results.tsv: 恢复 + bonus + hypothesis tracking
- T2 script: v2.7-hybrid prompt + bonus judge dimension
- CORRECTED_PLAN.md: 完整修正计划
- VERIFICATION_PROTOCOL.md: 旧5-phase协议

### 待做

1. 跑 T3 cross-model 对比 (v2.5.1 vs bare, $5)
2. Human baseline (凡哥做 3-5 bugs)
3. 修复 B03/B04 持续模式 → F7 候选
4. 49-bug 全量 T2 验证
5. 多 skill leaderboard (铁壁 + 火眼)

### 关键教训

1. 先实验后设计。$0.15 A/B 避免 $3 错误方向。
2. 线性链 > 螺旋链 (对LLM)。假设追踪增加方差, 不增加值。
3. Bonus维度有趣但不可靠 — 单judge方差太大。
4. F6 (T4配置检查) 是唯一经实验验证的单F-rule改进。
5. v2.5.1 真正的价值 = 降方差 (SD 2.5x < bare), 不是升天花板。
