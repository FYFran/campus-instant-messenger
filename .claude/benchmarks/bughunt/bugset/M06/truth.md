# M06 — Ground Truth

**Type:** T3（静默数据错 — 推理内容被丢弃，无报错）

**根因:** SSE chunk 解析器只读取 `delta.content` 字段。推理模型（DeepSeek R1/Flash）将可见输出放在 `delta.reasoning_content` 中。当 `delta.content` 为 null/空时，解析器静默丢弃所有内容 → 用户收到空白回复。

**正确修复:** 解析器同时检查 `delta.content` 和 `delta.reasoning_content`，拼接两者。

**评分要点:**
- 分类: T3 — 无报错，特定条件下静默空白 (1pt)
- 证据: DevTools 有 SSE 数据但页面空白 + 仅推理模型触发 (1pt)
- 根因: 解析器只读 delta.content 忽略 delta.reasoning_content (2pt)
- CF: 对比两种模型的 response 字段 (1pt)
- 修复: 同时提取 content 和 reasoning_content (1pt)
