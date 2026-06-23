# Q01 — Ground Truth

**Type:** Q0 — 恒真检查（False-pass quality gate）

**根因:** `bughunt_ci.py` CIGate 类中 `min_avg_score` 阈值在 quick 模式下设为 4.0/8，但一个完全不相关的回答只要 chain 完整就能得 3 分（chain=1 + trace=1 + 空分类=0 + 空证据=0 → 加上 heuristic 补的 evidence=1 → 3/8）。阈值 4.0 允许大量 template 级别的输出通过，因为分类+证据+CF heuristic 会把空报告垫到 3-4 分。

实际上 quick mode 的 heuristic（evidence>20 chars→1, cf>30 chars→1, fix>20 chars→1）过于宽松——agent 输出任何超过 20 字的文本就能拿分，不管内容是否相关。

**验证:**
1. 构造一个 template 级别的 agent 输出（填满 chain 但内容不针对 bug）
2. 跑 quick mode 评分 → 得到 ~3-4 分
3. 对比 gate threshold 4.0 → PASS（应该 FAIL）

**评分要点:**
- 分类: Q0 恒真检查 (1pt)
- 证据: 构造 template 输出 → 证明 heuristic 过于宽松 (1pt)
- 根因: quick mode heuristic 只看长度不看内容 + threshold 太低 (2pt)
- CF: 提高 threshold 到 5.0 → template 被拦住 (1pt)
- 修复: heuristic 加内容相关性检查 + threshold 上调 (1pt)
- 防御建议: 定期审计 gate bypass 案例 (1pt)
- 链完整 (1pt)
