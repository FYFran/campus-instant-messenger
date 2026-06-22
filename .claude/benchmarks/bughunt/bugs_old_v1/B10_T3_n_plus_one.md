# B10 — T3: N+1 query silent degradation

## Bug 描述
campus_go 的活动列表页面加载越来越慢。活动只有 50 个时加载只需 100ms，现在活动 200 个时需要 3 秒。没有报错，API 正常返回 200——就是越来越慢。用户抱怨"刷个列表要等半天"。

## Ground Truth

**Type:** T3（无 crash/error，数据悄悄错——这里"错"的是性能）

**根因:** `ListActivities` handler 中主查询获取活动列表后，对每个活动执行了单独的 SQL 查询获取 `signup_count`（N+1 模式）。活动 50 个时 51 次查询还能接受，200 个时 201 次查询导致性能退化。代码没有报错——只是越来越慢。

**正确修复:** 使用子查询或 JOIN 将 signup_count 合并到主查询中：`LEFT JOIN (SELECT activity_id, COUNT(*) as cnt FROM signups GROUP BY activity_id) s ON a.id = s.activity_id`

**评分要点:**
- 分类: T3 (1pt)
- 证据: 数据量-延迟对比 + 查询日志分析 (1pt)
- 根因: N+1 查询 — 主查询 + 每个活动单独查 (2pt)
- CF: JOIN→200活动<200ms (1pt)
- 修复: JOIN 替代 N+1 (1pt)
- 链完整 (1pt)
