# B11 — T0: nil pointer panic in SchoolDashboard

## Bug 描述

campus_go 的学校管理后台仪表板 `/api/admin/dashboard` 偶尔返回 500 错误并导致服务 panic 重启。日志中有 `runtime error: invalid memory address or nil pointer dereference`。不是每次请求都触发——只在数据库连接池耗尽或网络抖动时出现。

```
curl http://139.196.50.134/api/admin/dashboard → 500 Internal Server Error
```
