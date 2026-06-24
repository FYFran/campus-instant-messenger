# B03 — T0: missing college filter in ListActivities

## Bug 描述

campus_go 中，college_admin 角色的用户能看到并操作其他学院的活动。权限系统设计是"college_admin 只能管自己学院"，但活动列表 API `/api/activities` 对所有 college_admin 返回了全校所有学院的活动。ApproveActivity / RejectActivity 等管理接口也有同样的跨学院操作问题。
