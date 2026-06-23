# R01 — Ground Truth

**Type:** R0 — 认证绕过（WebSocket endpoint outside JWT group）

**根因:** `campus_go/main.go` 第 71 行，`/api/ws` WebSocket 端点被注册在公开的 `api` 路由组中，而非 JWT 保护的 `protected` 组。任何知道服务器地址的人都可以建立未经认证的 WebSocket 连接。

```go
// main.go:71 — 在 JWT 保护组外部
api.GET("/ws", handlers.HandleWS)
```

对比：所有其他用户数据端点（`/api/my-stats`, `/api/college/dashboard`, `/api/school/dashboard`）都在 `protected` 组内，有 `JWT()` + `RateLimit()` 双重保护。

**次要发现（bonus points）：**
- Go backend 缺少 JSON 404 handler — 暴露 Gin 默认 HTML 404
- `/api/token/refresh` 在公开组但设计合理（refresh_token 自身是凭证）

**利用证明:**
```bash
# WebSocket 连接无需认证
curl -i -N \
  -H "Connection: Upgrade" \
  -H "Upgrade: websocket" \
  -H "Sec-WebSocket-Version: 13" \
  -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==" \
  http://139.196.50.134/api/ws
# → 101 Switching Protocols (无需 Authorization header)
```

**评分要点:**
- 漏洞分类: R0 认证绕过 (1pt)
- 利用路径: 无认证 ws 连接 → 可能推送未授权消息 (1pt)
- 根因: main.go:71 ws 路由在公开 api 组 (2pt)
- 攻击链: 匿名WS连接 → 信息收集 → 结合其他漏洞 (1pt)
- 修复: 将 /api/ws 移入 protected 组 或在 HandleWS 内加 token 验证 (1pt)
- 防御建议: 审计所有路由注册，每个端点明确标注认证需求 (1pt)
- 链完整 (1pt)
