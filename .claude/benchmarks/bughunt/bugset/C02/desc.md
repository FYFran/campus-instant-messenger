# C02 — C1: Missing Input Validation

## Bug 描述

campus_go 的 API 端点在接受用户输入时，某些字段缺少长度/格式验证。审查代码找出至少一个接受用户输入但没有充分验证的端点。

重点关注：CreateActivity 的文本字段（title, description, location 等）是否有长度限制？
