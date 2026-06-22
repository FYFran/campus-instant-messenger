# B02v2 — T1: cross-endpoint race with misleading constraint error

## Bug 描述

campus_go 的活动报名系统偶尔报 "UNIQUE constraint violation" 错误。错误发生在 `/api/activities/{id}/signup` 接口。前端显示"报名失败，请重试"，重试后通常成功。数据库日志显示有时两个请求在同一毫秒到达，都返回了"未报名"的检查结果。更奇怪的是，有时学生在 `/api/activities/{id}` 看到"已报名"状态，但 `/api/my-signups` 没有显示该报名。
