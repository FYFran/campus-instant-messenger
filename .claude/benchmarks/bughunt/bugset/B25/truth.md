# B25 — Ground Truth

**Type:** T5（状态机异常 — 读/写状态不同步）

**根因:** 前端（Flutter）有**两个不同 API 调用**获取通知状态：
1. 通知列表页调用 `GET /api/notifications` — 返回 `is_read` 字段
2. 通知详情页调用 `GET /api/notifications/:id` — 也返回 `is_read` 字段
3. 标记已读调用 `PUT /api/notifications/:id/read` — 更新数据库 `is_read=1`

问题出在两个 GET 端点可能关联了不同的数据源或缓存。如果 `GET /api/notifications` 使用了物化视图、缓存表、或前端缓存，而 `PUT .../read` 只更新了主表，则列表页读到的永远是旧缓存数据。

具体到 campus_go：`GetNotifications` handler 直接从 `notifications` 表查询，但如果前端 Flutter 的 `NotificationProvider` 使用了本地状态缓存（如 `ListView.builder` 的 `itemBuilder` 不重新请求数据），标记已读成功后没有刷新列表数据源。

**更可能的根因（双后端）:** 如果 Go 后端更新了 `is_read`，但 Python 后端的缓存层（如 Redis 或内存缓存）仍返回旧数据——但 campus_go 没有缓存层。所以最可能的根因是前端状态管理：`markAsRead` API 调用成功后，前端没有更新本地 `notifications` 列表状态。

**正确修复:** 前端 `markAsRead` 成功后调用 `setState` 或状态管理器的 `refreshNotifications()`。或后端 `GET /api/notifications` 加 `Cache-Control: no-cache` 响应头。

**文件:** 前端 `campus_app/lib/providers/notification_provider.dart` + 后端 `campus_go/internal/handlers/dashboard.go:116-143`

**评分要点:**
- 分类: T5 — 状态同步问题（数据库已更新但展示不一致） (1pt)
- 证据: 详情页显示已读但列表页显示未读 + 数据库确认已读 (1pt)
- 根因: 前端本地状态未在 markAsRead 后刷新，或双端点数据源不一致 (2pt)
- CF: 前端 markAsRead 后刷新列表 → 两页状态一致 (1pt)
- 修复: 前端状态刷新或后端加 Cache-Control (1pt)
