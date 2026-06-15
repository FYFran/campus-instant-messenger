# TokenLine 每日启动

> 上次: 2026-06-15 全天深审 | 复制粘贴给Claude Code开始

---

## 开场提示（复制这段给新对话）

```
继续TokenLine全栈审计。上次完成了8轮修复(8 commits)，24/24冒烟测试全过。
基础代码在 _research/rewriter-go/，生产服务器47.82.103.247。
继续查漏补缺——安全、UX、性能、代码质量四个方面全面审查。
```

---

## 服务器

- 47.82.103.247 | root | SSH Key | 密码已轮换(记在memory)
- Go: /app/rewriter-go/ | systemctl restart rewriter
- 前端: /app/static/ | nginx reload
- DB: /app/new-api/data/tokenline.db (SQLite, 每日3点备份到backups/)
- 管理: https://tokenline.top/admin.html 密码 tokenline2026

## 已完成 (8次提交, 41修复)

### 安全 (18项)
- JWT算法锁定HS256 | CORS限制tokenline.top | 聊天XSS HTML转义
- bcrypt降级SHA256(不崩) | OTP常量时间比较+60s冷却+空号码防护
- 安全头(HSTS/CSP/nosniff/X-Frame/Permissions)
- OTP端点加rate limit防暴力破解 | JWT过期30d→7d
- 注册限流收紧2/s burst 3

### 后端 (10项)
- Dodo回调竞态修复(UPDATE WHERE pending原子化)
- DB连接池1→8(WAL并发) | 7个索引(email/phone/status/paid_at)
- chat.go重写(maxOut int→string修复,印尼安全规则系统提示,对话创建错误检查,Token扣减RowsAffected)
- feedback.go修复(500状态码+字段验证+换行注入+0600权限)
- /api/me新增phone+phone_verified | 补全/api/me/balance+/api/packs路由

### 前端 (8项)
- 聊天页v3: 日期分组对话+手机滑入抽屉+搜索+AI快捷操作(Ringkas/Perbaiki/Ulang)
- 个人中心弹窗(Email/Token/HP/套餐/改密码) | 充值按钮常驻侧栏
- 手机底部导航4入口 | 服务器同步对话历史
- 登录页"Lupa Password"链接 | about.html+docs.html补全

### 基础设施 (5项)
- UFW防火墙启用(22/80/443/8888) | fail2ban部署(sshd jail)
- nginx: SSL仅TLSv1.2/1.3 + gzip JSON/JS/CSS | DB每日备份cron + 磁盘80%预警
- root密码轮换 + 63脚本硬编码清除 | PWA图标SVG渐变

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
0个已知可利用安全漏洞
服务正常运行
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
