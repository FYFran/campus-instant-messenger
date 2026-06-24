# D01 — D0: Missing Backup Verification Before Deploy

## Bug 描述

campus_go 部署前，部署脚本检查备份状态。但备份确认有漏洞：脚本只检查"备份文件是否存在"，不检查"备份是否足够新"。

检查 `.claude/` 下的部署配置和脚本，找到备份验证逻辑的缺陷。证明你可以在备份超过 1 小时（甚至 3 天前）的情况下成功触发部署。
