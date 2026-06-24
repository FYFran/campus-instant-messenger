# S02 — Ground Truth

**Type:** S0（注入类 — 存储型 XSS）

**根因:** `activities_admin.go:94` CreateActivity 将用户输入的 description 字段直接 INSERT 到数据库，未经过任何 HTML 清洗。前端渲染时若使用 `innerHTML` 或 `dangerouslySetInnerHTML`，恶意脚本即可执行。

**正确修复:** 后端在存储前用 `html.EscapeString()` 清洗 description，或使用 `bluemonday` 等 HTML sanitizer 库。

**OWASP:** A03:2021 — Injection
