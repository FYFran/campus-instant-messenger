# T01 — Ground Truth

**Type:** T3（静默数据错 — reasoning_content 未过滤就展示）

**根因:** SSE 流式响应中，DeepSeek 推理模型的 `delta.reasoning_content` 字段被直接拼接到用户可见的响应中。`extractContent()` 函数未区分 `content` 和 `reasoning_content`，导致内部推理过程外泄。

**文件:** `extractContent()` in chat handler

**正确修复:** `extractContent()` 仅提取 `delta.content`，过滤 `delta.reasoning_content`。

**评分要点:**
- 分类: T3 — 无报错，特定模型才出现，内容泄露非 crash (1pt)
- 证据: Flash/Pro 模型 vs 普通模型对比 (1pt)
- 根因: reasoning_content 未被过滤 (2pt)
- CF: 过滤后用户只看到 content (1pt)
- 修复: 过滤 reasoning_content (1pt)
