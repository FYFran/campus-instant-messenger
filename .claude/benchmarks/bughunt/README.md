# BugHuntBench v0.1

调试 skill 质量基准。10 个已知根因的 bug，测 agent 是否能走完排查流程找到正确根因。

## 评分（满分 70）

| 维度 | 分值 | 判定 |
|------|------|------|
| 分类正确 | 1 | T-Type 与 ground truth 一致 |
| 产出链完整 | 1 | 7 步合同链每步产出非空 |
| 证据充分 | 1 | 复现步骤 + baseline 可验证 |
| 根因正确 | 2 | 根因与 ground truth 一致（含 file:line） |
| Counterfactual 真实 | 1 | CF 有可验证的 pre/post 证据 |
| 修复正确 | 1 | 修复消除根因，不引入新问题 |

## Bug 覆盖

| ID | Type | 语言 | 难度 | 场景 |
|----|------|------|------|------|
| B01 | T0 | Go | 易 | nil deref after DB query |
| B02 | T1 | Go | 中 | race condition signup |
| B03 | T2 | Go | 难 | multi-factor permission check |
| B04 | T3 | Python | 中 | silent data miscalculation |
| B05 | T4 | Go | 易 | regression from config change |
| B06 | T5 | Go | 中 | state machine stuck |
| B07 | T6 | Mixed | 难 | CI vs local env mismatch |
| B08 | T7 | Go | 易 | NOT_A_BUG — working as designed |
| B09 | T1 | Python | 中 | missing await in async code |
| B10 | T3 | Go | 难 | N+1 query silent performance bug |

## 执行

```
1. 注入 bug 到 campus_go 代码库
2. 给 agent bug 描述（用户视角）
3. agent 用目标 skill 排查
4. 自动判分 vs ground truth
```

## Ground Truth

每个 bug 在 `bugs/` 目录下有：
- `B0X_desc.md` — 用户视角的 bug 描述
- `B0X_truth.md` — 根因 + 正确修复 + 评分要点
- `B0X_patch.diff` — 正确的修复 diff
