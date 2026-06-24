# B19 — T1: 内存限流器并发竞态

## Bug 描述

campus_go 的登录限流偶尔不准确——有时同 IP 在 12 秒内能连续尝试多次登录。用 `go test -race` 跑测试时偶尔出现 race detector 告警。生产环境偶发，压力测试时更容易触发。
