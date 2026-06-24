# B16 — Ground Truth

**Type:** T7（NOT_A_BUG — 正确的 Go 事务模式）

**根因:** 这是 Go 中处理数据库事务的标准惯用法（idiom），不是 bug。pgx 驱动中，`Rollback()` 在事务已 Commit 后调用是一个安全的 no-op——驱动检测到事务已提交，直接返回 nil，不产生任何效果。

这个模式的目的：确保任何 early return（如参数验证失败、查询错误等）在执行 `c.JSON(400/500, ...)` 之前自动回滚事务。如果函数成功执行到 `tx.Commit()`，则 defer 的 Rollback 变成无害的 no-op。

**为什么不是 bug:**
1. pgx 文档明确说明 `Rollback() after Commit() is a no-op`
2. 这是 Go 数据库事务的标准模式（见 pgx 官方示例）
3. 等价模式在所有 Go 数据库教程中推荐使用

**评分要点:**
- 分类: T7 — NOT_A_BUG，标准 Go 事务模式 (1pt 仅当正确识别为 T7)
- 证据: pgx 文档 + Go 社区惯例 + 事务生命周期分析 (1pt)
- 根因: 不存在 bug。defer Rollback + Commit 是 Go 推荐的 safe-transaction 模式 (2pt 仅当正确识别非 bug)
- CF: 无需修改 — 当前代码在生产环境中正常工作 (1pt)
- 修复: 无需修复 (1pt)
