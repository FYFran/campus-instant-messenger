# AI 代码审查清单 — 10 点铁律

AI 生成的代码平均含 **1.7倍于人类** 的缺陷，**45%引入OWASP Top 10漏洞**（Veracode 2025）。
审查 AI 代码要比人类代码花更长时间，不是更短。

## 10 点检查清单

| # | 检查项 | 具体验证 |
|---|--------|---------|
| 1 | **需求精确度** | diff 实现了 ticket 的验收标准——不是 AI 的自行脑补 |
| 2 | **真实 API** | 每个 import 的函数/类/模块存在于 lock 文件中的确切版本 |
| 3 | **无 Slopsquatting** | 每个新依赖存在于官方 registry，有真实维护历史，名称完全正确 |
| 4 | **无硬编码密钥** | API keys/tokens/DB密码从环境变量或 secret manager 来 |
| 5 | **输入验证+输出编码** | 所有外部输入验证和清理，所有输出编码到对应 sink |
| 6 | **每个受保护路径 AuthN/AuthZ** | 新 endpoint/handler 强制认证+授权 |
| 7 | **错误处理真存在** | try/catch 不吞错误，失败模式有日志+上下文，用户消息不泄露内部 |
| 8 | **测试覆盖失败路径** | 新代码测试覆盖：null输入/malformed payload/网络失败/并发访问 |
| 9 | **不削弱 CI** | PR 不删除测试、不禁用 linter、不加 eslint-disable |
| 10 | **架构契合** | 新代码遵守模块边界、命名规范、设计模式 |

## 红绿灯分级策略

| 级别 | 允许 AI 做什么 | 审查要求 |
|------|---------------|---------|
| 🟢 **绿** — 低风险 | UI 组件/内部工具/测试脚手架/文档/日志 | 标准 PR 审查 |
| 🟡 **黄** — 标准 | 业务逻辑/数据转换/API 集成/后台任务/数据库查询 | 标准审查 + senior sign-off + SAST + 依赖扫描 |
| 🔴 **红** — 受限 | 认证/授权/加密/支付/数据库迁移/公开API/IaC/PII处理 | **AI 仅起草**，必须人工重写 + senior+security review + 威胁模型 |

## Addy Osmani 的教训

1. **Spec 先于代码** — 写 spec.md，再不编码
2. **小块迭代** — 一次一个函数，不是整个模块
3. **上下文喂饱** — 相关代码+文档+约束全部放进 prompt
4. **人类在环** — AI 输出 = Draft Zero，5分钟审查每1分钟生成
5. **频繁提交** — 每个 task 一个 commit，像游戏存盘点
6. **调教 AI** — CLAUDE.md 里写清楚风格/规则/禁止项

## IVR 框架（Intent-Validation-Refinement）

1. **Intent（人类）** — 提示前写下：要解决什么问题、接受什么架构取舍、3个关键失败模式
2. **Validation（AI/自动化）** — 生成代码后立即通过：人类写的测试、依赖审计、SAST
3. **Refinement（人类）** — 手动审查代码 vs Intent 声明，手动重构变量名、加架构注释

## 参考资料

- Addy Osmani (Google AI Director) — "My LLM Coding Workflow Going into 2026"
- Devin Rosario — "8 AI Code Generation Mistakes Devs Must Fix To Win 2026"
- Metacto — "Code Review for AI-Generated Code: 2026 Standards Guide"
- Veracode 2025 — 45% AI代码含OWASP漏洞
- Cloud Security Alliance — Slopsquatting 攻击（43%幻觉包名每次重现）
