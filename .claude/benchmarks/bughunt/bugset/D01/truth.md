# D01 — Ground Truth

**Type:** D0 — 备份验证缺陷（Accepts stale backup）

**根因:** 布阵 Gotcha#3 的实例化：备份确认只检查文件存在性（`test -f backup.tar.gz`），不检查时间戳。3 天前的备份也能通过 pre-flight 检查。缺乏 `find backup.tar.gz -mmin -60` 或等效的新鲜度检查。

**验证:**
1. 检查部署脚本中的备份验证逻辑
2. 确认只用了 existence check 而非 freshness check
3. 构造场景：3 天前的备份放在那里 → pre-flight PASS

**评分要点:**
- 分类: D0 (1pt)
- 证据: 脚本只检查 -f 不检查 -mmin (1pt)
- 根因: 备份新鲜度检查缺失 (2pt)
- CF: 加 freshness check → stale backup 被拒绝 (1pt)
- 修复: find backup -mmin -60 或 stat 检查时间戳 (1pt)
- 防御建议: pre-flight checklist 加备份新鲜度项目 (1pt)
- 链完整 (1pt)
