# B38 — TRAP: T0→T5

## Bug 描述

campus_go 服务首次启动后第一个请求必 panic nil pointer dereference，之后所有请求正常。重启服务后又会出现第一次 panic。每次重启稳定复现——第一次请求必挂，后面的都好。
