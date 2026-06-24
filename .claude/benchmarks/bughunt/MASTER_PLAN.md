# 试剑石 Master Plan — 自成长 Skill 质量系统

> 整合：8轮深度思考 × 6篇2026顶会论文 × 12个盲点 × 5个成长机制
> 目标：不是一次高分。是闭环自进化。

---

## 一、诚实基线

| 指标 | 实数 | 不吹牛逼 |
|------|------|---------|
| 缉凶 v2.5 真实分数 | 95.4±1.9pp (n=3) | 封版基线 |
| 缉凶 v2.6 GEPA | 90% (n=1) | 合同链重排序+F7/F8导致退化，已回滚 |
| 缉凶 v2.5.1 (F6 patch) | **待验证** | v2.5 + F6(T4配置检查) only |
| T-Type | 9.3/10 (v2.5) | B06 注入代码编译错误（非技能问题） |
| 方差 | v2.5 SD=1.9pp | bare SD=4.7pp — 技能降方差 2.5x |
| 祼跑提升 | +5.8pp (89.6→95.4) | Skill lift 显著 |
| 成本 | $5/run, 24min | 竞品 HAL $40K/run |

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

---

## 三、测量纪律

| 规则 | 原因 | 实施 |
|------|------|------|
| 每次优化后跑 Tier 0 | 即时反馈 T-Type | Layer0 scorer |
| 每轮优化后跑 Tier 2 | 全维度验证 | bughunt_t2.js |
| 同版本跑 3 次 | 测量方差 | ±SD |
| hold-out 10 bugs 每次 | 检测过拟合 | B16,B18,B25,B28,B31,B33,B36,B38,M05,T03 |
| 每月跑 Tier 3 | 回归保护 | cross-model + bare baseline |
| Bare 每大版本跑一次 | 已证明 Δ>0 | 省钱 + 够用 |

---

## 四、五环成长引擎

### Ring 1: Bug 矿场
```
git log --diff-filter=M -- campus_go/
→ 提取 commit message 含 "fix/bug/修复" 的 diff 
→ LLM 脱敏 + 泛化 → 人审 30 秒 → 加入 bugset/
```
**KPI:** 每周 +2-5 bugs。3 个月 = 50-70 bugs。

### Ring 2: 难度自升级
```
某 bug 连续 3 次满分 → 退役 → 生成更难变体
```

### Ring 3: 盲区聚类
```
Tier 0 分类失败 → 聚类 → 自动触发 forge 优化
```

### Ring 4: 过拟合检测
```
hold-out vs in-sample gap > 5pp → OVERFIT 告警 → forge 泛化
```

### Ring 5: Trap bugs
```
每周注入 1-2 个 trap bug → agent 瞎猜且 conf>0.9 → CCV 污染告警
```

---

## 五、GEPA 实验结论 (2026-06-22)

**v2.6 GEPA 优化 (合同链重排序 + F6/F7/F8 + T4配置检查 + Q9/Q10) → 退化**

| Version | Score | vs v2.5 | Verdict |
|---------|-------|---------|---------|
| v2.5 | 95.4±1.9pp (n=3) | baseline | 封版 |
| v2.6 GEPA | 90% (n=1) | **-5.4pp** | 退化，回滚 |

**根因分析：** 合同链重排序 ([分类]→[证据] 改为 [初步证据]→[分类]→[深度证据]) 破坏了原有工作流。F7(断言缺失前搜索) 和 F8(跨bug RESET) 可能引入过度约束。

**决策：回滚 v2.5，仅保留 F6 (T4 配置检查)。** v2.5.1 = v2.5 + F6 only。

v2.5.1 改动：
- 决策流新增 Q9: 症状可被配置差异解释 → T4
- F6 致命误判: T4 专属配置检查通过前不许读源码
- T4 强制配置检查 3 步: config diff / port check / startup log

---

## 六、执行记录

| 日期 | 事件 | 结果 |
|------|------|------|
| 2026-06-21 | 试剑石创建 | 10 bugs, T1/T2/T3 脚本 |
| 2026-06-21 | 缉凶 v2.1 优化 | 86.3% |
| 2026-06-22 AM | T1 10-bug 修复 | F1-F9 致命误判, 100% |
| 2026-06-22 AM | T1 35-bug 首跑 | 80% (分类-only 上限) |
| 2026-06-22 AM | T2 首跑 | 95% (n=1) |
| 2026-06-22 PM | T2 方差 + T3 skill lift | v2.5=95.4±1.9%, bare=89.6±4.7% |
| 2026-06-22 PM | v3.0 实验 | 91.7±7.3% — 砍 worked examples 退步 |
| 2026-06-22 PM | **封版** | v2.5=95.4%, 49 bugs, trap+mined 加入 |
| 2026-06-22 PM | v2.6 GEPA R1 | 90% — 退化 -5.4pp |
| 2026-06-22 PM | **回滚→v2.5.1** | v2.5 + F6 only, 待 T2 验证 |

## 七、自动化运维

```
# 每次 skill 改后
just bench-t2          # $0.50, 10min → 验证无退化

# 每天 cron
just bench-t1-full     # $0.03, 1min → T-Type 覆盖 + hold-out gap

# 每周 cron  
just bench-t3          # $5, 25min → skill lift vs bare
growth_engine mine     # 从 git log 挖新 bug
growth_engine check    # 检查 6 trigger

# 触发条件
- hold-out gap > 5pp → OVERFIT 告警 → forge 泛化
- 某 bug 3 次满分 → 退役 → 生成变体
- 同 T-Type c4=0 ×3 → 聚类 → forge 追加 F 规则
```
