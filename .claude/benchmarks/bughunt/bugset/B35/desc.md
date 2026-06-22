# B35 — T7: NOT_A_BUG — scope_type='all' 活动跨学院可见被误报权限漏洞

## Bug 描述

安全审查报告标记 campus_go 存在"权限绕过漏洞"：`scope_type='all'` 的活动对所有学院的学生可见，即使学生的学院与活动的 `college` 字段不匹配。审查者认为 `college_admin` 也可以看到和操作不属于自己学院的 scope_type='all' 活动。这被标记为 HIGH severity。
