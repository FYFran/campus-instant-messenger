# B06 — T5: state machine stuck

## Bug 描述
campus_go 的活动报名后状态一直停留在 "pending"，不会自动变成 "confirmed"。但审批流程是自动的（不需要人工审核的活动）。学生报名后等了 2 小时状态没变。

## Ground Truth

**Type:** T5（正常输入→异常输出，状态机卡住）

**根因:** activity 表新增了 `approval_required` 字段，默认值为 NULL。Signup handler 的状态转移逻辑检查 `if activity.ApprovalRequired` 时，NULL 值在 Go 中解析为 false，所以走的是"自动确认"分支。但最近一次 migration 将该字段改为了 `NOT NULL DEFAULT true`，旧的 `if !activity.ApprovalRequired` 逻辑倒置——需要审批的变自动，自动的变需要审批。同时 pending→confirmed 的状态转移在 `approval_required=true` 时缺少审批人指派步骤，导致状态机停在 pending。

**正确修复:** 
1. 统一 `approval_required` 的默认值和 NULL 处理
2. 补全状态转移：`approval_required=true` 且无审批人 → pending；有审批人 → pending_review

**评分要点:**
- 分类: T5 (1pt)
- 证据: 状态转移日志 (1pt)
- 根因: NULL→false + 迁移改默认 (2pt)
- CF: 修正后状态流转正常 (1pt)
- 修复: default + 审批分支 (1pt)
- 链完整 (1pt)
