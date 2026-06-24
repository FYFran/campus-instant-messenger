---
name: session-2026-06-19-20-tokenline-audit
description: 6月19-20日TokenLine 22项安全审计+前端全测+最低利润定价+CI流水线v2.0
metadata:
  type: project
---

# TokenLine 6/19-20 安全审计+全站升级

## 安全审计 (22项)

### 致命5
- C1: IPv6 localhost `[::1]:port` 解析错误 → 重写IP strip逻辑
- C2: 登录锁定并发绕过 → 原子 `checkAndRecordFailedLogin` (BEGIN+INSERT+SELECT+COMMIT)
- C3: `reqBody, _ := json.Marshal(...)` 错误被吞 → 改为 `reqBody, err :=` + return
- C4: Sentry DSN硬编码 → `os.Getenv("SENTRY_DSN")` + fallback
- C5: Admin兑换码无上限 → 日限200码 + remaining透传

### 高危5
- H1: Unicode同形字绕过 → NFKC归一化 (`golang.org/x/text/unicode/norm`)
- H2: DeepSeek key复用 → `DEEPSEEK_ADMIN_KEY` 环境变量
- H3: X-Real-IP伪造 → 仅信任localhost来源的X-Real-IP
- H4: OTP裸SHA-256 → HMAC-SHA256 + JWTSecret pepper
- H5: Rate limit key带端口 → 剥离端口号

### 中危6 + 低危6
- M1: ThesisOutline免费烧钱 → 每IP日10次限
- M2: WriteTimeout 180s→600s
- M3: 推荐码枚举 → 仅接受email格式ref
- M4: ThesisOutline field长度 → 300→500
- M5: 升级错误被吞 → slog.Error + 降级
- M6: Content-Type校验 → requireJSON中间件
- L1: 密码去空格 → Register+Login+ChangePassword
- L2: 手机号脱敏 → maskPhone()
- L3: /api/health限流 → RateLimit middleware
- L4: SMS回调无签名 → HMAC token验证
- L5: DODO panic → 降级mock模式
- L6: JWT密钥轮换 → JWT_SECRET_PREVIOUS env

## 最低利润定价
- **策略**: 价格不动(Dodo锁死)，Token量翻2-15倍 → 利润率~25%
- ID: Flash 4/10/20M, 实惠 30/80/200M, Pro 28/100/240M
- 回本: 月固定Rp 103K，卖3包/月回本

## CI流水线v2.0
- 独立阶段，FAST模式，多轮支持
- Bug: stage_preflight用全局FAIL判本轮 → 改用local this_run_fail

## 实战测试14项
- 注册/登录/Chat SSE/Packs/Templates/Outline/Citation/支付/统计/余额/弱密码/锁定
- 全部通过

**Why:** 首次全量安全审计+定价优化+流水线升级
**How to apply:** 每次改Go代码后跑 `FAST=1 bash ci-pipeline.sh`，定价变更先确认Dodo后台
