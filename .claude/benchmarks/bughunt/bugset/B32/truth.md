# B32 — Ground Truth

**Type:** T6（环境不匹配 — Python 版本差异）

**根因:** Python 3.9 和 3.12 之间 `asyncio.wait` 的默认行为有细微差异。在 Python 3.11+ 中，`asyncio.wait` 的默认 `return_when` 参数行为有小幅调整——当协程列表中有 coroutine 对象（而非 Task 对象）时，3.9 的处理方式与 3.11+ 不同。

具体来说：如果代码使用 `asyncio.wait(coroutines)` 而非 `asyncio.wait(tasks)`，Python 3.9 中未包装的 coroutine 在某些条件下不会被正确调度。而在 Python 3.12 中这些 coroutine 被自动包装为 Task。

另一种可能：`asyncio.gather` vs `asyncio.wait` 的错误处理差异。`asyncio.gather` 在 Python 3.9 中某个 task 抛异常时默认会取消其他 task（return_exceptions=False），而 Python 3.11+ 调整了取消传播行为。

**正确修复:**
```python
# 兼容所有版本的写法
tasks = [asyncio.create_task(send_notification(n)) for n in notifications]
results = await asyncio.gather(*tasks, return_exceptions=True)
```

使用 `asyncio.create_task` 显式包装 + `asyncio.gather(return_exceptions=True)` 确保所有通知都被发送，单个失败不影响其他。

**文件:** `campus_app/server/main.py` (batch notification handler)

**评分要点:**
- 分类: T6 — 不同 Python 版本行为差异 (1pt)
- 证据: 3.12 正常 3.9 不正常 + asyncio.wait 行为差异文档 (1pt)
- 根因: asyncio.wait coroutine vs Task 的版本差异 → 部分协程未被调度 (2pt)
- CF: 改用 asyncio.create_task + gather → 3.9 和 3.12 都正常 (1pt)
- 修复: create_task + gather(return_exceptions=True) (1pt)
