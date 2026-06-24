# G03 — Ground Truth

**Type:** G2 — 静默模型降级（Unmarked fallback to local model）

**根因:** 火眼 Gotcha#3 的实例化。当外部 API 调用失败（网络超时、rate limit、认证失败）时，火眼 fallback 到本地模型继续执行。但输出报告中没有标注 `Mode: single` 或标明使用了哪个模型。用户看到完整报告，不知道是低质量本地模型生成的。

具体：火眼的 external model 调用被 try-except 包裹，失败后切换 `model_mode = 'single'`，但 Phase 7 Write 阶段不检查 `model_mode`，输出中不标注实际使用的模型。

**验证:**
1. 检查火眼的模型调用代码
2. 模拟外部 API 超时 → 确认 fallback 生效
3. 检查输出报告 → 没有 "Mode: single" 标注
4. 对比：有标注 vs 无标注的报告看起来一模一样

**评分要点:**
- 分类: G2 (1pt)
- 证据: fallback 代码 + 输出缺失 model_mode (1pt)
- 根因: Phase 7 Write 不检查 model_mode (2pt)
- CF: 加标注 → 用户能看到降级信息 (1pt)
- 修复: Phase 7 强制输出 `## Mode: {single|engine}` + 模型名称 (1pt)
- 防御建议: 所有外部依赖失败都应显式标注 (1pt)
- 链完整 (1pt)
