# B03 — T2: multi-factor permission bypass

## Bug 描述

campus_go 中，college_admin 角色的用户有时能看到并操作其他学院的活动。权限系统设计是"college_admin 只能管自己学院"，但偶尔跨学院操作成功了。似乎跟活动所属学院名称包含特殊字符或跟管理员学院名称部分匹配有关。
