# B01v2 — Ground Truth

**Type:** T0（稳定复现 — 缓存过期后必 500）

**根因:** `ListActivities` handler 在数据库返回空结果时，`rows` 对象在某些驱动版本下为 nil。修复版本添加了 `rows.Err()` 检查，但缓存层 `GetCachedActivities` 在缓存 miss 时调用 handler 并将 nil `rows` 存入缓存。后续读取时，缓存返回 nil 切片，`range` 操作 panic。

第一层（handler）: `db.Query()` 返回空 rows → 未检查 `rows.Err()` → nil 传播
第二层（cache  indirection）: nil 被缓存 → 后续请求直接 panic 在 cache.go → 症状指向缓存而非原始 bug

这使 debug 更难：panic 堆栈指向 cache.go（误导信号），实际问题在 activities.go 的 rows 处理。

**正确修复:** 
1. activities.go: `for rows.Next()` 后添加 `if err := rows.Err(); err != nil { return err }`
2. cache.go: 缓存前检查结果是否为 nil/empty，不缓存 nil 值

**评分要点:**
- 分类: T0 — 识别稳定复现模式 (1pt)
- 证据: 复现步骤 + cache miss→panic 追踪 (1pt)
- 根因: 双重追踪到 activities.go rows.Err() 缺失 + cache 缓存 nil (2pt)
- CF: 两个独立修复各验证 (1pt)
- 修复: rows.Err() + cache nil guard (1pt)
- 链完整 (1pt)
