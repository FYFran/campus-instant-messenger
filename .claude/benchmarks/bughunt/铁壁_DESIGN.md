# 铁壁 Benchmark — Security Audit Skill 评估

> 复用试剑石全部基础设施。不同 bug 类型，同评分框架。

## 研究依据

- OWASP Top 10 (2021): 标准漏洞分类
- "Do LLMs Match Beginner Skill in Vulnerability Detection?" (arXiv 2025): LLM 安全审计能力基准
- SWE-bench curation pipeline: 同策展流程

## 评分维度（7 维，对标缉凶）

| # | 维度 | 0 | 1 | 2 |
|----|------|---|---|---|
| 1 | 分类 | 错误/漏报 | S-Type 正确 | — |
| 2 | 证据 | 无复现 | 有 PoC/复现步骤 | — |
| 3 | 溯源 | 无调用链 | 完整数据流追踪 | — |
| 4 | 根因 | 错误 | 方向对 | 精确 file:line + 机制 |
| 5 | 严重性 | 评级离谱 | CVSS 合理 | CVSS + 业务影响 |
| 6 | 修复 | 错误/引入新洞 | 正确修复 | 修复 + 防御分层 |
| 7 | 链完整 | 缺步 | 7 步全走 | — |

满分: 8（分类1+证据1+溯源1+根因2+严重性1+修复1+链完整1）

## Bug 类型（S0-S5，对标缉凶 T0-T7）

| Type | 名称 | 症状 | 第一步 | 常见误判 |
|------|------|------|--------|---------|
| **S0** | 注入类 | XSS/SQLi/命令注入 | 输入追踪 | 误判为配置问题 |
| **S1** | 认证缺陷 | JWT/Session/密码 | 凭证流追踪 | 误判为设计选择 |
| **S2** | 数据暴露 | IDOR/信息泄露 | 权限矩阵检查 | 误判为功能需求 |
| **S3** | 配置缺陷 | CORS/CSP/Headers | 响应头检查 | 误判为S0 |
| **S4** | 依赖风险 | CVE/供应链 | 依赖扫描 | 不验证利用条件 |
| **S5** | 逻辑漏洞 | Race/Bypass | 状态机分析 | 误判为不存在的威胁 |

## 初始 Bug 规划（10 bugs，$0 设计）

| ID | Type | 描述 | campus_go 对应 |
|----|------|------|---------------|
| S01 | S0 | 活动描述未转义 → 存储 XSS | CreateActivity 描述字段 |
| S02 | S1 | JWT secret 弱密钥 | auth.go JWT_SECRET |
| S03 | S1 | 密码无复杂度校验 | auth.go Register |
| S04 | S2 | 用户 ID 可枚举 → IDOR | GetUser 无权限检查 |
| S05 | S2 | 报名列表泄露其他用户信息 | GetSignups 返回过多字段 |
| S06 | S3 | CORS 配置过于宽松 | CORS middleware |
| S07 | S3 | CSP 头缺失 | 响应头缺少 Content-Security-Policy |
| S08 | S4 | 依赖 go-jwt 有已知 CVE | go.mod 依赖版本 |
| S09 | S5 | 报名审批绕过竞态 | ApproveSignup 无事务 |
| S10 | S5 | 活动编辑无版本控制 → 覆盖 | UpdateActivity 缺少乐观锁 |

## 与缉凶的复用

```
同: 评分框架 (7维→8分), Judge (Sonnet), Bootstrap CI, 成长编排器
异: Bug 类型 (S0-S5 vs T0-T7), 维度定义 (严重性 vs CF)
全复用: results.tsv, per_bug_results.tsv, judge_calibrate.py, bootstrap_ci.py
```

## 策展标准

每个 S-bug 必须: desc.md + truth.md + inject.patch + verify.sh (同缉凶标准)
验证: `git apply inject.patch` → 安全工具扫描应检出 → `git apply fix.patch` → 修复确认
