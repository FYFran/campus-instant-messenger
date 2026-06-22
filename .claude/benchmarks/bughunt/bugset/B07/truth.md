# B07 — Ground Truth

**Type:** T6（特定环境才触发 — CI 环境 vs 本地环境）

**根因:** Go 1.23 改变了 `database/sql` 包中 `Rows.Scan()` 对 NULL 的处理行为。Go 1.22 中 NULL 扫描到 `*string` 返回空字符串，Go 1.23 中返回 error。CI 中测试用的 SQLite 内存数据库的表结构与生产 PostgreSQL 不完全一致（SQLite 不支持某些字段类型），导致某些字段在 SQLite 中为 NULL。Go 1.22 容错，Go 1.23 严格报错。

**正确修复:** 
1. CI 测试改用 PostgreSQL testcontainer 或统一 SQLite schema
2. 所有 `Scan()` 目标使用 `sql.NullString` 等可空类型

**评分要点:**
- 分类: T6 (1pt)
- 证据: 环境 diff + Go 版本对比 (1pt)
- 根因: Go 1.23 NULL 处理变更 + SQLite schema 不一致 (2pt)
- CF: 统一环境→测试通过 (1pt)
- 修复: sql.NullString (1pt)
- 链完整 (1pt)
