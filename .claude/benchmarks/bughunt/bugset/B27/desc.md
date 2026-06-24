# B27 — T3: TokenLine 扣费成功但 API 调用失败

## Bug 描述

TokenLine 平台的用户报告：调用 AI API 时扣费发生在 API 调用之前。当 AI API 超时或失败时，token 已被扣除但用户没有收到任何回复。用户的余额减少了，对话历史中没有对应的 AI 回复。每次 API 失败都会触发。
