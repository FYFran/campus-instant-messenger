# 试剑石 Bug 库 v3.0

多skill bug set。35个缉凶bug + 铁壁/code-review/deploy/quality-gate/red-team bug set。

## 目录结构

```
{skill}/B01/
  desc.md     ← agent 可读(盲测)
  truth.md    ← 仅评分器可读(根因+修复+评分要点)
```

## Bug设计原则

1. 真实 — 模拟真实世界错误模式
2. 盲测 — agent只看到desc.md
3. 可验证 — 有可重现测试
4. 人审 — 对标SWE-bench 3人审核制

## 各Skill Bug类型

| Skill | 分类 | 示例 |
|-------|------|------|
| 缉凶 | T0-T7 | nil deref, race, multi-factor, config |
| 铁壁 | S0-S5 | hardcoded secret, SQLi, missing auth, CVE |
| code-review | C0-C4 | auth gap, race condition, XSS, error handling |
| deploy | D0-D4 | missing backup, config drift, rollback fail |
| quality-gate | Q0-Q3 | false pass, check skip, threshold bypass |
| red-team | R0-R3 | bypass auth, chain LOW→HIGH, replay |

## 当前进度

| Skill | Bug数 | 状态 |
|-------|-------|------|
| 缉凶 | 38(B)+7(M) | ✅ |
| 铁壁 | 待建 | ⚠️ |
| code-review | 待建 | ⚠️ |
| deploy | 待建 | ⚠️ |
| quality-gate | 待建 | ⚠️ |
| red-team | 待建 | ⚠️ |
