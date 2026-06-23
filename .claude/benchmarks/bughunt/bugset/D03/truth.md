# D03 — Ground Truth

**Type:** D2 — 中止条件缺失（No automated abort on pre-flight failure）

**根因:** 布阵 Iron Law 违反。部署脚本中 pre-flight 检查（备份新鲜度、磁盘空间、服务状态）在失败时只打印 WARNING 但不 exit 1。脚本继续执行部署。缺乏明确的 abort condition 列表和自动中止逻辑。

具体：`check_disk_space()` 在磁盘 < 10% 时 echo "WARNING: low disk" 但 return 0，部署继续。没有 "ABORT_IF: disk<5%, backup_age>1h, service_not_responding" 这样的显式中止条件清单。

**验证:**
1. 检查部署脚本的错误处理
2. 找到至少一个 pre-flight check 在失败时仍 return 0
3. 证明可以在 pre-flight WARNING 状态下完成部署

**评分要点:**
- 分类: D2 (1pt)
- 证据: pre-flight check 失败但 return 0 → 部署继续 (1pt)
- 根因: 无显式 ABORT_IF 清单 + pre-flight 不阻断 (2pt)
- CF: 加 ABORT_IF + set -e → pre-flight 失败阻断部署 (1pt)
- 修复: 定义 ABORT_IF 条件清单 + pre-flight failure → exit 1 (1pt)
- 防御建议: Iron Law 实施 — 每个红线有自动化门禁 (1pt)
- 链完整 (1pt)
