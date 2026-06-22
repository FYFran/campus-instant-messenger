# B30 — Ground Truth

**Type:** T1（竞态条件 — WebSocket 写入无锁）

**根因:** Go 的 WebSocket 连接（`gorilla/websocket`）不支持并发写入。如果服务端的通知推送 goroutine 和心跳 ping goroutine 同时对同一个 WebSocket 连接调用 `conn.WriteJSON()` 或 `conn.WriteMessage()`，底层 TCP 连接的数据会交错，导致客户端 JSON 解析失败，消息被静默丢弃。

campus_go 的 WebSocket 实现中，`WriteJSON` 被多个 goroutine 调用：
1. 通知推送 goroutine：有新通知时推送
2. 心跳 goroutine：每 30 秒发 ping

无写入锁保护。

**正确修复:**
```go
type WSConn struct {
    conn    *websocket.Conn
    writeMu sync.Mutex
}

func (w *WSConn) WriteJSON(v interface{}) error {
    w.writeMu.Lock()
    defer w.writeMu.Unlock()
    return w.conn.WriteJSON(v)
}
```

**文件:** `campus_go/internal/websocket/` (WebSocket handler)

**评分要点:**
- 分类: T1 — 并发写入竞态，压测时更明显 (1pt)
- 证据: 10 条丢 1-2 条的频率 + 多 goroutine WriteJSON 分析 (1pt)
- 根因: gorilla/websocket 不支持并发写，无写锁保护 (2pt)
- CF: 加写锁 → 消息不再丢失 (1pt)
- 修复: sync.Mutex 保护 WriteJSON (1pt)
