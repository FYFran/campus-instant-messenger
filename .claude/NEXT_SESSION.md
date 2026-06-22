# 新对话指令

你是皮特。读 `f:\ClaudeFiles\.claude\CLAUDE.md`。

## 当前状态：Exp B 完成，混合模型就绪

### Exp B 结果：线性 > 螺旋 (分类 3/3 vs 2/3)

| Bug | GT | Spiral type | Linear type | Spiral root | Linear root | Winner |
|-----|-----|-------------|-------------|-------------|-------------|--------|
| B05 | T4 | T4 ✅ | T4 ✅ | DB restore (wrong) | nginx port (correct) | **Linear** |
| B07 | T6 | T6 ✅ | T6 ✅ | nil guard (correct) | Go NULL Scan (correct) | Tie |
| M03 | T3 | T2 ❌ | T3 ✅ | Commented code (correct) | Commented code (correct) | **Linear** |

**关键发现：**
1. 线性分类更准 (3/3 vs 2/3)。螺旋未提升分类准确度。
2. 螺旋的 hypothesis_chain 字段非常有价值——agent 推理过程完全可审计。
3. 螺旋在 B05 上走了 3 轮假设推翻（H1:JWT→推翻→H2:DB→推翻→H3:DB双失效→确认），展现了真正的假设驱动 debugging。但最终还是线性猜对了根因。
4. **最佳方案：混合模型。** 线性分类（可靠）+ 可证伪假设追踪（透明）。

### v2.7-hybrid 设计（已实现）

```
[分类 + H] → [证据：验证H] → [追踪：H成立?继续:H推翻?修正H2] → [分析] → [修复] → [验证] → [记录]
```

关键改变：
- 分类步增加 `假设 H: 如果我对，___应该为真。验证方法: ___`
- 证据步增加 `H验证结果: 成立/推翻(证据:___)`
- H 被推翻 → 查 F1-F6 找替代方向 → 修正分类 + 新 H
- 最多推翻 2 次，第 3 次 STOP
- **分类决策流不变**（v2.5.1 核心），**F1-F6 不变**，**T4 配置检查不变**

### 待做

```
1. 跑 v2.7-hybrid T2 验证 (10 bugs, $0.50) → 确认 ≥93%
2. 跑 Exp C: bonus bug checker ($0.03 + T2 agent reports)
3. 如果 v2.7 ≥93% 且 Exp C ≤1 bonus → 封版 v2.7-hybrid
4. 如果 v2.7 ≥93% 且 Exp C ≥3 bonus → 加 bonus 维度 + 重跑
5. 如果 v2.7 <93% → 回滚 v2.5.1
```

### 关键文件

```
.claude/skills/缉凶.md                    → v2.7-hybrid (当前)
.claude/skills/缉凶-v3.0-alpha.md         → 纯螺旋 (实验，保留参考)
.claude/benchmarks/bughunt/
  bughunt_ab_spiral.js                     → Exp B A/B脚本
  bughunt_bonus_check.js                   → Exp C bonus检测
  CORRECTED_PLAN.md                        → 修正计划
```

### 实验教训

1. **螺旋不提升分类准确度** — 线性决策流本身就是好的分类器
2. **假设链的最大价值是审计** — 知道 agent 为什么犯错比知道它犯什么错更有用
3. **混合 > 纯替代** — 保留工作的部分(分类)，增强弱的部分(推理透明)
4. **3 bug A/B 够用** — 便宜 ($0.15) 且能在问题变大前发现方向错误
