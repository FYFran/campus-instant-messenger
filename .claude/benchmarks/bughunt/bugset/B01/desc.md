# B01 — T0: nil deref after DB query

## Bug 描述

campus_go 的活动列表 API `/api/activities` 在数据库为空时返回 500 错误。有活动时正常。
```
curl http://139.196.50.134/api/activities → 500 Internal Server Error
```
