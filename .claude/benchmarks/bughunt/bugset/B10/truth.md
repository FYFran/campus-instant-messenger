# B10 — Ground Truth (v2)

**Type:** T3（无 crash/error，性能退化 — N+1 查询模式）

**根因:** `dashboard.go:149` `GetMySignups` handler 中，主查询获取报名记录后，对每条记录执行了单独的 SQL 查询获取活动信息。原代码用 JOIN 一次查询完成，注入后改为逐条查询 → N+1。

注入前 (bug): 逐条查询 activity 详情 — 10 signups = 11 queries
注入后 (fix): `JOIN activities a ON s.activity_id=a.id` — 1 query

**正确修复:** 使用 JOIN 合并查询：`FROM signups s JOIN activities a ON s.activity_id=a.id`

**评分要点:**
- 分类: T3 — 无报错，越来越慢 (1pt)
- 证据: 查询计数对比（N条报名=N+1 vs JOIN=1）(1pt)
- 根因: N+1 — 循环内单独查询替代 JOIN (2pt)
- CF: JOIN→查询数从N+1降为1 (1pt)
- 修复: JOIN 合并 (1pt)
- 链完整 (1pt)
