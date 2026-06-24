# B21 — Ground Truth

**Type:** T3（无报错 — 功能缺失导致数据不一致）

**根因:** `main.py:1062-1077` 的 `complete_activity` 端点只做了两件事：(1) 更新活动状态为 `'completed'`，(2) 发送"学时已发放"通知。但它**从未向 certificates 表插入任何记录**。

学时统计 `GET /api/my-stats` 通过 `SELECT COALESCE(SUM(c.hours),0) FROM certificates c WHERE c.user_id=$1` 计算——只从 certificates 表聚合。没有 INSERT 就没有学时。

管理员后续点击"生成证书"按钮会调用另一个端点 `generate_certificates`，它才真正插入证书——这就解释了"有时正常有时不正常"。

**正确修复:** 在 `complete_activity` 中添加证书生成循环：
```python
for signup in signups:
    hours = staff_hours if signup['role'] == 'staff' else participant_hours
    cert_number = f"CERT-{datetime.now().strftime('%Y%m%d')}-{signup['user_id']}"
    await db.execute(
        "INSERT INTO certificates (...) VALUES (...) ON CONFLICT DO NOTHING")
    await db.execute(
        "UPDATE users SET volunteer_hours = (SELECT COALESCE(SUM(hours),0) FROM certificates WHERE user_id=$1) WHERE id=$1",
        signup['user_id'])
```

**文件:** `campus_app/server/main.py:1062-1077`

**评分要点:**
- 分类: T3 — 无报错，HTTP 200 但数据未更新 (1pt)
- 证据: 完成活动后 certificates 表无新记录 + 定位到 complete_activity 无 INSERT (1pt)
- 根因: main.py:1062-1077 — complete_activity 只改状态不发证书 (2pt)
- CF: 添加证书 INSERT → 完成活动后学时正确增加 (1pt)
- 修复: 在 complete_activity 中添加证书生成 (1pt)
