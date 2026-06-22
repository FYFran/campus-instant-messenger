# 试剑石 Bug 库 v2.1

35 个 bug，覆盖 T0-T7 全部类型 × Go/Python/Dart 三语言。

## 目录结构

```
B01/
  desc.md     ← agent 可读（用户视角 bug 描述）
  truth.md    ← 仅评分器可读（根因 + 修复 + 评分要点）
  verify.sh   ← 执行验证脚本（可选）

B02/
  ...
```

## 安全规则

1. **desc.md 公开** — agent 调查时只能读这个文件
2. **truth.md 私有** — 仅评分器（试剑石 Judge）有权读取
3. **verify.sh 私有** — 执行验证时由 sandbox 运行
4. **禁止 agent 读取 bugset/*/truth.md** — 违反 = 污染告警

## Bug 清单

| ID | Type | 语言 | 来源 | 场景 |
|----|------|------|------|------|
| B01 | T0 | Go | 生产 | 空DB→500 (rows.Err缺失) |
| B02 | T1 | Go | 生产 | 并发报名重复 (ON CONFLICT移除) |
| B03 | T2 | Go | 生产 | 学院权限部分匹配 (strings.Contains) |
| B04 | T3 | Python | 生产 | 时长截断 (int vs round) |
| B05 | T4 | Go | 生产 | nginx proxy_pass错端口 |
| B06 | T5 | Go | 注入 | 状态机卡pending (NULL default) |
| B07 | T6 | Mixed | 生产 | Go版本NULL Scan差异 |
| B08 | T7 | Go | 生产 | NOT_A_BUG (产品设计) |
| B09 | T1 | Python | 生产 | missing await (coroutine未执行) |
| B10 | T3 | Go | 注入 | N+1查询 (子查询移除) |
| B11 | T0 | Go | 审计 | rows,_ := db.Query → nil panic |
| B12 | T3 | Go | 审计 | QueryRow.Scan错误丢弃 → 零值 |
| B13 | T4 | Go | 审计 | 登录限流被注释 (回归) |
| B14 | T3 | Go | 审计 | Scan error → continue → 行丢失 |
| B15 | T6 | Go | 审计 | is_read int→bool scan mismatch |
| B16 | T7 | Go | 审查 | NOT_A_BUG (defer Rollback pattern) |
| B17 | T2 | Go | 审计 | 注册码空值+env未设→角色风险 |
| B18 | T5 | Go | 审计 | 活动审批无状态校验 → 非法回退 |
| B19 | T1 | Go | 审计 | 内存限流器并发map竞态 |
| B20 | T6 | Go | 审计 | time.Parse无时区 → 8h偏差 |
| B21 | T3 | Python | 生产 | complete_activity不发证书 |
| B22 | T0 | Python | 构造 | 空DB除零崩溃 |
| B23 | T2 | Go | 构造 | signup_start异常日期 → 报名永不开放 |
| B24 | T4 | Infra | 构造 | nginx proxy_cache污染API响应 |
| B25 | T5 | Mixed | 构造 | 通知已读状态前后端不一致 |
| B26 | T0 | Go | 构造 | JWT中间件nil token→panic |
| B27 | T3 | Python | 构造 | TokenLine扣费先于API调用 |
| B28 | T5 | Python | 构造 | TokenLine订单processing无超时 |
| B29 | T7 | Go | 审查 | NOT_A_BUG (bcrypt.DefaultCost合理) |
| B30 | T1 | Go | 构造 | WebSocket并发写 → 消息丢失 |
| B31 | T3 | Python | 构造 | float累加精度偏差 |
| B32 | T6 | Python | 构造 | asyncio.wait 3.9 vs 3.12 差异 |
| B33 | T0 | Dart | 构造 | Flutter null assertion → 白屏 |
| B34 | T2 | Go | 构造 | N+1子查询 + 缺索引 → 慢查询 |
| B35 | T7 | Go | 审查 | NOT_A_BUG (scope_type=all设计) |

## 类型分布

| Type | 数量 | 说明 |
|------|------|------|
| T0 | 5 | 稳定复现 (B01, B11, B22, B26, B33) |
| T1 | 4 | 间歇/竞态 (B02, B09, B19, B30) |
| T2 | 4 | 多因素 (B03, B17, B23, B34) |
| T3 | 7 | 静默数据 (B04, B10, B12, B14, B21, B27, B31) |
| T4 | 3 | 回归 (B05, B13, B24) |
| T5 | 4 | 状态机 (B06, B18, B25, B28) |
| T6 | 4 | 环境差异 (B07, B15, B20, B32) |
| T7 | 4 | NOT_A_BUG (B08, B16, B29, B35) |

## 语言分布

| 语言 | 数量 |
|------|------|
| Go | 22 |
| Python | 8 |
| Mixed/Infra | 3 |
| Dart | 2 |

## 注入型 Bug

| ID | 注入方式 | 注入目标 |
|----|---------|---------|
| B02 | 行替换 | activities.go (ON CONFLICT 移除) |
| B06 | 行替换 | activities.go (approval_required 逻辑反转) |
| B10 | 行替换 | activities.go (子查询替换为 0) |

其余 32 个 bug 为描述型 — agent 通过阅读代码和日志排查。
