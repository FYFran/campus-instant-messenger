# BugHuntBench 评分框架

## 执行流程

```
1. 给 agent bug 描述（用户视角） + 目标 skill
2. agent 排查 + 输出 bug report
3. 独立评分 agent 对照 ground truth 打分
4. 汇总报告
```

## 自动判分规则

每个 bug 满分 7 分，对照 ground truth 的评分要点：

| # | 维度 | 分值 | 判据 |
|---|------|------|------|
| 1 | 分类 | 1 | T-Type 与 truth 一致 |
| 2 | 链完整 | 1 | 7 步产出非空（或 T7/emergency 正确缩短） |
| 3 | 证据 | 1 | 复现步骤 + baseline 可验证 |
| 4 | 根因 | 2 | 与 truth 一致（含 file:line）。部分正确=1 |
| 5 | CF | 1 | 有可验证 pre/post 证据（非模板文本） |
| 6 | 修复 | 1 | 消除根因 + 不引入新问题 |

## 汇总

```
总分 = Σ(bug得分) / 70 × 100

T0-T7 覆盖率 = 分类正确的 bug 类型数 / 8
链完整率 = 产出链完整的 bug 数 / 10
根因命中率 = 根因正确的 bug 数 / 10
CF 真实率 = CF 有证据的 bug 数 / 10
```
