# S01 — Ground Truth

**Type:** S1（认证缺陷 — 弱 JWT 密钥）

**根因:** `middleware/auth.go:21` 当 JWT_SECRET 环境变量未设置时，代码没有拒绝启动，而是回退到硬编码的弱密钥 `"campus-secret-key-2024"`。攻击者可以暴力破解此密钥并伪造任意用户的 JWT token。

**正确修复:** 移除硬编码回退。JWT_SECRET 未设置时必须报错退出。

**OWASP:** A07:2021 — Identification and Authentication Failures
