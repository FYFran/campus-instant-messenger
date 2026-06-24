# M04 — Ground Truth

**Type:** T1（时序泄露 — 响应时间不一致泄露用户存在性）

**根因:** 登录 handler 中，数据库查询未找到用户时直接返回 401（无 bcrypt），而找到用户时执行 bcrypt.CompareHashAndPassword（~2s）。攻击者通过响应时间差异枚举有效邮箱。

**正确修复:** 用户不存在时也执行一次 dummy bcrypt.CompareHashAndPassword（用固定 hash），使两种路径耗时一致。

**评分要点:**
- 分类: T1 — 同一操作（登录）不同邮箱响应时间不一致 (1pt)
- 证据: 不存在邮箱 <100ms vs 存在邮箱 ~2s (1pt)
- 根因: ErrNoRows 分支跳过 bcrypt → 时序差异泄露用户存在性 (2pt)
- CF: 加 dummy bcrypt → 两种路径等时 (1pt)
- 修复: 不存在用户也跑一次 CompareHashAndPassword (1pt)
