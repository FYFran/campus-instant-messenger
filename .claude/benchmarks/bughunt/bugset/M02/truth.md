# M02 — Ground Truth

**Type:** T1（竞态 — TOCTOU race condition）

**根因:** IP 频率检查（SELECT COUNT）和账号创建（INSERT）是分离的数据库操作，不在同一事务中。并发请求同时通过 COUNT 检查 → 都认为未超限 → 都执行 INSERT。

**正确修复:** 用 BEGIN IMMEDIATE 事务包裹 ip_log INSERT + COUNT check + user INSERT，让并发请求串行化。

**评分要点:**
- 分类: T1 — 并发竞态 (1pt)
- 证据: 并发注册时 IP 限流偶尔失效 (1pt)
- 根因: SELECT COUNT + INSERT 分两次操作无事务保护 (2pt)
- CF: 事务化后同 IP 并发请求串行执行 (1pt)
- 修复: 事务包裹检查+写入 (1pt)
