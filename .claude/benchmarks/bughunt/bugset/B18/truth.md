# B18 — Ground Truth

**Type:** T5（状态机异常 — 非法状态回退）

**根因:** campus_go 的 `ModifyActivity` 和 `ApproveActivity` 端点在接受 PUT/POST 请求时，没有验证目标状态转换的合法性。具体来说：`ApproveActivity` handler 把活动的 `status` 从 `pending_review` 改为 `published`，但如果一个 `ended` 状态的活动被意外重新提交审批（通过直接调用 API），没有任何状态机检查阻止它从 `ended` 变回 `published`。

实际上，`ApproveActivity` handler 只检查了权限（role == school_admin），没有检查当前状态是否允许审批。状态机允许的审批转换只能是 `pending_review → published`，但代码中没有这个约束。

**正确修复:**
```go
var currentStatus string
err := tx.QueryRow(c.Request.Context(),
    "SELECT status FROM activities WHERE id=$1 FOR UPDATE", actID).Scan(&currentStatus)
if currentStatus != "pending_review" {
    c.JSON(400, gin.H{"detail": "只能审批待审核的活动"})
    return
}
```

**文件:** `campus_go/internal/handlers/activities_admin.go` (ApproveActivity handler)

**评分要点:**
- 分类: T5 — 状态机缺少合法转换检查 (1pt)
- 证据: ended 活动 API 调用后变 published + 定位到无状态校验的 ApproveActivity (1pt)
- 根因: ApproveActivity 无当前状态检查，允许 ended→published 非法跳转 (2pt)
- CF: 加状态校验 → ended 活动审批返回 400 (1pt)
- 修复: 审批前检查 currentStatus == "pending_review" (1pt)
