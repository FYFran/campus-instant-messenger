# B13 — Ground Truth

**Type:** T4（回归 — 之前工作正常，现在失效）

**根因:** `auth.go:69-78` Login 函数中的频率限制代码被整块注释掉了，注释标记为 `DISABLED FOR TESTING - RESTORE AFTER`。代码注释显示是在某次测试时被禁用，但从未恢复。注释掉的代码包括：loginRateMu 锁、12 秒冷却检查、IP 记录更新。函数顶部的 `loginRateLimit` map 和 `loginRateMu` mutex 仍然声明但不再使用。

**正确修复:** 取消注释频率限制代码块（auth.go:70-78），恢复登录频率限制功能。

**文件:** `campus_go/internal/handlers/auth.go:69-78`

**评分要点:**
- 分类: T4 — 之前有防护→现在无防护，典型回归 (1pt)
- 证据: 连续 100 次错误密码全部 401 + 定位到注释掉的代码 (1pt)
- 根因: auth.go:70-78 频率限制被注释 "DISABLED FOR TESTING"，未恢复 (2pt)
- CF: 取消注释 → 同 IP 12 秒内第二次登录返回 429 (1pt)
- 修复: 恢复注释掉的 rate limit 代码 (1pt)
