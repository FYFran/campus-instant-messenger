# B22 — T0: Python 后端空数据库除零崩溃

## Bug 描述

Python 后端（campus_app）的仪表板统计 API `/api/dashboard/stats` 在数据库没有任何活动记录时返回 500 错误。日志显示 `ZeroDivisionError: division by zero`。数据库有活动时一切正常。
