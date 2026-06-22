# M08 — T0: Global JSON Middleware Blocks Non-JSON Requests

## Bug 描述

文件上传功能完全不工作——每次返回 415 Unsupported Media Type。短信回调和支付网关回调也返回 415。所有非 JSON Content-Type 的请求都被拒绝。
