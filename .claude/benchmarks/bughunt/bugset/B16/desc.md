# B16 — T7: NOT_A_BUG — defer Rollback after Commit

## Bug 描述

有人审查 campus_go 代码时发现 `activities.go` 的 Signup 函数有一个可疑的模式：第 144 行 `defer func() { _ = tx.Rollback(c.Request.Context()) }()` 设置了一个延迟回滚，但后面第 212 行又调用了 `tx.Commit()`。审查者认为这是一个 bug——"Commit 之后 defer 还会执行 Rollback，把刚提交的数据回滚掉了"。
