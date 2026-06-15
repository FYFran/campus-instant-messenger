# TokenLine 每日启动

> 上次: 2026-06-15 第10轮安全深审 | 复制粘贴给Claude Code开始

---

## 开场提示（复制这段给新对话）

```
继续TokenLine全栈。上次2026-06-15完成第10轮深审(10 commits b8a7f59)，
security-auditor + code-reviewer 双agent并行扫出23项问题，
全部修复部署：内容过滤启用 + OTP防爆 + phone_verified检查 + defer rows.Close。
24/24冒烟全过，redteam扫描2项误报(本地MCP+Google Fonts URL)。
生产47.82.103.247，后端Go /app/rewriter-go/，前端/app/static/。
待修: WhatsApp OTP(Facebook被墙) + 云片模板审核 + SQLite→PG + JWT httpOnly。
```

---

## 服务器

- 47.82.103.247 | root | SSH Key | 密码已轮换(记在memory)
- Go: /app/rewriter-go/ | systemctl restart rewriter
- 前端: /app/static/ | nginx reload
- DB: /app/new-api/data/tokenline.db (SQLite, 每日3点备份到backups/)
- 管理: https://tokenline.top/admin.html 密码 tokenline2026

## 已完成 (10次提交, 53修复)

### v2.10 — 第10轮安全深审 (2026-06-15, b8a7f59)
- 🔴 security-auditor + code-reviewer 双agent并行深审
- 🔴 内容过滤启用: FilterContent + SanitizePrompt 纵深防御(之前被禁用只靠DeepSeek)
- 🔴 OTP暴力破解防护: 5次失败后OTP自动作废
- 🔴 RequestPasswordReset加phone_verified检查(之前可绕过未验证手机号重置密码)
- 🟠 user.go 4处rows.Close()→defer(防连接泄漏)
- 🟠 替换自定义contains()→strings.Contains(标准库)
- 🟡 safety.go创建(词边界匹配减少误杀) + 部署到生产

### v2.9 — 前9轮修复 (9 commits)
- 安全18项: JWT HS256锁定, CORS tokenline.top, XSS转义, bcrypt降级, OTP常量时间比较, 安全头, rate limit, JWT 7d, 注册限流2/s
- 后端10项: Dodo回调竞态, DB WAL+连接池, 7索引, chat重写, feedback修复, API补全
- 前端8项: 聊天v3, 个人中心, 底部导航, 对话同步, 页面补全
- 基础设施5项: UFW, fail2ban, nginx TLS+gzip, DB备份, 密钥轮换, PWA图标

## 待修 (需要新开发，不是bug)

| 优先级 | 项目 | 说明 |
|--------|------|------|
| 🔴 | WhatsApp/Facebook注册 | 需要翻墙浏览器或朋友帮忙，拿PHONE_NUMBER_ID+ACCESS_TOKEN |
| 🟡 | 云片SMS模板审核 | API key已配(b0f46c5...)，等模板通过就能发 |
| 🟡 | SQLite→PostgreSQL | 生产并发瓶颈，SQLite序列化所有写操作 |
| 🟡 | JWT→httpOnly Cookie | 防XSS窃取token，需前后端全改 |
| 🟡 | 产品SKU统一 | topup.html和admin.html定价不一致（admin未部署到生产） |
| 🟡 | 内容过滤器升级 | 子串匹配有误杀，需NLP方案 |
| 🟢 | 单元/集成测试 | 只有冒烟测试，无覆盖率 |
| 🟢 | 外部监控告警 | Prometheus/Grafana |

## 当前生产状态

```
24/24冒烟测试全过
0个已知可利用安全漏洞 (本次深审修复4项高危)
服务正常运行 v2.10
DB: 84用户 104消息 0支付
SSL: Let's Encrypt 9月到期
磁盘: 14G/30G (51%)
```

## 关键文件映射

| 文件 | 用途 |
|------|------|
| _research/rewriter-go/ | Go后端完整代码 |
| _research/rewriter-go/main_server.go | 生产服务器用的main.go |
| _research/rewriter-go/internal/handler/chat_server_fixed.go | 修复版chat.go |
| _research/chat-final.html | 聊天页v3最终版 |
| _smoke_test.py | 24项冒烟测试 |
| memory/tokenline-credentials.md | 敏感凭证(勿泄露) |

## 已知代码分歧

服务器(/app/rewriter-go/)运行Xendit支付版本。
本地(_research/rewriter-go/)是Dodo支付版本。
两套config.go不同——修改时注意对齐。
