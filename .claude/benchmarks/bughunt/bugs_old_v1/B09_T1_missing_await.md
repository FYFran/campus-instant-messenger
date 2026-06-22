# B09 — T1: missing await in async

## Bug 描述
Python 后端（main.py）的学生积分更新偶尔不生效。用户完成活动后积分应该立刻增加，但有时刷新页面积分还是旧的。再刷新一次又对了。不是每次都发生。

## Ground Truth

**Type:** T1（竞态/时序 — 加 print 后频率降低）

**根因:** `update_user_points()` 是 async 函数，但在 `/api/signup/confirm` handler 中调用时漏了 `await`。函数被创建为 coroutine 但从未执行。在某些时序下（请求处理较慢时），event loop 在返回响应前处理了该 coroutine，积分更新生效；在快速返回时，coroutine 被丢弃，积分未更新。

**正确修复:** 添加 `await update_user_points(user_id, points)`

**评分要点:**
- 分类: T1 (1pt)
- 证据: 复现 + 时序分析 (1pt)
- 根因: 缺少 await → coroutine 未执行 (2pt)
- CF: 加 await→积分每次更新 (1pt)
- 修复: 添加 await (1pt)
- 链完整 (1pt)
