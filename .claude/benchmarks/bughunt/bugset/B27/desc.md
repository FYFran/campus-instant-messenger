# B27 — T3: TokenLine 扣费成功但 API 调用失败

## Bug 描述

TokenLine 平台的用户报告：调用 AI API 时偶尔扣了 token 但没有返回结果。用户的余额减少了，但对话历史中没有对应的 AI 回复。用户感觉"被吞了 token"。不是每次都发生——大约 20 次调用出现 1 次。
