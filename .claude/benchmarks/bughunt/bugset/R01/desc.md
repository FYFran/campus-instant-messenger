# R01 — R0: Missing Authentication on Sensitive Endpoint

## Bug 描述

campus_go 有一个管理统计端点，返回系统用户统计和活动数据。执行安全审计，检查此端点是否被正确保护。尝试从外部（无认证）访问此端点，确认是否存在认证绕过漏洞。

目标端点：`GET /api/admin/stats`

## 审计范围

- campus_go 后端代码在 `f:/ClaudeFiles/campus_go/`
- 生产服务器: 139.196.50.134
- 主要审计: 路由注册 + middleware 配置
- 次要审计: 敏感数据暴露面
