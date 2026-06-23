# S03 — Ground Truth

**Type:** S2（数据暴露 — 不安全的直接对象引用 IDOR）

**根因:** `activities_admin.go` ModifyActivity handler 只检查了用户角色是否为 `college_admin` 或以上，但没有验证目标活动是否属于该管理员的学院。攻击者可以通过枚举活动 ID 修改任意学院的活动。

**正确修复:** 在 ModifyActivity 的 SQL WHERE 子句中添加学院检查：`AND ($role = 'school_admin' OR college = (SELECT college FROM users WHERE id=$userID))`

**OWASP:** A01:2021 — Broken Access Control
