# TokenLine 每日启动

> 上次: 2026-06-15 | 复制粘贴给Claude Code开始

---

TokenLine 印尼AI token平台。网站 tokenline.top 上线，Dodo支付生产模式就位。继续搞WhatsApp OTP。

## 当前进度

| 完成 | 项目 |
|------|------|
| ✅ | 网站全线上：首页/聊天(Markdown+代码高亮)/充值/管理面板 |
| ✅ | Dodo生产模式：API Key `3VYwkQDO-suv...` Product `pdt_0Nh2IBGF...` Webhook `whsec_ruLN...` |
| ✅ | 6档token包定价，利润率41-85%，账算透(¥人民币) |
| ✅ | 管理面板 admin.html 密码 `tokenline2026` 实时数据+预警 |
| ✅ | DeepSeek余额 ¥370 |

| 未完成 | 说明 |
|--------|------|
| ❌ WhatsApp OTP | 差 PHONE_NUMBER_ID + ACCESS_TOKEN |
| ❌ 安全修复 | bcrypt密码哈希、IDOR、CORS |

## WhatsApp OTP卡在哪

代码已写好（whatsapp.go、auth.go），差从Meta Developer拿两个token。卡在国内网络打不开developers.facebook.com。

**试过的方案：**
- v2rayN SOCKS5/HTTP代理 — 浏览器DNS泄露
- SSH SOCKS5隧道 — curl能通(200)，Edge不行
- 服务器playwright自动化 — Facebook反爬检测
- n.eko远程浏览器 — WebRTC穿透失败

**SSH SOCKS5已验证能通Facebook：**
```
ssh -D 10999 root@47.82.103.247  # 启动隧道
curl --socks5-hostname 127.0.0.1:10999 FB → 200 ✅
```
差一个**能正确代理DNS的浏览器**（Firefox勾"Proxy DNS when using SOCKS5"就行）

## 服务器

47.82.103.247 | root@Yf773711 | SSH Key已设
Go: /app/rewriter-go/rewriter-linux | systemctl restart rewriter
前端: /app/static/ | DB: /app/new-api/data/tokenline.db
管理员: https://tokenline.top/admin.html 密码 tokenline2026

## 下次继续

1. 装Firefox（走SSH隧道SOCKS5+代理DNS）→ Meta Developer注册
2. 或找不在国内的人帮忙注册
3. 拿到WhatsApp Token → 设环境变量 → 重启 → OTP上线
