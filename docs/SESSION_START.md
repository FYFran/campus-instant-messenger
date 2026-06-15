# TokenLine 每日启动

> 上次: 2026-06-15 全天 v2.13 完成, v3.0 方案就绪待实施

---

## 开场提示 (复制给新对话)

```
TokenLine v2.13 → v3.0。上次完成v2.13全部改动+部署，
并写完v3.0完整设计文档 docs/TOKENLINE_V3_PLAN.md。

服务器 47.82.103.247，2核4G HK轻量 67元/月，
Go /app/rewriter-go/，前端 /app/static/，
DB SQLite /app/new-api/data/tokenline.db。
Gotenberg Docker :3200，New API Docker :3100。
Dodo支付生产环境已就绪。
云片SMS tpl_id=6416850 SUCCESS 余额100.5元。
admin面板 /admin.html (密码 tokenline2026)。

设计系统：暖白#faf9f6 + 炭黑#1a1c2c + 金棕#b8975a，Inter字体。
3层定价：Flash(19.9K-99.9K) 满血(189.9K-999.9K) Pro(399K-3.5M)。
双币系统：flash_balance + pro_balance 分离。
```

---

## 服务器

- 47.82.103.247 | root | SSH Key
- 2核4G HK轻量 30G磁盘 200Mbps
- Go: /app/rewriter-go/ | systemctl restart rewriter | 端口9100
- 前端: /app/static/ | nginx reload
- DB: /app/new-api/data/tokenline.db (每日3:05备份, 保留7天)
- Gotenberg: Docker 127.0.0.1:3200 (PDF导出)
- New API: Docker 127.0.0.1:3100 (DeepSeek代理)
- 备份timer: tokenline-backup.timer ✅

## 云片SMS

- API Key: b0f46c521929478ed0e248c1013a4cad
- 模板ID: 6416850 (SUCCESS) — `[TokenLine] Kode verifikasi Anda: #code#. Jangan berikan kode ini kepada siapapun.`
- 余额: 100.5 CNY (充值后)
- 告警线: <20 CNY
- 每条印尼短信: 0.50 CNY

## 页面清单 (12页, 全部200)

| 路径 | 文件 | 功能 |
|------|------|------|
| / | index.html | 首页, 暖白设计 |
| /login.html | login.html | 登录, 忘记密码→/reset-password.html ✅ |
| /register.html | register.html | 注册+手机号+OTP验证 ✅ |
| /chat/ | chat/index.html (chat-pro) | 6模式+12模板+SSE流式+导出+文件上传+CrossRef |
| /dashboard.html | dashboard.html | 仪表盘(退出+头像待修) |
| /topup.html | topup.html | 6套餐(待改三组) |
| /reset-password.html | 新建 | 密码重置 ✅ |
| /refund.html | refund.html | 退款政策(待改写) |
| /about.html | about.html | 关于 |
| /tos.html | tos.html | 条款 |
| /privacy.html | privacy.html | 隐私 |
| /compare.html | compare.html | 对比 |

## 后端API (15个端点)

| 端点 | 功能 | 状态 |
|------|------|------|
| POST /api/auth/register | 注册 | ✅ |
| POST /api/auth/login | 登录 | ✅ |
| GET /api/me | 用户信息 | ✅ (待加双余额) |
| POST /api/chat | SSE聊天 6模式 | ✅ (待改双扣费) |
| GET /api/chat/history | 对话历史 | ✅ |
| POST /api/export | PDF导出(Gotenberg) | ✅ |
| GET /api/templates | 12模板列表 | ✅ |
| GET /api/citation/search | CrossRef引用 | ✅ |
| POST /api/upload | 文件上传(txt/docx) | ✅ |
| POST /api/payment/create | 创建支付 | ✅ (待改三组pack) |
| POST /api/payment/callback | Dodo回调 | ✅ (待改双余额credit) |
| POST /api/payment/midtrans-callback | Midtrans回调 | ✅ |
| GET /api/payment/methods | 支付方式列表 | ✅ |
| POST /api/auth/send-otp | 发送OTP(云片) | ✅ |
| POST /api/auth/verify-otp | 验证OTP | ✅ |
| POST /api/feedback | 意见箱 | ✅ |
| GET /api/packs | 套餐列表 | ✅ (待改三组) |
| GET /api/health | 健康检查 | ✅ (4xx/5xx拆分) |
| GET /api/admin/balances | 管理面板余额 | ✅ |
| ~~POST /api/me/refund~~ | 退款 | ❌ v3.0删 |

## 数据库

- 3用户: demo@tokenline.top / FYFran / test@tokenline.top
- 5对话 10消息 0支付
- 备份: /app/new-api/data/backups/tokenline_YYYYMMDD_HHMMSS.db.gz
- subscriptions表: token_balance (待加 flash_balance + pro_balance)
- payments表: 待加 pack_type

## 安全层

- JWT HS256 + 7天
- 4xx/5xx拆分统计
- IDOR已修(chat.go +conversation所有权检查)
- XSS已修(export.go +HTMLEscapeString)
- WAL权限已修(syscall.Umask(0077))
- OTP防爆: 5次失败锁定 + 60s冷却
- 全端点rate limit
- nginx: HSTS/CSP/X-Frame/nosniff/XSS-Protection
- fail2ban: sshd + nginx-http-auth + nginx-botsearch
- admin面板auth: X-Admin-Key header (已修)

## v2.13 完成清单

- 健康监控4xx/5xx拆分 (停止假报警)
- IDOR修复 (chat所有权验证)
- XSS修复 (PDF导出HTML转义)
- WAL权限修复 (umask 0077)
- SMS冷却修复 (密码重置漏了checkCooldown)
- Feedback权限修复 (feedback.txt chown)
- Midtrans支付代码就绪 (缺key)
- SQLite每日备份timer
- 云片模板6416850 SUCCESS + 余额100.5元
- 部署chat-pro为聊天主页面
- 部署dashboard/refund/about页面
- 新建reset-password.html
- 注册页+手机号+OTP流程
- 文件上传后端+前端 (txt/docx)
- CrossRef引用API + 前端riset模式自动调用
- GoatCounter脚本 (需注册账号)
- Admin面板中文化 + 安全修复(Header传key)
- 登录页忘记密码链接修复
- 所有页面favicon补全
- 服务器旧bak文件清理
- 测试数据清理 (119→3用户)
- 完整财务模型 + CNY定价方案

## v3.0 待实施 (设计文档: docs/TOKENLINE_V3_PLAN.md)

14个文件，~920行改动。按文档实施：
1. 数据库迁移 (4条ALTER TABLE)
2. 后端6文件 (pay/chat/user/midtrans/admin_balance/main)
3. 前端8文件 (success新建 + admin重写 + topup/chat/index/dashboard/refund改)

## 关键文件位置

| 文件 | 用途 |
|------|------|
| docs/TOKENLINE_V3_PLAN.md | v3.0完整实现方案 |
| _research/rewriter-go/ | Go后端源码 (本地) |
| _research/chat-pro.html | 聊天页源码 |
| _research/admin_panel.html | 管理面板源码 |
| _research/pricing_model.py | 定价模型脚本 |
| _research/tokenline_finance.py | 财务分析脚本 |
| _research/register.html | 注册页源码(已加手机+OTP) |
| _research/login.html | 登录页源码 |
| _research/reset-password.html | 密码重置页源码 |
| justfile | 命令入口 (无tokenline target, 手动scp+ssh) |
