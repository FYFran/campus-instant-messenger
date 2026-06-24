# C01: 提交前审查 — 缺少FOR UPDATE的并发写

## Bug描述
审查signup handler的代码变更。两个用户同时报名同一活动时可能超过max_participants。

## 语言
Go

## 难度
medium
