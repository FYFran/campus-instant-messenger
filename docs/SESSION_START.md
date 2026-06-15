# TokenLine 每日启动

> 上次: 2026-06-15 全天深度改造 v2.11 | 复制下面给新对话

---

## 开场提示

```
继续TokenLine全栈。上次2026-06-15下午完成v2.12，
改动：清理+export修复+限流+nginx反爬+云片SMS模板提交。

服务器 47.82.103.247，后端Go /app/rewriter-go/，
前端 /app/static/，DB SQLite /app/new-api/data/tokenline.db。
Gotenberg PDF导出在Docker :3200。
24/24冒烟全过，5页面200 OK。

设计系统：暖白#faf9f6 + 炭黑#1a1c2c + 金棕#b8975a，Inter字体，
玻璃态导航，Bento网格，3级会员(Silver-Flash/Gold-Pro)。

当前102用户136消息0支付。WhatsApp OTP未通(Facebook被墙)。
云片SMS模板 tpl_id=6416790 CHECKING审核中。
```

---

## 服务器

- 47.82.103.247 | root | SSH Key
- Go: /app/rewriter-go/ | systemctl restart rewriter
- 前端: /app/static/ | nginx reload
- DB: /app/new-api/data/tokenline.db (每日3点备份)
- Gotenberg: Docker 127.0.0.1:3200 (PDF导出)
- New API: Docker 127.0.0.1:3100 (DeepSeek代理)

## 页面清单

| 路径 | 文件 | 功能 |
|------|------|------|
| / | index.html (v12) | 首页,暖白高级,3级会员,真实功能声明 |
| /login.html | login-premium.html | 统一设计,API登录 |
| /register.html | register-premium.html | 密码强度,API注册 |
| /chat-pro.html | chat-pro-v3.html | SSE流式,6模式,模板API,导出API |
| /dashboard.html | dashboard-v2.html | 真实数据,柱状图,活动列表 |

## 后端API

| 端点 | 功能 | 状态 |
|------|------|------|
| POST /api/auth/register | 注册 | ✅ |
| POST /api/auth/login | 登录 | ✅ |
| GET /api/me | 用户信息 | ✅ |
| POST /api/chat | SSE聊天 | ✅ 6模式 |
| GET /api/chat/history | 对话历史 | ✅ |
| POST /api/export | PDF导出(Gotenberg) | ✅ |
| GET /api/templates | 12模板列表 | ✅ |
| POST /api/payment/create | 创建支付 | ✅ |
| POST /api/payment/callback | 支付回调 | ✅ |
| POST /api/auth/send-otp | 发送OTP(云片) | ⚠️ 模板审核中 |
| POST /api/auth/verify-otp | 验证OTP | ✅ 5次防爆 |

## 安全层

- safety.go: FilterContent + SanitizePrompt (印尼内容过滤)
- JWT HS256 + 7天过期 + token_version
- OTP 5次失败锁定 + phone_verified检查
- 全端点rate limit: auth 2/s, chat 5/s, export 5/s
- nginx: HSTS/CSP/X-Frame/nosniff/XSS-Protection
- fail2ban: sshd + nginx-http-auth + nginx-botsearch + nginx-limit-req
- Go后端: export/template handler 最新

## 设计系统

```
背景: #faf9f6 (暖白)
文字: #1a1c2c (炭黑)
点缀: #b8975a (金棕,仅Pro/高亮)
字体: Inter 400-800
卡片: white bg, 1px rgba(0,0,0,.05), 1.5rem radius
按钮: btn-dark(#1a1c2c), btn-gold(#b8975a), btn-ghost(border)
导航: glass blur(16px) fixed top
间距: section 12rem, card 2.5rem, grid gap 1.5rem
会员: ●Gratis ▲Silver(Flash) ★Gold(Pro)
```

## 关键文件

| 文件 | 用途 |
|------|------|
| _research/tokenline-v12.html | 首页最新版 |
| _research/chat-pro-v3.html | 写作台最新版 |
| _research/dashboard-v2.html | 仪表盘最新版 |
| _research/login-premium.html | 登录页 |
| _research/register-premium.html | 注册页 |
| _research/rewriter-go/internal/handler/export.go | PDF导出handler |
| _research/rewriter-go/internal/handler/safety.go | 内容过滤器 |
| _smoke_test.py | 24项冒烟测试 |

## 当前生产状态

```
24/24冒烟全过
0虚假声明 0合规风险
5页面200 OK全部统一设计
DB: 102用户 136消息 0支付
SSL: Let's Encrypt 9月到期
磁盘: 17G/30G (59%)
Docker: new-api + gotenberg running
Go后端: v2.12 — 新增export markdown渲染+限流+admin路由+cost/revenue追踪
Nginx: bot-block+AI爬虫拦截+honeypot+static限流
```

## v2.12 改动清单 (2026-06-15下午)

| 改动 | 说明 |
|------|------|
| 清理 | firefox.exe(84MB)+bak文件+chat_server.go+main_server.go+anti-bot.conf |
| export.go | `**bold**`→`<strong>`, `` `code` ``→`<code>`, `# heading`→`<h1>` |
| main.go | +export/template handler, +pubLimiter, +admin路由, +cost/revenue追踪, +monitor |
| 限流 | /templates+/packs+/feedback 10/s burst 20 |
| nginx | bot-block.conf替代anti-bot.conf, 攻击工具403, AI爬虫403, 蜜罐444, 合法bot放行, static限流30r/s |
| ka/权限 | chmod 755修复Permission denied |
| 云片SMS | API提交模板 tpl_id=6416790, check_status=CHECKING |

## 已知非bug

| 问题 | 说明 |
|------|------|
| code=5 `未找到匹配的模板` | 云片模板CHECKING中，审核通过后自动消失 |
| nginx SSL错误 (bad key share/bad record type) | 外网扫描器，正常现象 |
| nginx conflicting server name | reload竞态，无害 |

## 待修

| 优先级 | 项目 |
|--------|------|
| 🔴 | 云片SMS模板审核通过后改otp.go绑tpl_id |
| 🔴 | WhatsApp OTP (Facebook被墙，需梯子+印尼SIM卡) |
| 🟡 | Pro功能: CrossRef引用API + 文档上传 |
| 🟡 | SQLite→PostgreSQL迁移 |
| 🟡 | 0支付→开始推用户、集成支付回调 |
| 🟢 | 全页面i18n集成(tokenline-i18n.js已部署) |
| 🟢 | Export endpoint curl实战验证 |
