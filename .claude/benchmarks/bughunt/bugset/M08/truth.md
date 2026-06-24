# M08 — Ground Truth

**Type:** T0（稳定复现 — 所有非 JSON 请求必 415）

**根因:** 全局 `requireJSON` 中间件对所有 POST/PUT/PATCH 请求检查 Content-Type: application/json。文件上传使用 multipart/form-data，外部回调使用 application/x-www-form-urlencoded → 中间件拒绝 → 415。中间件没有路由白名单机制。

**正确修复:** 中间件加白名单——文件上传路由和回调路由跳过 Content-Type 检查。

**评分要点:**
- 分类: T0 — 每次非 JSON 请求必 415 (1pt)
- 证据: 所有 multipart/form-data 请求返回 415 (1pt)
- 根因: requireJSON 中间件不区分路由类型，无白名单 (2pt)
- CF: 白名单后文件上传成功 (1pt)
- 修复: 中间件加 route whitelist (1pt)
