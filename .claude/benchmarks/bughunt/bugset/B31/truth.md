# B31 — Ground Truth

**Type:** T3（无报错 — 浮点精度累积误差）

**根因:** Python 的 `float` 类型使用 IEEE 754 双精度（64-bit），在累加多个小数时会产生累积误差。`3.5 + 2.0 + 1.5` 在数学上等于 7.0，但在浮点表示中可能产生 `6.999999999999999`。

具体来说，`main.py` 中学时累加使用 Python 原生 `float`：
```python
total_hours = 0.0
for cert in certificates:
    total_hours += cert['hours']  # float 累加 → 累积误差
```

对于 3-5 个活动的累加，误差在 1e-15 量级。如果活动数量多（50-100 个），误差可能累积到 1e-12。

虽然 JSON 序列化时 `json.dumps(6.999999999999999)` 在某些配置下会输出 `6.999999999999999` 而非 `7.0`，但 Python 的 `json` 模块默认会输出最短表示。Flutter 端的 `double` 类型也有同样精度。

**正确修复:** 
对于货币/学时分，应使用 `Decimal` 或整数（存储为百分之一小时，即分钟）：
```python
from decimal import Decimal
total_hours = Decimal('0')
for cert in certificates:
    total_hours += Decimal(str(cert['hours']))
```
或后端数据库用 `NUMERIC(10,2)` 而非 `float`，Go 端用 `float64` 并 round 到 2 位小数。

**文件:** `campus_app/server/main.py` (my-stats endpoint)

**评分要点:**
- 分类: T3 — 无报错，浮点精度静默偏差 (1pt)
- 证据: 显示 7.000000000000001 而非 7.0 + float 累加定位 (1pt)
- 根因: Python float 累加 → IEEE 754 累积误差 → JSON 输出长小数 (2pt)
- CF: 用 Decimal 或 round → 正确显示 7.0 (1pt)
- 修复: Decimal 替代 float 或 round(x, 2) (1pt)
