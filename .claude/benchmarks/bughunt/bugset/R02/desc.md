# R02 — R1: Privilege Escalation via Chained Vulnerabilities

## Bug 描述

campus_go 中，普通学生用户能否获取 college_admin 或 school_admin 权限？检查是否存在从低权限到高权限的攻击链。

已知：
- `/api/activities` 对任何登录用户返回活动列表
- 活动详情包含创建者和审核者信息
- 存在一个用户角色更新接口

找出一条从 student → college_admin 的完整攻击链，要求每步都可复现。
