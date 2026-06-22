# B03 — Ground Truth

**Type:** T0（稳定复现 — 每次 college_admin 请求都看到所有学院的活动）

**根因:** `activities.go` ListActivities 函数的 SQL WHERE 子句只过滤了 `status != 'draft'`，完全没有 college 范围的过滤条件。其他管理 handler（ApproveActivity、RejectActivity、ModifyActivity、GetPendingApprovals）使用 `($role = 'school_admin' OR scope_type = 'all' OR college = (SELECT college FROM users WHERE id=$userID))` 模式做了学院隔离，但 ListActivities 遗漏了此条件。同时 handler 没有从 Gin context 读取 `role` 变量。

**正确修复:** 
1. 在 ListActivities 中读取 `role := c.GetString("role")`
2. 在 SQL WHERE 子句追加 `AND ($4 = 'school_admin' OR a.scope_type = 'all' OR a.college = (SELECT college FROM users WHERE id=$1))`
3. 将 role 作为第 4 个查询参数传入

**评分要点:**
- 分类: T0 — 识别为缺失功能/稳定复现 (1pt)
- 证据: 复现 + 对比其他 handler 的 college 过滤模式 (1pt)
- 根因: ListActivities SQL 缺少 college 过滤 + role 未读取 (2pt)
- CF: 对比其他 handler 中已有的 college 过滤模式 vs ListActivities 缺失 (1pt)
- 修复: 添加 role 读取 + SQL college 过滤条件 (1pt)
- 链完整 (1pt)
