# B26 — Ground Truth

**Type:** T0（稳定复现 — 无 Authorization 头必 panic）

**根因:** `middleware/auth.go` JWT 中间件在处理无 Authorization 头的请求时，`c.GetHeader("Authorization")` 返回空字符串。`strings.TrimPrefix(tokenString, "Bearer ")` 后仍然是空字符串。随后 `jwt.ParseWithClaims(tokenString, ...)` 被传入空字符串，返回 nil token。代码直接访问 `token.Valid` 或 `token.Claims` 而没有检查 `token == nil`，触发 nil pointer dereference。

关键代码路径：
```go
tokenString := c.GetHeader("Authorization")
tokenString = strings.TrimPrefix(tokenString, "Bearer ")
token, _ := jwt.ParseWithClaims(tokenString, &Claims{}, ...)
if token.Valid { ... }  // token 为 nil → panic
```

**正确修复:**
```go
token, err := jwt.ParseWithClaims(tokenString, &Claims{}, ...)
if err != nil || token == nil {
    c.JSON(401, gin.H{"detail": "无效的token"})
    c.Abort()
    return
}
```

**文件:** `campus_go/internal/middleware/auth.go`

**评分要点:**
- 分类: T0 — 无 Authorization 头必 panic (1pt)
- 证据: panic 堆栈定位到 JWT 中间件 + 空 token 复现 (1pt)
- 根因: middleware/auth.go — token 为 nil 后未检查直接访问 token.Valid (2pt)
- CF: 加 nil check → 无 token 返回 401 而非 panic (1pt)
- 修复: 检查 err != nil || token == nil (1pt)
