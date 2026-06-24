# B30 — T1: WebSocket 推送偶尔丢失消息

## Bug 描述

campus_go 的 WebSocket 实时推送偶尔丢消息。用户收到新通知的推送时，有时 WebSocket 连接正常但收不到消息。刷新页面（重新连接 WebSocket）后消息又出现了。不是每次都丢——大概 10 条消息丢 1-2 条。
