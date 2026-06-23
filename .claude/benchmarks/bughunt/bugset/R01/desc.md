# R01 — R0: Unprotected Endpoint Outside JWT Middleware Group

## Bug 描述

campus_go 的 Go 后端中，审计路由注册代码 `main.go`。查找是否有端点被注册在 JWT 中间件保护组之外，但仍应需要认证。

重点关注：
- 哪些端点注册在 `api` 组（公开）vs `protected` 组（需JWT）
- 是否有端点错误地放在公开组中
- WebSocket 端点的认证状态
- Token 刷新端点的安全设计

证明任何发现的不受保护端点可以被未经认证的用户访问。
