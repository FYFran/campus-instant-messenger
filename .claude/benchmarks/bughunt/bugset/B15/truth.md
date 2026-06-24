# B15 — Ground Truth

**Type:** T6（环境不匹配 — Go 类型 vs DB 类型）

**根因:** `dashboard.go:131` GetNotifications 函数中 `isRead` 声明为 Go `bool` 类型，但 PostgreSQL 数据库中 `notifications.is_read` 列是 `integer` 类型（存储 0 或 1）。pgx 驱动默认不自动转换 integer→bool，导致 `rows.Scan` 失败：`can't scan into dest[4] (col: is_read): cannot scan integer into *bool`。

Scan 错误被 `log.Printf + continue` 捕获，所以每行都因为 scan 失败被跳过，最终返回空列表或只返回没有错误的行。但数据库层面 `is_read=1` 的记录确实存在。

**正确修复:**
```go
var isReadInt int
// ... Scan(&id, &title, &content, &ntype, &isReadInt, &createdAt)
isRead := isReadInt != 0
```
或在 SQL 中使用 `CASE WHEN is_read=1 THEN true ELSE false END as is_read`。

**文件:** `campus_go/internal/handlers/dashboard.go:131`

**评分要点:**
- 分类: T6 — Go bool ≠ PostgreSQL integer，环境/驱动行为差异 (1pt)
- 证据: 日志中 "cannot scan integer into *bool" + 数据库 is_read=1 但 API 返回空/false (1pt)
- 根因: dashboard.go:131 — Go bool 无法 scan PostgreSQL integer (2pt)
- CF: 改为 int 中间变量或 SQL CASE → is_read 正确返回 true/false (1pt)
- 修复: 修改 Scan 目标类型 (1pt)
