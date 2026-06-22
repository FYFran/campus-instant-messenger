# 试剑石 Master Plan — 自成长 Skill 质量系统

> 整合：8轮深度思考 × 6篇2026顶会论文 × 12个盲点 × 5个成长机制
> 目标：不是一次高分。是闭环自进化。

---

## 一、诚实基线

| 指标 | 实数 | 不吹牛逼 |
|------|------|---------|
| 缉凶 v2.5 真实分数 | ~91-92% | v2.4 96.3% 含 judge fallback 虚高 |
| T-Type | 9/10 | B06 失败——注入代码编译错误（非技能问题，测量噪音） |
| 方差 | **未知** | 同版本未跑过两次 |
| 过拟合 | **未知** | B11-B35 从未跑过 |
| 祼跑提升 | +8.8pp (77.5→86.3) | 裸 agent 同期提升→部分来自测试环境变松 |
| 成本 | $5/run, 24min | 竞品 HAL $40K/run — 我们 $5 已经很省 |

---

## 二、四层管线（成本架构）

```
Tier 0 ($0, <1s)         Tier 1 ($0.05, <1min)    Tier 2 ($0.5, ~5min)     Tier 3 ($5, ~25min)
┌──────────────┐      ┌──────────────────┐      ┌──────────────────┐      ┌──────────────────┐
│ 纯规则         │  →   │ 分类-only        │  →   │ 全调查+batch judge│  →   │ 全调查+cross-model│
│ c1+c2+c6+c7  │      │ 1 agent, $0.01   │      │ 10+1 agent       │      │ +bare +独立judge  │
│ 4/8 分 $0    │      │ 只验证T-Type     │      │ 完整7维评分       │      │ 发布/周检用       │
│ 每次save跑   │      │ 每次skill改跑     │      │ 每轮优化后跑       │      │ 验证不退化        │
└──────────────┘      └──────────────────┘      └──────────────────┘      └──────────────────┘
```

**3轮优化成本：$15 → $0.60（节省96%）**

---

## 三、测量纪律

| 规则 | 原因 | 实施 |
|------|------|------|
| 每次优化后跑 Tier 0 | 即时反馈 T-Type | Layer0 scorer |
| 每轮优化后跑 Tier 2 | 全维度验证 | 新 bughunt_t2.js |
| 同版本跑两次 | 测量方差 | ±X pp |
| hold-out 5 bugs 每次 | 检测过拟合 | B26-B30 固定 hold-out |
| 每月跑 Tier 3 | 回归保护 | cross-model + bare baseline |
| Bare 每大版本跑一次 | 已证明 Δ>0 | 省钱 + 够用 |

---

## 四、五环成长引擎

### Ring 1: Bug 矿场（自动挖矿）

```
git log --diff-filter=M -- campus_go/ 
→ 提取 commit message 含 "fix/bug/修复" 的 diff 
→ LLM 脱敏 + 泛化 
→ 人审 30 秒（desc.md + truth.md）
→ 加入 bugset/
→ 试剑石自动变难
```

**KPI:** 每周 +2-5 bugs。3 个月 = 50-70 bugs。

### Ring 2: 难度自升级

```
某 bug 连续 3 次 8/8 → 退役（不删除，不参与 Tier 1-2）
→ 生成更难变体（+1 层间接引用 / +1 个误导信号）
→ 新 bug 加入
```

### Ring 3: 盲区聚类

```
Tier 0 分类失败 → 聚类（T1→T3 ×3次, T2→T3 ×2次）
→ 自动触发 forge 优化对应维度
→ commit → Tier 0 → 验证改善
```

### Ring 4: 过拟合检测

```
每月跑 hold-out B26-B35（10 bugs）
→ 对比 in-sample vs hold-out 分数
→ hold-out 低于 in-sample >5pp → OVERFIT 告警
→ 强制回 forge 泛化优化
```

### Ring 5: Trap bugs（防瞎猜）

```
每周注入 1-2 个 trap bug（看起来像 X 但不是 bug / 根因完全另一边）
→ agent 判 NOT_A_BUG 或正确根因 → OK
→ agent 瞎猜且 conf>0.9 → CCV 污染告警
→ 触发 human review
```

---

## 五、立即执行（今天）

### Step 1: 修 B06 注入
`bug_injection.py` B06 注入未编译代码 → 测量噪音。改为注入逻辑错误（不涉及编译）。

### Step 2: 同步工作流 prompt 
`bughunt_final.js` buildPrompt 内联分类文本同步到 v2.5。

### Step 3: 选 hold-out 集
B26-B30 (5 bugs) 固定为 hold-out。其余 30 bugs 为 in-sample。

### Step 4: 测量方差
缉凶 v2.5 × Tier 1 × 2 次 → 得到 ±误差。

### Step 5: 跑 growth_engine mine
从 git history 自动挖 5-10 新 bug → 人审 → 加入题库。

---

## 六、本周完成

- Tier 0/1/2 三个 workflow 化
- 10 个 hold-out bugs (B26-B35) 首次跑分
- 方差正式报告
- growth_engine 首次挖矿结果
- 第一个盲区 → forge 自动优化 → 验证闭环

---

## 七、"顶级"的定义（不是一次分数）

| 维度 | 现在 | 顶级 = |
|------|------|--------|
| **自进化** | 手动改 skill | commit → 自动优化 → 自动验证 → 自动升级 |
| **抗过拟合** | 未知 | hold-out vs in-sample <3pp |
| **可测量** | 无方差数据 | 每指标有 ±CI |
| **经济** | $5/run | $0.5/run (Tier 2), $0/run (Tier 0-1) |
| **持续变难** | 静止题库 | 每周 +2-5 bugs, 退役满分 bugs |
| **防作弊** | 答案物理分离 | +trap bugs + CCV 跨会话检测 |
| **跨项目** | 仅 campus_go | +tokenline + generic-go |
| **多技能** | 仅 缉凶 | +铁壁 + 火眼 排行榜 |

---

## 八、不做什么（故意放弃）

| 放弃 | 原因 |
|------|------|
| 3-judge consensus 全量跑 | Kohli 2026: 9 judge = 2 票。1 个好 judge 够 |
| 每次跑 bare agent | Δ>0 已证明。省 50% 成本 |
| T-Type 追 100% | 症状重叠不可消除。95% 够 |
| 人工标注金标集 | 成本 >$1000，当前规模不需要 |
| 跨模型 judge 每次跑 | Sonnet 3x 成本。Tier 3 每月 1 次够 |
