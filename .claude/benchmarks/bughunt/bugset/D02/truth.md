# D02 — Ground Truth

**Type:** D1 — 冒烟测试跳过（No endpoint health check after deploy）

**根因:** 布阵 Gotcha#2 的实例化：部署脚本在 `nginx -s reload` 后只检查 nginx 进程存在（`pgrep nginx`），不 curl 实际后端。如果新代码有启动失败（端口冲突、SQL migration 失败、import 错误），nginx 进程仍然活着但返回 502。

具体：P5 冒烟阶段缺失。部署脚本没有 `curl -f http://127.0.0.1:9501/api/health && echo OK || echo FAIL` 这样的端点验证。

**验证:**
1. 检查部署脚本的 P5/P4 阶段
2. 确认只检查进程，不检查端点响应
3. 模拟：部署有语法错误的代码 → nginx OK 但 /api/health → 502 → 部署脚本仍报 SUCCESS

**评分要点:**
- 分类: D1 (1pt)
- 证据: 脚本只有 pgrep 没有 curl health check (1pt)
- 根因: P5 冒烟阶段缺失端点验证 (2pt)
- CF: 加 curl health check → 502 被检测到 → 触发回滚 (1pt)
- 修复: 部署脚本加 curl -f /api/health + /api/activities 验证 (1pt)
- 防御建议: P5 标准化 — 至少 3 个关键端点冒烟 (1pt)
- 链完整 (1pt)
