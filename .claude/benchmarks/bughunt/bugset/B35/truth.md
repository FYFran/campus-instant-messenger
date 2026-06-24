# B35 — Ground Truth

**Type:** T7（NOT_A_BUG — 有意的产品设计）

**根因:** `scope_type='all'` 是 campus_go 的产品设计特性，允许校级活动对全校所有学院开放。这不是 bug。

代码中明确有双范围设计：
- `scope_type='college'` + `scope_value='计算机学院'`：仅限特定学院
- `scope_type='all'` + `scope_value='*'`：全校开放

对于 `college_admin`，`scope_type='all'` 的活动属于全校范围，由 `school_admin` 审批，`college_admin` 只有查看权限。`ApproveActivity`/`ModifyActivity` 等操作端点有额外的权限检查（`school_admin` only），所以 `college_admin` 不能操作不属于自己学院的活动。

**为什么不是 bug:**
1. 产品需求明确区分"院级活动"和"校级活动"
2. `scope_type='all'` 的查看权限是有意为之——所有学生都应该能看到校级活动
3. 操作权限（审批/修改）有独立检查，不依赖 scope_type
4. 代码中 `school_admin` only 的检查在 ApproveActivity 等操作端点生效

**评分要点:**
- 分类: T7 — NOT_A_BUG，产品设计特性 (1pt 仅当正确识别为 T7)
- 证据: scope_type 设计文档 + 操作权限独立检查 (1pt)
- 根因: 不存在权限漏洞。查看≠操作，操作端有独立权限控制 (2pt 仅当正确识别非 bug)
- CF: 无需修改 — 当前行为符合产品设计 (1pt)
- 修复: 无需修复 (1pt)
