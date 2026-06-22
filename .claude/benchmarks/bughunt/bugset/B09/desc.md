# B09 — T1: missing await in async

## Bug 描述

Python 后端（main.py）的学生积分更新偶尔不生效。用户完成活动后积分应该立刻增加，但有时刷新页面积分还是旧的。再刷新一次又对了。不是每次都发生。
