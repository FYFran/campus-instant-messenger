# T03 — Ground Truth

**Type:** T4（回归 — 前端更新引入 bug）

**根因:** 前端更新后 `send()` 函数引用了未定义的 `currentLang` 变量拼接请求 payload。每次调用 `send()` → `ReferenceError` → catch 块返回通用错误。该变量在之前的重构中被移除但引用未更新。

**文件:** chat.js, send()

**正确修复:** 将 `currentLang` 替换为 `getCurrentLanguage()` 函数调用。

**评分要点:**
- 分类: T4 — 之前能用，更新后坏了 (1pt)
- 证据: git diff + 所有用户都失败 (1pt)
- 根因: 引用已移除的变量 currentLang (2pt)
- CF: 替换后正常 (1pt)
- 修复: currentLang → getCurrentLanguage() (1pt)
