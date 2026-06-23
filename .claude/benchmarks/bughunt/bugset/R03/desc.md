# R03 — R2: Replay Attack on Idempotent-Sensitive Operation

## Bug 描述

campus_go 的活动报名接口 `/api/activities/:id/signup` 是否防止重放攻击？同一个报名请求发送两次会发生什么？

测试：
- 构造一个标准报名请求
- 连续发送两次完全相同的请求（相同的 JWT token、相同的 body）
- 观察是否创建了重复的报名记录

检查服务端是否有 nonce/timestamp/idempotency-key 等防重放机制。
