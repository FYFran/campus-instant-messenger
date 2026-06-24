# B22 — Ground Truth

**Type:** T0（稳定复现 — 空数据库必崩溃）

**根因:** `main.py` 的 dashboard stats 端点计算平均志愿时长时，用总时长除以参与活动数：`avg_hours = total_hours / activity_count`。当数据库无活动时，`activity_count = 0`，触发 `ZeroDivisionError`。FastAPI 的异常处理器将其转为 500 响应。

**正确修复:**
```python
avg_hours = total_hours / activity_count if activity_count > 0 else 0
```

**文件:** `campus_app/server/main.py` (dashboard stats endpoint)

**评分要点:**
- 分类: T0 — 空 DB 稳定复现，必崩溃 (1pt)
- 证据: 日志中 ZeroDivisionError + 空 DB 复现 (1pt)
- 根因: main.py dashboard stats — activity_count=0 时未保护除法 (2pt)
- CF: 加 activity_count > 0 检查 → 空 DB 返回 avg_hours=0 (1pt)
- 修复: 三元表达式或 if 保护 (1pt)
