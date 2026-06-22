# B17 — Ground Truth

**Type:** T2（多因素 — 环境变量未设置 + 用户传空注册码）

**根因:** `auth.go:164-175` Register 函数中角色提升逻辑存在缺陷：

```go
teacherCode := os.Getenv("REG_TEACHER_CODE")
collegeAdminCode := os.Getenv("REG_COLLEGE_ADMIN_CODE")
superCode := os.Getenv("REG_SUPER_CODE")
switch {
case teacherCode != "" && req.RegCode == teacherCode:
    role = "teacher"
case collegeAdminCode != "" && req.RegCode == collegeAdminCode:
    role = "college_admin"
case superCode != "" && req.RegCode == superCode:
    role = "super"
}
```

问题：当环境变量 `REG_TEACHER_CODE` 未设置时，`teacherCode` 为空字符串 `""`。如果用户也传了空的 `reg_code`（`req.RegCode == ""`），则条件 `teacherCode != ""` 为 false，不会匹配。但如果环境变量被设置为空字符串（某些部署脚本的默认值），则 `teacherCode == ""` 且 `req.RegCode == ""`，**不会**触发角色提升——因为 `!= ""` 为 false。

真正的风险发生在：环境变量被设置为容易猜到的值（如 "123456" 或 "teacher"），而攻击者恰好尝试了这些值。这不是代码逻辑 bug，而是配置安全实践问题。

**但更微妙的实际 bug**: 当三个环境变量全部为空（生产环境典型场景），`req.RegCode` 不论传什么值都不会匹配任何 case，role 保持 "student"。这本身是正确的。但如果某个部署环境错误地将 `REG_TEACHER_CODE` 设为空字符串而非完全不设置，且用户发现可以传空注册码——`teacherCode != ""` 阻止了匹配。所以实际触发条件非常窄。

**更准确的描述**: 如果 `REG_TEACHER_CODE` 被设置为一个空格 `" "`（不是空字符串），则 `teacherCode != ""` 为 true，用户传入 `" "` 即可匹配。这是配置注入的边界情况。

**正确修复:** 
1. 加 `strings.TrimSpace()` 处理环境变量
2. 加最小长度检查：`len(teacherCode) >= 8`
3. 如果所有特权注册码均未配置，拒绝任何非空 reg_code 的提权尝试

**文件:** `campus_go/internal/handlers/auth.go:164-175`

**评分要点:**
- 分类: T2 — 需要环境变量配置异常 + 用户输入匹配两个因素 (1pt)
- 证据: 定位注册码比较逻辑 + 环境变量边界条件分析 (1pt)
- 根因: auth.go:164-175 注册码比较未 TrimSpace + 无最小长度验证 (2pt)
- CF: 加 TrimSpace + 长度检查 → 空格/空注册码无法提权 (1pt)
- 修复: TrimSpace + 最小长度 8 (1pt)
