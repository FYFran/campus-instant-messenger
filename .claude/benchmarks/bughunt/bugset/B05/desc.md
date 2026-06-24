# B05 — T4: regression from config change

## Bug 描述

campus_go 的 JWT token 刷新接口 `/api/token/refresh` 昨天还能用，今天突然全部返回 401。代码没改过，但服务器重启过。
