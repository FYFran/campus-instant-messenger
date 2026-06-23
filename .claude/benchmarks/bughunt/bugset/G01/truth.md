# G01 — Ground Truth

**Type:** G0 — 维度覆盖缺失（Missing "database migration strategy" dimension）

**根因:** 火眼 Gotcha#1 的实例化。火眼默认覆盖代码质量、安全、测试、文档、部署配置等维度，但缺少"数据库迁移策略"维度。campus_go 的 `schema_init.sql` 是手动维护的，没有 migration 版本控制（如 golang-migrate、flyway），也没有回滚策略。如果火眼不扫描此维度，这个 gap 不会被报告。

具体：campus_go 的数据库 schema 通过手动 SQL 文件管理，没有任何 migration tooling 或版本追踪。这是一个 P1 gap（数据丢失风险），但默认维度不会发现它。

**验证:**
1. 检查火眼的 Phase 1 PreScan 维度列表
2. 确认没有 "database migration" 维度
3. 手动检查 campus_go → 发现 schema_init.sql 无版本控制
4. 证明 gap 确实存在但火眼默认配置扫不到

**评分要点:**
- 分类: G0 (1pt)
- 证据: PreScan 维度列表缺少 migration (1pt)
- 根因: 维度覆盖不完整 — 不包含 DB migration (2pt)
- CF: 添加 migration 维度 → 发现 P1 gap (1pt)
- 修复: 火眼维度列表添加 database migration strategy (1pt)
- 防御建议: 定期审计维度覆盖 vs 行业最佳实践 (1pt)
- 链完整 (1pt)
