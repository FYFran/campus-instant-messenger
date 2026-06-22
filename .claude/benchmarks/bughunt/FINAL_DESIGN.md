# 试剑石 最终设计 — 零人类干预自进化系统

> 借鉴: SkillAxe (Microsoft Jun 2026), GEPA (ICLR 2026 Oral), BenchEvolver (May 2026),
>        Conformal Elo (Jun 2026), Noise-Response Calibration (Mar 2026),
>        "9 Judges = 2 Votes" (Apple May 2026), ArenaBencher (2025)
> 核心: 凡哥不需要碰代码。系统自己进化。

---

## 一、人类基线 — 不需要凡哥 debug

### 三个现成参照系

| 参照系 | 分数 | 来源 |
|--------|------|------|
| **Expert human** | **~95%** | SWE-bench 人类 parity (TDFlow EACL 2026: "human-level at 94.3%") |
| **No-skill AI** | **89.6%** | 我们的 bare agent (no 缉凶 skill) |
| **Original dev fix** | **8/8 per bug** | M01-M08 原始 git fix = GT by definition |

### 凡哥唯一需要做的事 (10min)

**Judge 校准:** 看 3 个 judge 争议 case，说 "高了/低了/公平"。
不需要懂代码。只需要判断: "JWT_SECRET 丢了确实会导致 401，给 0 分太严了"。

---

## 二、Judge 自动校准 — 不需要人类标签

### 2026 研究: 多种自动化校准方法

| 方法 | 人类标签 | 怎么工作 |
|------|---------|---------|
| **Noise-Response** (Mar 2026) | 0 | 加受控噪声 → 测量 judge 敏感度 → 校准 |
| **Conformal Elo** (Jun 2026) | 0 | 概率化 Elo + 共形预测 → 17.9 MAE |
| **PU Learning** (Jun 2026) | 少量正例 | 正-未标记学习 → 纠偏 |

### 我们的实现: 三层校准

```
Layer 1: 自一致检查 (免费)
  同一 report 跑 2 次 Sonnet judge → 分数不同 → 标记 DISPUTE
  分数相同 → 高置信度

Layer 2: Noise-Response (免费)
  对 judge 输入加轻微扰动 (改 bug 描述措辞, 不改含义)
  → 测量 judge 对表面措辞的敏感度
  → 敏感的维度降权

Layer 3: 凡哥 spot-check (10min, 需要时)
  只有 Layer 1+2 都标记 DISPUTE 的 case → 给凡哥看
  预计 <5% 的 case 需要
```

---

## 三、Skill 自进化 — SkillAxe 替代手工 GEPA

### SkillAxe (Microsoft, Jun 2026) 4 维诊断

```
1. Quality impact: skill 对分数的影响有多大?
   → bare vs skill delta = 3pp → 影响存在但不巨大

2. Trigger precision: skill 在正确的时机触发吗?
   → T-Type 10/10 → 100% precision ✅

3. Instruction compliance: agent 遵循 skill 指令吗?
   → Chain 10/10 → 100% compliance ✅

4. Solution-path coverage: skill 覆盖所有必要步骤吗?
   → B03/B05 root_cause 持续 0 → coverage gap ❌
   → 这是我们要修的维度
```

### 自进化循环 (自动化, $0.15/循环)

```
T2/T3 跑 → 保存 per-bug trace + judge 评语
    ↓
SkillAxe 4 维诊断 → 识别最弱维度
    ↓ (当前: solution-path coverage, B03+B05)
GEPA 读失败 trace → 生成候选改进 (只针对弱维度)
    ↓
Lean T2 验证 (3-run, 只测受影响 bugs)
    ↓
mean ≥ baseline? → MERGE
mean < baseline? → DISCARD
    ↓
growth.log 记录: 日期/候选/分数/决定
```

**凡哥角色: 0。全自动。**

---

## 四、Benchmark 自硬化 — BenchEvolver 思路

### 硬化规则 (自动)

```
某 bug 连续 3 次 8/8 → 标记 "饱和"
  → GEPA 生成更难变体 (同 type, 更隐蔽的症状)
  → 新变体入 bugset/, 旧版退役到 archive/
  → 跑一次 T2 验证新变体 (agent 还能 8/8? → 太难, 回退)

某 type 覆盖不足 → 触发 mine
  → growth_engine mine 从 git history 找该 type 的新 bug
  → 入 bugset
```

### 当前饱和 bugs (需要变体)

```
B01 T0: 3/3 全 8/8 → 退役, 生成更难 nil deref 变体
B02 T1: 3/3 全 8/8 → 退役, 生成更难 race 变体
B06 T5: 3/3 全 8/8 → 退役
B08 T7: 3/3 全 8/8 → 退役
B09 T1: 3/3 全 8/8 → 退役
```

---

## 五、完整架构

```
                    ┌──────────────────────────┐
                    │     试剑石 Benchmark       │
                    │  49 bugs, 自动硬化         │
                    └──────────┬───────────────┘
                               │
            ┌──────────────────┼──────────────────┐
            ▼                  ▼                  ▼
     ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
     │  T2 Full     │   │  T2 Lean    │   │  T3 Lean    │
     │  10 bugs     │   │  N bugs     │   │  trace保存   │
     │  $0.50       │   │  $0.05/bug  │   │  $0.50      │
     └──────┬───────┘   └──────┬──────┘   └──────┬──────┘
            │                  │                  │
            └──────────────────┼──────────────────┘
                               │
                    ┌──────────▼───────────┐
                    │   Judge (Sonnet x1)   │
                    │   3-layer auto-cal    │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │   SkillAxe 4-dim      │
                    │   诊断 → 生成候选     │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │   GEPA Validate      │
                    │   Lean T2 ×3         │
                    │   MERGE / DISCARD    │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │   缉凶 Skill          │
                    │   自动进化            │
                    └──────────────────────┘
```

---

## 六、凡哥的 3 个角色 (全加起来 <30min)

| 角色 | 频率 | 时间 |
|------|------|------|
| **Judge 校准** | 首次 + 每月 | 10min (3-5 disputed case) |
| **战略决策** | 需要时 | 5min ("推铁壁还是推火眼?") |
| **Mine 审查** | 每周 | 10min (审 3-5 新 bug 候选) |

**不做的: debug 代码, 改 skill, 跑 benchmark, 写 F-rule。**

---

## 七、预算: $5/月 全自动运行

| 项目 | 频率 | 月成本 |
|------|------|--------|
| T2 Full (基线检测) | 每周 1 次 | $2.00 |
| T2 Lean (候选验证) | 每月 ~5 次 | $1.00 |
| T3 Lean (成长追踪) | 每月 1 次 | $0.50 |
| GEPA 分析 | 每月 ~3 次 | $0.15 |
| Mine (bug 挖矿) | 每周 1 次 | $0 |
| Benchmark 硬化 | 每月 ~3 bugs | $0.50 |
| **总计** | | **~$4.15** |

---

## 八、当前状态 vs 最终设计

| | 现在 | 最终 |
|---|------|------|
| 人类基线 | ❌ | SWE-bench proxy ~95% |
| Judge 校准 | ❌ | 3-layer auto (noise-response + self-consistency + 凡哥 spot) |
| 成长闭环 | 设计好, 未跑 | SkillAxe 4-dim → GEPA → auto merge |
| Benchmark | 静态 49 bugs | 自动硬化 (饱和→变体) |
| 多 skill | 缉凶 only | 铁壁 + 火眼 |
| 成本 | $2.75 spent | $4.15/月 |
| 凡哥时间 | 0 | <30min/月 |
