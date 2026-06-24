# B29 — Ground Truth

**Type:** T7（NOT_A_BUG — bcrypt.DefaultCost=10 在当前硬件上合理）

**根因:** 不是 bug。`bcrypt.DefaultCost = 10` 是 Go 标准库的选择，代表 2^10 = 1024 轮迭代。在 2026 年的典型服务器硬件上，cost=10 的哈希耗时约 100-200ms，cost=12 约 400-800ms。cost 值需要在安全性和用户体验之间平衡。

**为什么不是 bug:**
1. bcrypt 10 仍然远强于 SHA-256 等快速哈希
2. 配合 Argon2id 的支持（auth.go:126-128），新用户默认使用 Argon2id，bcrypt 仅用于兼容旧密码
3. 提高 cost 会导致登录延迟，对移动端用户体验影响显著
4. 没有已知的实际攻击能合理时间内破解 cost=10 的 bcrypt 哈希

**如果要优化:** 可以渐进迁移 — 登录时用 bcrypt 验证后，用 Argon2id 重新哈希并更新数据库。这样在不影响用户体验的情况下逐步淘汰 bcrypt。

**评分要点:**
- 分类: T7 — NOT_A_BUG，成本值在合理范围 (1pt 仅当正确识别为 T7)
- 证据: bcrypt.DefaultCost=10 的行业实践分析 + Argon2id 并存 (1pt)
- 根因: 不存在安全漏洞。10 vs 12 是安全/性能权衡 (2pt 仅当正确识别非 bug)
- CF: 无需修改 — 但可添加渐进迁移策略 (1pt)
- 修复: 无需修复 (1pt)
