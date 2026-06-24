# G02 Truth

## 分类
G1 - API不一致

## 位置
- Go: campus_go/internal/handlers/*.go (gin.H{"detail": ...})
- Python: campus_app/server/main*.py ({"error": ...} / {"detail": ...})

## 根因
双后端开发时没有定义统一的API错误响应格式。前端需要处理两种不同的错误格式。

## 修复
1. 定义统一错误格式：`{"error": {"code": "...", "message": "...", "details": []}}`
2. 两个后端统一使用
3. 写入API规范文档

## 评分要点
- [ ] Probe是否扫描了两个后端的错误响应格式？
- [ ] 是否标记为P1(架构不一致)？
- [ ] 修复建议是否包含具体统一格式？
