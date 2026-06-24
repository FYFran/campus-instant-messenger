# B02v2 — Ground Truth

**Type:** T1（竞态条件 — 跨两个 API endpoint 的 SELECT-INSERT 窗口）

**根因:** `activities.go:152` Signup handler 中 SELECT 缺少 `FOR UPDATE`。SELECT 检查已有报名和 INSERT 新报名之间存在窗口期。两个并发请求同时通过 SELECT，然后都执行 INSERT → UNIQUE violation
2. 更微妙的问题：`/api/activities/{id}` 的"已报名"状态通过 `EXISTS(SELECT 1 FROM signups WHERE ...)` 子查询实时计算（快），但 `/api/my-signups` 通过 LEFT JOIN 读取（慢）。在高并发下，INSERT 事务在 EXISTS 子查询和 LEFT JOIN 之间提交 → EXISTS 看到新行（已报名=true），LEFT JOIN 读到旧快照（无此报名）

两个因素共同造成："UNIQUE violation" 错误 + "看到已报名但列表没有" 的状态不一致。

**误导信号:** "UNIQUE constraint violation" 错误提示 → agent 可能认为数据库约束配置有问题，或认为是重复提交的客户端 bug。实际是缺少行级锁 + 事务隔离级别问题。

**正确修复:**
1. Signup handler: SELECT 加 `FOR UPDATE` 锁定活动行
2. INSERT 加 `ON CONFLICT (activity_id, user_id) DO NOTHING`
3. `/api/my-signups` 查询使用 `REPEATABLE READ` 或加事务包裹确保一致性读

**评分要点:**
- 分类: T1 — 跨endpoint竞态 (1pt)
- 证据: 并发测试复现 UNIQUE violation + 状态不一致 (1pt)
- 根因: SELECT-INSERT 窗口 + EXISTS vs LEFT JOIN 事务时序 (2pt)
- CF: FOR UPDATE→无重复 + 一致性读→状态一致 (1pt)
- 修复: FOR UPDATE + ON CONFLICT + 事务隔离 (1pt)
- 链完整 (1pt)

**难度提升点 (vs B02 原版):**
- +1 indirection: 症状分布在两个不同 endpoint
- +1 misleading: "UNIQUE violation" 提示误导为约束配置问题
- 双因素: 不仅是插入重复，还有读取不一致
