# T02 — Ground Truth

**Type:** T1（竞态 — 条件触发空回复）

**根因:** `extractContent()` 函数在 `delta.content` 为 null 且 `delta.reasoning_content` 有值时，错误地将所有内容归类为"思考"。当模型交替返回 content 和 reasoning_content 时，中间状态导致累计内容为空。

**文件:** chat handler, extractContent()

**正确修复:** 同时检查 content 和 reasoning_content，任何非空值都计入可见内容。

**评分要点:**
- 分类: T1 — 偶尔出现，条件触发，不是每次 (1pt)
- 证据: 模型返回了 tokens 但前端空白 (1pt)
- 根因: extractContent 对 null content 处理错误 (2pt)
- CF: 修复后无空回复 (1pt)
- 修复: 正确处理 content+reasoning_content (1pt)
