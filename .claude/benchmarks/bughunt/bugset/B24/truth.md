# B24 — Ground Truth

**Type:** T4（回归 — nginx 配置变更引入）

**根因:** nginx 配置中 `proxy_cache` 或 `proxy_buffering` 对 GET 请求意外启用了缓存。在最近的部署中，nginx 配置被修改为添加静态资源缓存，但 `location /api/` 块的缓存指令被错误地继承或全局缓存设置意外影响了 API 路由。

具体来说，`proxy_cache_valid 200 60s` 的全局设置导致返回 200 的 API 响应被缓存 60 秒。用户 POST 报名后的下一次 GET 请求命中缓存，返回报名前的旧列表。

**正确修复:**
```nginx
location /api/ {
    proxy_pass http://127.0.0.1:9501;
    proxy_cache off;           # API 响应不应缓存
    proxy_no_cache 1;          # 双重确保
    proxy_cache_bypass 1;
}
```

**文件:** `nginx-campus.conf` (location /api/ 块)

**评分要点:**
- 分类: T4 — 部署/配置变更引入，之前无此问题 (1pt)
- 证据: 1-2 分钟后刷新正确 + 定位到 nginx 缓存配置 (1pt)
- 根因: nginx-campus.conf — proxy_cache 意外应用于 /api/ 路由 (2pt)
- CF: 禁用 API 缓存 → POST 后 GET 立即返回新数据 (1pt)
- 修复: proxy_cache off + proxy_cache_bypass (1pt)
