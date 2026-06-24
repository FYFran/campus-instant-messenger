# B26 — T0: JWT 中间件空指针 panic

## Bug 描述

campus_go 在特定条件下处理不带 Authorization 头的请求时发生 panic。日志显示 `runtime error: invalid memory address or nil pointer dereference` 发生在 `auth.go` 的 JWT 中间件中。正常带 token 的请求没问题。
