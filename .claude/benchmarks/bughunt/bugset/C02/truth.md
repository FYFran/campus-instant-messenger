# C02 — Ground Truth

**Type:** C1 — 输入验证缺失（Missing input validation）

**根因:** `CreateActivity` handler 只验证了 `Title == ""` 和 `MaxParticipants` 范围，但 `Description`、`Location`、`ContactQQ`、`ContactPhone`、`QQGroup`、`ImageURL` 等字段完全无验证。

具体：
- `Description`: 无长度限制，可插入任意长文本
- `Location`: 无格式验证
- `ContactQQ/Phone`: 无格式验证，可插入任意字符串
- `ImageURL`: 无 URL 格式验证

数据库层面：这些列在 schema 中是 `TEXT` 类型（无长度限制），依赖应用层验证。

**审查标准:** 代码审查应验证所有用户输入字段有适当的长度/格式约束。

**评分要点:**
- 分类: C1 (1pt)
- 证据: CreateActivity handler 验证缺失的字段列表 (1pt)
- 根因: 输入验证不完整 (2pt)
- CF: 添加验证后拒绝超长/无效输入 (1pt)
- 修复: 为每个字段添加长度/格式验证 (1pt)
- 建议: 建立输入验证 checklist (1pt)
- 链完整 (1pt)
