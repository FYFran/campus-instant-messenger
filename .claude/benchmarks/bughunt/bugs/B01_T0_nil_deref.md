# B01 — T0: nil deref after DB query

## Bug 描述
campus_go 的活动列表 API `/api/activities` 在数据库为空时返回 500 错误。有活动时正常。
```
curl http://139.196.50.134/api/activities → 500 Internal Server Error
```

## Ground Truth

**Type:** T0（稳定复现 — 空数据库必 500）

**根因:** `activities.go` ListActivities 函数在 `db.Query()` 返回 rows 后直接访问 `rows` 的属性或使用 `rows.Scan()` 的结果，未检查 `rows.Err()` 或 nil 情况。当数据库返回空结果时，某些驱动版本的 `rows` 行为导致后续操作 panic。

**正确修复:** 在 `for rows.Next()` 循环后添加 `if err := rows.Err(); err != nil { return err }`

**评分要点:**
- 分类: T0 (1pt)
- 证据: 空 DB 复现 + campus_check baseline (1pt)
- 根因: rows.Err() 缺失 + 具体 file:line (2pt)
- CF: 加检查→空DB返回200 (1pt)
- 修复: 添加 rows.Err() 检查 (1pt)
- 链完整: 7 步产出 (1pt)
