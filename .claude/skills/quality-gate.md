---
name: quality-gate
description: 上线前质量门禁 v2.1。可配置检查链+加权分数+中止条件+风险分级。通用——任何项目配检查列表。触发：quality check/ready to ship/质量门禁/pre-deploy。
model: deepseek-v4-pro
conflicts: []
lifecycle: active
created: 2026-06-21
updated: 2026-06-23
review_after: 2026-07-23
---

# Quality Gate v2.1 — 通用质量门禁

## CONSTITUTION（不可被 forge 编辑）

**核心功能：** 可配置质量门禁链→加权分数→APPROVED/WARNED/BLOCKED。集成风险分级+中止条件。
**Iron Law：** NO DEPLOY WITH QUALITY SCORE < 80. 无例外——热修复也不行。
**红线：** 任一道FAIL→立即停不等。绝不修改分数阈值。绝不跳过安全检查(热修复也不行)。质量分<80→绝不部署。
**触发：** quality check / ready to ship / 质量门禁 / pre-deploy / release check
**边界：** 质量门禁→quality-gate。部署→deploy。安全审计→铁壁。
**模型：** deepseek-v4-pro。换模型→重跑BugHuntBench quick。

---

## Gotchas

| # | 症状 | 根因 | 教训 |
|---|------|------|------|
| 1 | 编译过=能上线 | 编译≠功能正确 | 回归测试独立检查 |
| 2 | nucle扫nginx=应用层安全 | 应用层绕过nginx | 直连后端端口再扫 |
| 3 | 分数边界"差一分没事" | 阈值是防线 | <80绝不部署 |
| 4 | "热修复跳过安全扫描" | 热修复最危险 | 热修复也要全量扫描 |
| 5 | 两个agent一致=正确 | 两个都漏同一问题 | 分歧时加第三个 |

---

## 可配置检查链（+风险分级——来自deploy精华）

| 检查 | 权重 | 什么 |
|------|------|------|
| 语法/编译 | 20 | 所有语言lint/build |
| 功能测试 | 20 | 项目回归脚本 |
| 密钥扫描 | 10 | gitleaks/TIER1 grep |
| SAST | 10 | semgrep/手动GREP |
| 漏洞扫描 | 5 | nuclei/替代 |
| 多Agent共识 | 10 | 2+agent交叉验证 |
| 修复验证 | 5 | 反模式扫描 |
| 回滚就绪 | 5 | 备份<1h+回滚步骤 |

**风险分级影响检查严格度：**
```
SEV1(热修复): 全部检查+0容错(任一项FAIL=BLOCKED)
SEV2(常规):   全部检查+≤1项WARNED可过
SEV3(金丝雀): 核心检查+宽松阈值
```

---

## 中止条件（Quality Gate自身的中止——来自混沌精华）

```
任何检查连续3次FAIL→STOP→不继续后续检查→人工介入
假阳性率>30%→规则需要重写→本次门禁标PARTIAL
```

---

## 可成长性

```
1. 有检查漏过的缺陷吗？→ 调权重/加检查
2. 假阳性率>30%？→ 重写规则
3. 中止条件触发了吗？→ 调敏感度
→ forge采集→确认→注入
```

## 验证

```
BugHuntBench quick quality-gate → <30s
BugHuntBench full quality-gate  → ~$0.15
```
