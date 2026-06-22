# Human Baseline Protocol — 凡哥手动 Debug

## 选 bug (5 个, 覆盖核心类型)

| Bug | Type | 预计难度 | 为什么选 |
|-----|------|---------|---------|
| B01 | T0 nil deref | 简单 | 基线: 最简单的 bug 人类多快 |
| B04 | T3 数据截断 | 中 | AI 偶尔失败, 人类对比 |
| B05 | T4 配置回归 | 中-难 | AI 持续失败 (root_cause=0), 关键对比 |
| B08 | T7 NOT_A_BUG | 特殊 | AI 写代码还是停下? 人类判断 |
| M03 | T3 限流失效 | 难 | Git-mined 真实 bug, 最接近实战 |

## 操作步骤

1. 我给凡哥每个 bug 的 desc.md（只读 bug 描述）
2. 凡哥读 → 查 campus_go 代码 → 判分类/根因
3. 不限工具, 不限时间
4. 记录每个 bug: 分类 / 根因 / 置信度 / 用了多久

## AI 之后做的事

1. Sonnet 用同一 judge prompt 评 凡哥 的答案
2. 对比 凡哥 vs AI 在每个维度的分数
3. 计算: 人类分数 / AI 分数 / gap

## 需要凡哥的时间

~30 分钟 (5 bugs × ~5-6min each)

## 用途

- 所有 AI 分数的参照系
- Judge 校准 (凡哥评分 vs Judge 评分)
- 知道 AI 在哪个 type 上比人类弱
