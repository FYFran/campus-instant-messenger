# B38 — Ground Truth

**Type:** T5（状态机异常 — 懒初始化未完成时被访问）

**TRAP:** 看起来像 T0（"每次重启必现 crash"），实质是 T5 状态机问题。服务启动时 tokenBlacklist 是懒初始化的（lazy init），但第一个请求在初始化完成前就访问了它。此时 `tokenBlacklist` 还是 nil → `tokenBlacklist.IsBlacklisted()` → nil pointer panic。第一个请求崩溃后，懒初始化被触发完成，后续请求正常。

**根因:** `auth.go:35` tokenBlacklist 使用 `sync.Once` 懒初始化，但 `middleware.go:88` 的 JWT 中间件在 `init()` 完成前就调用了 `IsBlacklisted()`。`sync.Once` 的 `Do()` 未完成时，其他 goroutine 不会被阻塞（它们看到 nil 对象）。

**正确修复:** 在 `main.go` 启动时显式初始化 tokenBlacklist：`auth.InitTokenBlacklist()` 放在 `router.Run()` 之前。

**评分要点:**
- 分类: T5 — 懒初始化未完成 = 状态未就绪 (1pt)
- 证据: 第一次请求必崩 + 重启复现 + 定位 init 顺序 (1pt)
- 根因: tokenBlacklist 懒初始化 race → middleware 访问时 nil (2pt)
- CF: 加显式 InitTokenBlacklist() → 消除竞态 (1pt)
- 修复: main.go 加 InitTokenBlacklist() 在 Run 前 (1pt)
