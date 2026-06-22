# B34 — Ground Truth

**Type:** T2（多因素 — 数据量增长 + 子查询未优化 + 缺少索引）

**根因:** `activities.go:28-38` ListActivities 的主查询包含 `(SELECT COUNT(*) FROM signups WHERE activity_id=a.id)` 子查询。对于列表中的每个活动，数据库都需要执行一次子查询来计数报名人数。50 个活动 × 1 次子查询 = 51 次查询（1 主查询 + 50 相关子查询）。

如果 `signups.activity_id` 缺少索引（或索引统计信息过期），每次子查询做全表扫描。50 活动 × signups 表 N 行 = O(N×M) 复杂度。

**三个因素叠加:**
1. 活动数量增多（>50）→ 子查询次数增多
2. signups 表缺少 `activity_id` 索引 → 每次子查询全表扫描
3. 主查询还有 `EXISTS(SELECT 1 FROM signups WHERE activity_id=a.id AND user_id=$1)` → 再加一层子查询

**正确修复:**
1. 添加 `CREATE INDEX IF NOT EXISTS idx_signups_activity ON signups(activity_id)`
2. 用 LEFT JOIN + GROUP BY 替代标量子查询（一次查询解决）：
```sql
SELECT a.*, COALESCE(sc.cnt, 0) as signup_count
FROM activities a
LEFT JOIN (SELECT activity_id, COUNT(*) as cnt FROM signups GROUP BY activity_id) sc ON a.id = sc.activity_id
```

**文件:** `campus_go/internal/handlers/activities.go:28-38` + DB schema

**评分要点:**
- 分类: T2 — 需要活动增长 + 缺索引 + 标量子查询三个因素 (1pt)
- 证据: 50+ 活动后延迟 >2s + EXPLAIN 显示全表扫描 (1pt)
- 根因: 标量子查询 O(N×M) + 缺 activity_id 索引 (2pt)
- CF: 加索引 + JOIN 替代子查询 → 50 活动 <100ms (1pt)
- 修复: 索引 + JOIN 优化 (1pt)
