# G02 — Ground Truth

**Type:** G1 — 交叉验证漏报（Single-dimension gap downgraded to LOW）

**根因:** 火眼 Phase 4 Confirm 要求 ≥2 个维度确认同一个 gap 才标记为 P0/P1。但某些 gap 天然只在一个维度可见（如：API 版本管理只在 API 维度可见，代码质量维度看不到）。这种情况下单维度 gap 被标记为 "LOW confidence — single dimension only"，可能被 Phase 5 忽略，导致真实 gap 漏报。

具体：火眼 Phase 4 的 cross-validation 逻辑中，如果 `confirming_dimensions < 2`，gap priority 被降级。但某些 gap 就是只在单一维度可见的。

**验证:**
1. 检查火眼 Phase 4 Confirm 的 cross-validation 阈值
2. 构造一个真实存在但只在一维可见的 gap
3. 跑火眼 → gap 被降级 → 最终报告不包含此 gap

**评分要点:**
- 分类: G1 (1pt)
- 证据: Confirm 阈值 ≥2 维度 + 单维 gap 被降级 (1pt)
- 根因: cross-validation 阈值不考虑单维专属 gap (2pt)
- CF: 加例外逻辑 → 单维高置信度 gap 仍上报 (1pt)
- 修复: single-dimension gap → 标记为 "SINGLE_SOURCE" 而非降级 (1pt)
- 防御建议: 人工 review 所有被降级的 gap (1pt)
- 链完整 (1pt)
