# M01 — Ground Truth

**Type:** T1（竞态/并发 — 高并发时偶尔超时）

**根因:** Dashboard 聚合查询使用 `WHERE child_id IN (SELECT id FROM parents WHERE user_id=?)` 关联子查询。MySQL 优化器在并发负载下可能切换到 dependent-subquery 执行计划（逐行执行内查询），导致 O(N×M) 复杂度，数据库 CPU 飙升 → 超时。

**文件:** `dashboard.go` 统计查询部分

**正确修复:** 将关联子查询替换为显式 JOIN，让优化器使用 hash/semi-join 单次扫描。

**评分要点:**
- 分类: T1 — 高并发时偶尔超时，平时正常 (1pt)
- 证据: 高峰期 CPU 飙升 + 子查询执行计划 (1pt)
- 根因: IN (SELECT ...) 关联子查询在并发下走 dependent-subquery (2pt)
- CF: EXPLAIN 对比 JOIN vs 子查询 (1pt)
- 修复: 替换为 LEFT JOIN + GROUP BY (1pt)
