# T02 — T1: Reasoning Content Leaked to Chat

## Bug 描述

TokenLine 平台的 AI 聊天偶尔出现空回复——用户提问后模型不回答，聊天框显示空白。API 日志显示模型确实返回了 tokens，但前端渲染出来是空的。问题只在特定条件下触发。
