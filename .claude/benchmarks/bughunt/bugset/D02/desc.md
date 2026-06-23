# D02 — D1: Skipped Smoke Test After Deploy

## Bug 描述

campus_go 部署后，nginx reload 成功就算部署成功。但缺少对实际 API 端点的冒烟验证——部署脚本没有在 reload 之后 curl 关键健康检查端点。

检查部署配置和脚本。证明 reload 成功 ≠ 服务正常，找出哪个关键端点可能在新部署后返回错误但不会被检测到。
