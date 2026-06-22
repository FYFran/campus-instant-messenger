# B15 — T6: 通知列表中 is_read 字段显示异常

## Bug 描述

用户的系统通知列表 `/api/notifications` 中，所有通知的 `is_read` 字段始终为 `false`，即使用户已经点开阅读过。数据库中 `notifications.is_read` 列存储的是整数（0 或 1），但 API 返回的 JSON 中 `is_read` 始终是 `false`。日志中有 `scan error` 的记录。
