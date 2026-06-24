# B05 — Ground Truth

**Type:** T4（昨天还好好的 → git bisect + 配置变更追踪）

**根因:** 服务器重启时 nginx 配置被回退到旧版本，旧配置中 `proxy_pass` 指向了已经下线的 Python 后端（port 9500）而非当前的 Go 后端（port 9501）。Go 后端正常运行但请求根本没到达。

**正确修复:** 恢复 nginx 配置中 proxy_pass 指向 9501，并设置配置文件的版本控制。

**评分要点:**
- 分类: T4 (1pt)
- 证据: git log + 服务器重启时间线 (1pt)
- 根因: nginx proxy_pass 指向错误端口 (2pt)
- CF: 改回 9501→刷新正常 (1pt)
- 修复: nginx 配置恢复 (1pt)
- 链完整 (1pt)
