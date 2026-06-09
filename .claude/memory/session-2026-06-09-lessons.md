---
name: session-2026-06-09-lessons
description: 6月9日全面安全审计+工业化升级的关键教训
metadata:
  type: feedback
---

## 做了什么
三轮红队攻击+修复，共修复137+漏洞，改48文件。动态QR码5秒刷新。Go/Python/Flutter全链路安全加固。

## 做得好的
- 并行agent效率高（审计4路、修复3路、红队4路同时打）
- 每个修复都有语法验证
- 追到文件:行号级别的具体问题
- 第三轮发现main_remote.py是生产文件(之前修了main.py白修)

## 关键教训

**Why:** 
1. main_remote.py被忽略了两轮——生产部署文件没被包含在审计范围。修了main.py两轮才发现服务器上跑的是另一个文件。
2. 密钥(.env的JWT_SECRET/DB_PASSWORD)只gitignore了但没轮换——如果服务器历史上被访问过，攻击者仍有密钥。
3. HTTPS只改了客户端，服务器证书可能不存在——会导致app连不上。
4. python-jose早已不维护、Go依赖有已知CVE、Flutter get包有不修的漏洞——都只标记了没替换。
5. 修复面太广，137+漏洞中有些是加装饰器(@limiter)的浅层修复，实际效果取决于服务器nginx配置。

**How to apply:**
- 审计/攻击之前先确定"生产跑的是什么文件" — 查deploy.py/server_setup.sh/nginx配置
- 改安全配置要确认服务器侧也改了（HTTPS→先确认TLS证书存在）
- 密钥轮换要实际做，不只是gitignore
- 依赖漏洞建专门的更新计划，不是标记了就过
- 每轮修复后跑campus_check做功能回归，不只是语法检查
- 拆main.py之前不要再往里加代码了
