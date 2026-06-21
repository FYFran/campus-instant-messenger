# Skill Compliance 研究 — 2026-06-21

## 问题

缉凶 370 行 7 Phase，15 judge 确认结构完整（20/20 lint），但执行测试发现 agent 跳过 gate/不严格执行。

## 根因（学术证据）

### 1. Compliance Gap (arXiv:2605.01771, May 2026)
- LLM 在默认框架下 **0% 指令合规率**
- 口头同意 10/10 次，实际执行 0/10 次
- 该 gap 结构上不可避免（RL 奖励文本不观察行为）
- **从文本本身无法检测违规**（Data Processing Inequality）
- 唯一有效缓解：**审计追踪**（audit trails）→ 97% 合规率

### 2. Guardrails Beat Guidance (arXiv:2604.11088, May 2026)
- 5,000+ Claude Code agent 运行，679 个规则文件
- **负面约束（"不要做 X"）> 正面指令（"做 X"）**
- 规则极性是唯一区分有益/有害规则的因子
- 随机/打乱/不匹配域的规则文件与精心策划的规则效果相同
  → 暗示机制是 **context priming**，不是特定行为指令
- 最多 50 条规则无性能退化

### 3. Plan Compliance (arXiv:2604.12147, Apr 2026)
- 16,991 SWE-agent 轨迹，4 个 LLM
- **额外 Phase 会降低性能**（计划与内部策略不对齐时）
- Periodic reminders 有效
- 差的计划比没有计划更糟

### 4. SkillOpt (arXiv:2605.23904, May 2026)
- Microsoft: 把 skill 当"可训练外部状态"
- Bounded edit + validation gate + rejected-edit buffer
- 6 benchmark × 7 model × 3 harness = 52 cell，全部 best or tied-best
- Skills transfer across model scales AND harnesses

## 设计原则

| # | 原则 | 来源 |
|---|------|------|
| 1 | **负面约束优先** — "如果不做 X，后果 Y" 替代 "做 X" | Guardrails Beat Guidance |
| 2 | **审计追踪强制** — 每个决策留痕，不留痕=未发生 | Compliance Gap |
| 3 | **体积压缩** — <200 行，删"怎么做"留"不能做什么" | Plan Compliance + Anthropic 官方 |
| 4 | **决策点提醒** — 在关键分叉重复核心约束 | Plan Compliance |
| 5 | **Pass^k 思维** — 追求最差情况可靠，不是平均 | Replayable Agents |

## 三层评估

```
L1 静态 Lint（便宜）→ 结构完整 ✓ (skill-lab v0.2)
L2 输出断言（中等）→ 格式正确 ✓ (test-prompts)
L3 轨迹审计（贵）  → 行为合规 ✗ (需要实际执行 agent)
```

## 行动

1. 缉凶 v2.0 — 约束框架重写，<200 行
2. skill-lab v0.3 — +Trace Audit 层
3. 99 重定义 = 执行测试 100% 轨迹完整率
