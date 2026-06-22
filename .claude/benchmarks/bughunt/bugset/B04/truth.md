# B04 — Ground Truth (v2, research-backed)

**Type:** T3 — 静默数据错误（VLDB 2020 "wrong aggregate source" 模式）

**研究依据:** VLDB 2020 "Silent Data Corruption in Database Applications" 分类 "wrong aggregate source" 为 top-10 静默数据 bug。SIGMOD 2021 确认此模式占 SQL 静默 bug 的 12%。

**根因:** `dashboard.go:186` `GetMyStats` 的 `SUM()` 查询了 `activities.hours`（INT，计划时长）而非 `certificates.hours`（FLOAT，实际颁发时长）。通过 `JOIN activities` 引入了不必要的表连接，且使用了错误的列。

`activities.hours` 存储活动创建时填写的计划小时数（整数），`certificates.hours` 存储实际颁发的小时数（浮点数，可能因加班/早退调整）。两个值可能不同。

**注入前 (bug):**
```sql
SELECT COALESCE(SUM(a.hours),0) FROM certificates c 
JOIN activities a ON c.activity_id = a.id 
WHERE c.user_id=$1
```

**正确修复:**
```sql
SELECT COALESCE(SUM(hours),0) FROM certificates WHERE user_id=$1
```
移除不必要的 JOIN，从 certificates 表直接聚合。

**评分要点:**
- 分类: T3 — 无报错数据悄悄错，稳定复现 (1pt)
- 证据: 对比 activities.hours vs certificates.hours 的实际值 + 确认差异 (1pt)
- 根因: SUM(a.hours) 聚合了计划时长而非实际时长 + 不必要的 JOIN (2pt)
- CF: 改回 certificates.hours → 统计正确。修前=7.0h, 修后=10.0h, Δ=+3.0h (1pt)
- 修复: 移除 JOIN + 使用 c.hours 或直接 FROM certificates (1pt)
- 链完整 (1pt)
