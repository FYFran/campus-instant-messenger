# C01 — Ground Truth

**Type:** C0 — 错误吞噬（Swallowed error without handling）

**根因:** campus_go 多处使用 `_, _ = db.Exec(...)` 忽略错误。具体位置：
- `activities_admin.go:157-159`: `_, _ = db.Exec(c.Request.Context(), "INSERT INTO notifications...")` — 通知插入失败静默忽略
- `activities_admin.go:207-209`: 同上 pattern，驳回通知
- `publish_requests.go:333-355`: 多处 `db.Exec` 无错误检查
- `lottery.go:42`: `db.QueryRow(...).Scan(&userCollege)` 无错误检查

Python backend:
- `main_remote.py` 多处 bare `except:` 吞噬所有异常

**审查标准:** 代码审查应标记所有 `_ = err` / bare except 并要求至少 log 错误。

**评分要点:**
- 分类: C0 (1pt)
- 证据: 具体 file:line + 吞噬的错误类型 (1pt)
- 根因: 缺少错误处理规范 + review 未拦截 (2pt)
- CF: 对比有错误处理的代码 (1pt)
- 修复: 至少 log.Printf 错误，关键路径 return err (1pt)
- 建议: lint rule 禁止 bare except / _ = error (1pt)
- 链完整 (1pt)
