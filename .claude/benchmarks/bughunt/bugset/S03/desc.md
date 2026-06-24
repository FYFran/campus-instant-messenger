# S03 — S2: IDOR in activity modification

## Bug 描述

campus_go 中，college_admin 可以修改其他学院管理员创建的活动。通过直接调用 `/api/admin/activities/{id}/modify` 接口并传入任意活动 ID，没有检查该活动是否属于当前管理员的学院。
