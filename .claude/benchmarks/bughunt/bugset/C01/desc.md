# C01 — C0: Swallowed Error (bare except / _ = err)

## Bug 描述

campus_go 代码库中存在多处错误被静默忽略的情况。审查代码找出至少一个位置，其中错误被完全忽略（不是返回、不是记录日志），而是被 `_` 或 bare except 吞噬。

目标：找到代码审查应该拦截但未拦截的静默错误处理缺陷。
