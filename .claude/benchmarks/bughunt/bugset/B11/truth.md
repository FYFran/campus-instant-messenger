# B11 — Ground Truth

**Type:** T0（稳定复现 — DB 连接异常时必 panic）

**根因:** `dashboard.go:55` SchoolDashboard 函数中使用 `rows, _ := db.Query(c.Request.Context(), ...)` 忽略了 db.Query 的错误返回值。当数据库连接池耗尽或网络异常时，`db.Query()` 返回 error，同时 `rows` 为 `nil`。后续 `defer rows.Close()` 在 nil 指针上调用方法，触发 panic。

**正确修复:** 
```go
rows, err := db.Query(c.Request.Context(), ...)
if err != nil {
    log.Printf("SchoolDashboard query error: %v", err)
    c.JSON(500, gin.H{"detail": "查询失败"})
    return
}
defer rows.Close()
```

**文件:** `campus_go/internal/handlers/dashboard.go:55`

**评分要点:**
- 分类: T0 — 条件满足时稳定 panic (1pt)
- 证据: 日志中的 nil pointer dereference + 定位到 `rows, _ := db.Query` (1pt)
- 根因: dashboard.go:55 忽略 db.Query error → rows 为 nil → defer rows.Close() panic (2pt)
- CF: 加 error check → 异常时返回 500 而非 panic (1pt)
- 修复: 改 `rows, _ :=` 为 `rows, err :=` + error check (1pt)
