# B19 — Ground Truth

**Type:** T1（竞态条件 — 并发 map 访问）

**根因:** `auth.go:22-23` 声明的 `loginRateLimit` 是一个普通的 `map[string]time.Time`，由 `loginRateMu sync.Mutex` 保护。但 rate limit 代码（auth.go:70-78）被注释掉后，如果有其他代码路径或未来恢复的代码在**读** map 时没加锁，就会触发竞态。

更具体的实际竞态：即使在注释掉的代码中，`loginRateLimit[c.ClientIP()]` 的读写操作如果没正确加锁，在并发请求下会出现 `fatal error: concurrent map read and map write`。

在 Go 中，map 不是并发安全的。即使只是读取（`lastAttempt, exists := loginRateLimit[c.ClientIP()]`），如果另一个 goroutine 同时在写入（`loginRateLimit[c.ClientIP()] = time.Now()`），就会触发竞态。

**正确修复:**
使用 `sync.RWMutex` 替代 `sync.Mutex`，读操作用 RLock，写操作用 Lock。或使用 `sync.Map`。

```go
var loginRateLimit sync.Map  // 替代 map[string]time.Time + sync.Mutex
```

**文件:** `campus_go/internal/handlers/auth.go:22-23`

**评分要点:**
- 分类: T1 — 并发竞态，race detector 可检测 (1pt)
- 证据: `go test -race` 输出 + 定位到无锁 map 访问 (1pt)
- 根因: auth.go:22-23 — 普通 map + sync.Mutex 但读写未全部加锁 (2pt)
- CF: 改用 sync.Map 或确保全部加锁 → race detector 通过 (1pt)
- 修复: sync.Map 或 RWMutex (1pt)
