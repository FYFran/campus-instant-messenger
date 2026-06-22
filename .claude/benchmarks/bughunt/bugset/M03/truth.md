# M03 — Ground Truth

**Type:** T3（静默数据错 — 限流 key 错配，保护永不触发）

**根因:** checkCooldown(phone) 用 phone 作为 map key 查找，但调用方传入的 key 是 `'otp_' + userID` 格式。key 格式不匹配 → map 永远 miss → checkCooldown 返回 false → 限流 block 永远不执行。

**正确修复:** 统一 key 格式——直接用 userID 调用限流函数，不经过 cooldown wrapper。

**评分要点:**
- 分类: T3 — 无报错，保护静默失效 (1pt)
- 证据: 连续失败无拦截 + map key 对比 (1pt)
- 根因: 调用方传入 'otp_{userID}' 但 map key 是 phone → 永久 miss (2pt)
- CF: 修正后失败次数超限即拦截 (1pt)
- 修复: 统一 key 格式 (1pt)
