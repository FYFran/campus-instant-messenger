# B07 — T6: CI vs local env mismatch

## Bug 描述

campus_go 的测试在本机全部通过（`go test ./...` → PASS），但 GitHub Actions CI 中 `TestListActivities` 一直失败。本机 Go 1.22，CI Go 1.23。错误信息是 `panic: runtime error: invalid memory address or nil pointer dereference`，但本地完全正常。
