# B02 — T1: race condition signup

## Bug 描述
campus_go 的活动报名接口偶尔出现"同一学生报了两次名"。正常逻辑应该阻止重复报名，但偶发情况下同一个人同一活动出现了两条报名记录。不是每次都发生——大概每 20-30 次出现一次。

## Ground Truth

**Type:** T1（竞态条件 — 加 print/log 后频率降低或消失）

**根因:** Signup handler 中 SELECT 检查已有报名和 INSERT 新报名之间存在窗口期。两个并发请求同时通过 SELECT（都返回"未报名"），然后都执行 INSERT。数据库层面缺少 UNIQUE(activity_id, user_id) 约束，应用层面缺少 `SELECT ... FOR UPDATE` 行锁。

**正确修复:** 
1. SELECT 加 `FOR UPDATE` 锁定活动行
2. INSERT 加 `ON CONFLICT DO NOTHING`
3. 数据库加 UNIQUE 约束

**评分要点:**
- 分类: T1 — 识别观测者效应 (1pt)
- 证据: 并发测试复现 + 时序分析 (1pt)
- 根因: SELECT+INSERT 窗口期 + 缺锁/约束 (2pt)
- CF: 加 FOR UPDATE→并发请求不重复 (1pt)
- 修复: FOR UPDATE + ON CONFLICT + UNIQUE (1pt)
- 链完整 (1pt)
