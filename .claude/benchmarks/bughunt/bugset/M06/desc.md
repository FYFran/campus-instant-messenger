# M06 — T3: SSE Parser Drops Reasoning Model Output

## Bug 描述

某些 AI 模型（特别是推理模型）的流式响应中，用户收到空白回复。API 明明返回了数据（可以在浏览器 DevTools 中看到 EventStream 有内容），但前端显示的是空的。普通模型正常，只有特定模型有问题。没有报错。
