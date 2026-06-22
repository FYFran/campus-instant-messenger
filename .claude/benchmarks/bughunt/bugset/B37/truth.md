# B37 — Ground Truth

**Type:** T6（环境不匹配 — 生产 DB schema 列类型不同）

**TRAP:** 看起来像 T3 静默数据错误（"无报错数据为0"），实质是 T6 环境差异。生产数据库 `certificates.duration` 列是 VARCHAR(10)，开发环境是 DECIMAL(5,1)。Go 代码用 `rows.Scan(&duration)` 扫描 float64 → VARCHAR 列 → Scan 静默失败返回 0。日志中有 `sql: Scan error on column index 3` 但被忽略了。

**根因:** `certificates.go:73` 的 `rows.Scan(&cert.Duration)` 忽略 error 返回值。生产 migration 漏执行 → schema 不一致 → float64→VARCHAR scan 失败 → 0。

**正确修复:** 加 error check + 对齐生产 schema（`ALTER TABLE certificates MODIFY COLUMN duration DECIMAL(5,1)`）

**评分要点:**
- 分类: T6 — 识别出环境差异 (1pt)
- 证据: 两个环境对比 + 日志 scan error (1pt)
- 根因: production schema VARCHAR vs dev DECIMAL + Scan error 被忽略 (2pt)
- CF: 加 error check → panic/log → 暴露问题 (1pt)
- 修复: 加 error check + ALTER TABLE (1pt)
