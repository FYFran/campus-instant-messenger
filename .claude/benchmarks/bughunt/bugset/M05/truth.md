# M05 — Ground Truth

**Type:** T0（稳定复现 — 每次请求必 ReferenceError crash）

**根因:** send 函数中引用了未声明变量 `currentLang` 用于构建请求体。每次调用 send() → ReferenceError → catch 块返回通用错误。变量从未在任何作用域中定义。

**正确修复:** 将 `currentLang` 替换为已存在的 `getCurrentLanguage()` 函数调用。

**评分要点:**
- 分类: T0 — 每次请求必 crash (1pt)
- 证据: 所有用户所有功能均失败 (1pt)
- 根因: 引用未定义变量 ReferenceError (2pt)
- CF: 声明变量 → 错误消失 (1pt)
- 修复: 替换为 getCurrentLanguage() (1pt)
