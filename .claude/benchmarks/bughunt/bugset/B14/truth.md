# B14 — Ground Truth

**Type:** T3（无报错 — 数据静默丢失）

**根因:** `dashboard.go:98-108` CollegeStudents 函数中 `for rows.Next()` 循环内使用 `rows.Scan(...)` 扫描 8 个字段。如果某行的数据与 Go 类型不匹配（如 `volunteer_hours` 为 NULL 而扫描目标是 `float64` 非指针），Scan 返回 error。代码用 `if err := rows.Scan(...); err != nil { log.Printf(...); continue }` 处理——记录日志后 **跳过该行**（continue）。结果：有问题的学生行被静默跳过，不在 API 响应中出现。

更关键的是，循环结束后没有 `rows.Err()` 检查，迭代过程中的其他错误也会被遗漏。

**正确修复:**
1. 将 `volunteerHours float64` 改为可处理 NULL 的类型（如 `*float64` 或使用 COALESCE）
2. 循环后添加 `if err := rows.Err(); err != nil { ... }`

**文件:** `campus_go/internal/handlers/dashboard.go:98-108`

**评分要点:**
- 分类: T3 — 无报错，行被静默跳过 (1pt)
- 证据: 学生总数对不上 + 日志中的 scan error + 定位到 continue 跳过逻辑 (1pt)
- 根因: Scan error → continue → 行丢失 + 无 rows.Err() 检查 (2pt)
- CF: 用 COALESCE 处理 NULL → 所有行正常显示 (1pt)
- 修复: COALESCE + rows.Err() 检查 (1pt)
