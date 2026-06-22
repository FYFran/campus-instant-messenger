# B01v2 — T0: nil deref through cache indirection

## Bug 描述

campus_go 的活动列表 API `/api/activities` 在服务器运行一段时间后（约30分钟后），偶尔开始返回 500 错误。刚启动时完全正常。重启后恢复正常，但30分钟后又开始 500。

日志显示 panic 在 `cache.go` 的 `GetCachedActivities` 函数，不是在 `activities.go`。看起来跟缓存过期有关。当缓存为空或过期时触发。
