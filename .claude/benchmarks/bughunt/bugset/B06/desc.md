# B06 — T5: state machine stuck

## Bug 描述

campus_go 的活动报名后状态一直停留在 "pending"，不会自动变成 "confirmed"。但审批流程是自动的（不需要人工审核的活动）。学生报名后等了 2 小时状态没变。
