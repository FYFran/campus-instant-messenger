# B12 — Ground Truth

**Type:** T3（无报错 — 数据静默错误）

**根因:** `dashboard.go:30-33` CollegeDashboard 函数中 4 处 `db.QueryRow(...).Scan(...)` 调用均未检查 Scan 的错误返回值。当用户记录的 `college` 字段为 NULL 或空字符串时，第一条 QueryRow 的 Scan 失败，但程序继续执行后续 3 条查询。如果某条查询因为 college 值异常而失败，对应统计量保持 Go 零值（0），最终返回全零数据但 HTTP 200。

具体来说，`db.QueryRow(...).Scan(&students)` 这种写法丢弃了 error。如果 college 为空字符串导致后续查询匹配 0 行，Scan 返回 `pgx.ErrNoRows`，但错误未被检查，变量保持零值。

**正确修复:**
```go
err := db.QueryRow(...).Scan(&students)
if err != nil && !errors.Is(err, pgx.ErrNoRows) {
    log.Printf("CollegeDashboard students query error: %v", err)
    c.JSON(500, gin.H{"detail": "查询失败"})
    return
}
```

**文件:** `campus_go/internal/handlers/dashboard.go:30-33`

**评分要点:**
- 分类: T3 — 无报错，数据静默错误 (1pt)
- 证据: 学院有数据但仪表板全0 + 定位到无 error check 的 Scan 调用 (1pt)
- 根因: 4 处 QueryRow.Scan 丢弃 error，college 空值→ErrNoRows→零值→200 (2pt)
- CF: 加 error check → 有错误时返回 500 或正确处理 ErrNoRows (1pt)
- 修复: 每处 Scan 后检查 error (1pt)
