# B04 — T3: silent data miscalculation

## Bug 描述
campus_go 的学生志愿时长统计页面显示的总时长偶尔比实际签到的时长短。没有报错，没有 crash——就是数字不对。学生反映"明明签到了 10 小时，页面只显示 7 小时"。

## Ground Truth

**Type:** T3（无 crash/error，数据悄悄错）

**根因:** 时长计算中，签到记录的 `duration_minutes` 字段在数据库迁移时从 INT 改为了 FLOAT，但 Python 端仍用 `int()` 强制转换，导致小数部分被截断。每次 1.5 小时的签到被记为 1 小时，累积误差导致总时长偏低。

**正确修复:** `int()` → `round()` 或在求和时使用浮点累加后取整。

**评分要点:**
- 分类: T3 — 无报错数据错 (1pt)
- 证据: 不变量推断 + 数据 diff (1pt)
- 根因: int() 截断 + schema 变更 (2pt)
- CF: 改 round()→统计正确 (1pt)
- 修复: int→round (1pt)
- 链完整 (1pt)
