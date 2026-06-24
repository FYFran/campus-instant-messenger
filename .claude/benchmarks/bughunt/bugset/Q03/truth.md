# Q03 — Ground Truth

**Type:** Q2 — 阈值绕过（Threshold can be silently lowered）

**根因:** `.codecov.yml` 和 CI 配置中的覆盖率阈值没有保护机制。任何有仓库写权限的人可以直接修改 `codecov.yml` 中的 `threshold` 值，CI 不会检测阈值本身的变更。

具体：`codecov.yml` 中 `target: 50%` 可以被改成 `target: 10%`，CI 照样 PASS，不会告警"阈值被人改过"。

**验证:**
1. 读取 `.codecov.yml` → 记录当前阈值
2. 修改阈值从 50% → 10%
3. 提交并观察 CI → PASS（不告警阈值变更）
4. 没有 git hook 或 CI step 检测 `.codecov.yml` 本身的变更

**评分要点:**
- 分类: Q2 阈值绕过 (1pt)
- 证据: codecov.yml 可任意修改 + CI 不检测配置变更 (1pt)
- 根因: 阈值配置无完整性保护 + 无变更审计 (2pt)
- CF: 加配置完整性检查 → 阈值变更触发告警 (1pt)
- 修复: CI 加 step 检测 .codecov.yml hash 变更 + 需审批 (1pt)
- 防御建议: 所有 CI 配置文件纳入完整性校验 (1pt)
- 链完整 (1pt)
