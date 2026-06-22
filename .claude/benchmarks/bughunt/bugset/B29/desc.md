# B29 — T7: NOT_A_BUG — bcrypt cost 值被质疑太低

## Bug 描述

安全审查报告中标记 campus_go 的密码哈希使用了"不安全的 bcrypt cost 值"。报告指出 `auth.go:156` 中 `bcrypt.GenerateFromPassword([]byte(req.Password), bcrypt.DefaultCost)` 的 cost 参数是 `bcrypt.DefaultCost`（值为 10），而 OWASP 2026 年推荐最低 cost 为 12。审查者认为这导致密码哈希容易被暴力破解。
