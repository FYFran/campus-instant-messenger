# B20 — Ground Truth

**Type:** T6（环境不匹配 — 时区差异）

**根因:** `activities.go:164` Signup 函数中 `deadline, err := time.Parse(time.RFC3339, deadlineStr)` 解析的 deadline 字符串来自数据库 text 列，通常存储为 UTC 时间（如 `"2026-06-22T15:59:00Z"`）。而 `time.Now()` 返回的是服务器的本地时间（CST，UTC+8）。

比较 `time.Now().After(deadline)` 时：
- deadline 是 UTC 15:59（即北京时间 23:59）
- `time.Now()` 返回北京时间 16:00（即 UTC 08:00）
- `time.Now().After(deadline)` → 北京时间 16:00 vs UTC 15:59 → 取决于 Go 的时区处理

Go 的 `time.Time` 内部存储绝对时间（纳秒自 epoch），`After()` 比较的是绝对时刻。如果 deadline 正确解析为带时区的 RFC3339 时间，比较本应正确。但数据库的 deadline 列是 `text` 类型，值可能是 `"2026-06-22T23:59:00"`（无时区后缀）。`time.Parse(time.RFC3339, "2026-06-22T23:59:00")` 将这个时间解析为 UTC，而实际上数据库存的是北京时间 23:59（即 UTC 15:59）。结果：北京时间 23:59 的截止时间被当作 UTC 23:59（即北京时间次日 07:59），导致截止判断提前 8 小时触发。

**正确修复:**
```go
loc, _ := time.LoadLocation("Asia/Shanghai")
deadline, err := time.ParseInLocation("2006-01-02T15:04:05", deadlineStr, loc)
```

**文件:** `campus_go/internal/handlers/activities.go:164`

**评分要点:**
- 分类: T6 — 数据库 text 时间无时区 vs time.Now() 本地时区 (1pt)
- 证据: 提前 8 小时截止 + 定位到 time.Parse 无时区处理 (1pt)
- 根因: activities.go:164 — time.Parse 将无时区字符串当作 UTC，与北京时间差 8h (2pt)
- CF: 用 ParseInLocation(Asia/Shanghai) → 截止判断正确 (1pt)
- 修复: ParseInLocation 替代 time.Parse (1pt)
