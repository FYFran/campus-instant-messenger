# B23 — Ground Truth

**Type:** T2（多因素 — DB 字段为 NULL + Go 零值语义 + 业务逻辑）

**根因:** `activities.go:170-174` Signup 函数处理 `signupStart` 的逻辑：

```go
var signupStart *time.Time
if signupStartStr != "" {
    if t, err := time.Parse(time.RFC3339, signupStartStr); err == nil {
        signupStart = &t
    }
}
```

当 `signupStartStr` 为空字符串（数据库中 `signup_start` 为 NULL，被 COALESCE 转为 `''`），`signupStart` 保持 `nil`。

然后在 `activities.go:184-186`：
```go
if signupStart != nil && time.Now().Before(*signupStart) {
    c.JSON(400, gin.H{"detail": "报名尚未开始"})
    return
}
```

逻辑本应正确：`signupStart == nil` → 不检查开始时间 → 允许报名。但如果数据库中的 `signup_start` 存储了非标准空值（如字符串 `"null"`、空格 `" "`、或无效日期如 `"0001-01-01T00:00:00Z"`），则：
- `signupStartStr != ""` → true（因为包含非空字符串）
- `time.Parse(time.RFC3339, signupStartStr)` → 可能成功解析出公元 1 年的时间
- `time.Now().Before(*signupStart)` → true（当前时间在公元 1 年之后）
- → 返回"报名尚未开始"

**触发条件:** 数据库 `signup_start` 字段包含无效但非空的日期字符串。

**正确修复:**
1. 解析后验证 signupStart 在合理范围内（如不早于 2020 年）
2. 或：`time.Parse` 失败时不设置 signupStart（当前已有 err != nil 检查，但 `"0001-01-01T00:00:00Z"` 是合法 RFC3339）

**文件:** `campus_go/internal/handlers/activities.go:170-174, 184-186`

**评分要点:**
- 分类: T2 — 需要 DB 异常数据 + 解析成功 + 时间比较三个因素 (1pt)
- 证据: 活动无报名开始时间限制但被拦截 + 数据库 signup_start 值检查 (1pt)
- 根因: time.Parse 成功解析异常日期→signupStart 为远古时间→Before 永远 true (2pt)
- CF: 加 signupStart 合理性验证 → 异常日期被忽略，正常报名 (1pt)
- 修复: 解析后验证年份 >= 2020 (1pt)
