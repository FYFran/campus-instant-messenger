# M07 — Ground Truth

**Type:** T1（竞态 — 支付回调 TOCTOU 导致双发）

**根因:** 支付 webhook handler 先 SELECT 检查 payment 状态（是否已处理），然后 UPDATE 标记为已支付。支付网关偶发重复回调（网络重试）→ 两个并发回调同时 SELECT 看到 pending → 都通过检查 → 都执行 UPDATE + 发放 token。

**正确修复:** 用原子 CAS 操作：`UPDATE payments SET status='paid' WHERE id=? AND status='pending'`。RowsAffected=1 的获胜，RowsAffected=0 的走幂等返回。

**评分要点:**
- 分类: T1 — 支付回调并发竞态，偶尔双发 (1pt)
- 证据: 同 invoice ID 两次处理日志 (1pt)
- 根因: SELECT check + UPDATE 分离 → TOCTOU 窗口 (2pt)
- CF: CAS UPDATE → 只有一个 callback 成功修改 (1pt)
- 修复: WHERE status='pending' 原子条件更新 (1pt)
