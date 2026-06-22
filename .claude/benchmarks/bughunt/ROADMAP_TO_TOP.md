# 试剑石 顶级路线图 — 从 70% 到 100%

> 借鉴: SkillAxe (Jun 2026), GEPA ICLR 2026 Oral, Socratic-SWE (Jun 2026), No-No Debug, SWE-bench Top-10
> 核心: 不是加功能。是闭环自进化 + 诚实测量 + 人类校准。

---

## 一、我们现在在哪

```
顶级 ████████████████████ 100%
我们 ██████████░░░░░░░░░░  50%
     │
     ├── 诚实测量 ✅ (88.8% honest, 去掉虚高)
     ├── 单一真相源 ✅ (skill = benchmark prompt)
     ├── GEPA-GATE 设计 ✅ (闭环架构)
     ├── 实验驱动 ✅ ($0.15 A/B → $1.50 验证)
     │
     ├── 闭环未跑通 ❌ (0 次完整 GEPA→验证→合并)
     ├── 人类基线 ❌ (不知道 88.8% 对人类什么水平)
     ├── Judge 未校准 ❌ (LLM 判 LLM, 无人类锚点)
     ├── 单 skill ❌ (只有缉凶, 铁壁/火眼不在榜)
     ├── n=1 基线 ❌ (v2.5.1 诚实基线只跑了 1 次)
     └── 无跨会话记忆 ❌ (每次从头开始)
```

---

## 二、6 篇关键论文 → 6 个具体行动

### 论文 1: SkillAxe (Jun 2026) — 4 维 skill 质量度量

**发现:** 把 skill 质量分解为 4 维: quality impact, trigger precision, instruction compliance, solution-path coverage。自动诊断 + 改进。28% 相对提升, 闭合 47-67% 人类 skill 差距。

**行动: 用 SkillAxe 4 维度度量缉凶, 识别真正薄弱的维度。**
```
现在: "88.8% overall" — 不知道哪个维度弱
顶级: "Trigger precision 100%, Solution coverage 70% → 改进方向明确"
```

### 论文 2: GEPA ICLR 2026 Oral — 遗传进化 > RL

**发现:** GEPA 比 MIPROv2 高 13%, 比 RL 少 35x 训练量。读完整执行 trace, 不是只看分数。Pareto 前沿保留多策略, 不平均成一个。

**行动: 升级 GEPA-GATE 为真正的 GEPA。**
```
现在: 手动触发 → GEPA teacher 分析 → 人工验证
顶级: 自动触发 → GEPA 读 trace → 生成 N 个候选 → Pareto 前沿选优 → 自动验证 → merge
```

### 论文 3: "Nine Judges, Two Effective Votes" (May 2026)

**发现:** 9 个 LLM 法官 ≈ 2 个独立投票。模型犯同样的错。最佳单法官 ≥ 全 panel。多模型不解决偏误。

**行动: 放弃双模 judge。用最佳单 judge + 人类校准。**
```
现在: "deepseek+sonnet 双模取均值" — 浪费钱, 不增加独立性
顶级: "Sonnet 单 judge + 凡哥校准 10 个 case → 校准后评分"
```

### 论文 4: Socratic-SWE (Jun 2026) — 从 trace 蒸馏 skill

**发现:** 闭环自进化: 跑 → 蒸馏历史 trace → 提取结构化 skill → 指导修复 → 再跑。3 轮迭代达 SWE-bench 50.4%。

**行动: 每个 T2 run 的 agent trace 保存 → 蒸馏 → 生成 worked example 候选。**
```
现在: T2 run → 只看分数, trace 丢弃
顶级: T2 run → 保存失败 case 的完整 trace → GEPA 读 trace → 生成改进
```

### 论文 5: No-No Debug — 跨会话错误记忆

**发现:** 实时错误日志 → 每 3 天自动审查 → 规则累积 → 确认门控。29 errors/week → 6/week (79% 减少)。

**行动: 建跨会话错误记忆库。**
```
现在: 每次新会话 = 清零
顶级: .fixes/ 自动索引 → 同模式 3+ 次 → 自动建议 F-rule → T2 验证 → merge
```

### 论文 6: SWE-bench Verified Top-10 (Jun 2026)

**发现:** Opus 4.8 = 88.6% (最高可用模型)。但 DeepSWE 发现 12% cheating + 24% false negative。Pro 榜更难。

**行动: 对标外部基准。**
```
现在: 只有自己的 88.8%, 不知道外部含义
顶级: 缉凶 skill 在 campus_go real bugs 上的 fix rate vs SWE-bench agent 在同类问题上
```

---

## 三、4 Phase 路线图

### Phase 1: 闭环启动 (~$0.60, 今天/明天) [曾预算 $2]

- [ ] T2 R2 + R3 → n=3 诚实基线
  - R2: 全量 10 bugs ($0.50, 进行中)
  - R3: 只跑失败 bugs (≤6/8) via T2 Lean ($0.10-0.20)
- [ ] B05 第二个 ≤5/8 → 触发 GEPA
- [ ] GEPA 分析 B05 失败 trace → 生成候选 F-rule (~$0.05)
- [ ] 候选单独 T2 Lean 验证 (3-run on B05 only, ~$0.15)
- [ ] 通过 → merge → **第一个完整的 GEPA-GATE 循环**

**里程碑: 闭环跑通 1 次。**
**省钱: $0.60 vs 原预算 $2 (70% 节省: 失败 case 重跑用 Lean, 不用全量)**

### Phase 2: 测量升级 (~$2, 本周) [曾预算 $5]

- [ ] 凡哥手动做 5 bugs → 人类基线 (免费)
- [ ] Sonnet judge 评分 vs 凡哥评分 → 校准 judge (免费)
- [ ] SkillAxe 4 维诊断: GEPA 单次分析 (~$0.05)
- [ ] 修复最弱维度 → T2 Lean 验证 ($0.15)

**省钱: $2 vs 原预算 $5 (60% 节省: 人类基线免费, GEPA 一次够, Lean 验证)**

### Phase 3: 多 Skill + 记忆 (~$3, 本月) [曾预算 $10]

- [ ] 铁壁 skill 上 benchmark (改 T2 script, 免费)
- [ ] 跨会话错误记忆库 (code change, 免费)
- [ ] 3 个完整 GEPA-GATE 循环 (3 × $0.20 平均)
- [ ] growth_engine mine 改进 → +5 真实 bugs (免费)

**省钱: $3 vs 原预算 $10 (70% 节省: 脚本复用, mine 免费, Lean 验证)**

### Phase 4: 自主进化 (~$5/月) [曾预算 $20/月]

- [ ] 闭环全自动 (触发 → 分析 → 验证 → merge)
- [ ] 每周 T2 Lean 自动回归检测 ($0.20/周)
- [ ] Benchmark 自动硬化 (退役满分 bugs)

**省钱: $5/月 vs 原预算 $20/月 (75% 节省: Lean 自动化, 低频 T3)**


---

## 四、预算对比 (精打细算 vs 原计划)

| Phase | 原预算 | 精打细算 | 怎么省的 |
|-------|--------|---------|---------|
| P1: 闭环启动 | $2.00 | **$0.60** | R3 只跑失败 case (Lean $0.15 vs 全量 $0.50) |
| P2: 测量升级 | $5.00 | **$2.00** | 人类基线+校准免费, GEPA 一次够 |
| P3: 多 Skill | $10.00 | **$3.00** | 脚本复用, mine 免费, Lean 验证 |
| P4: 自主/月 | $20.00 | **$5.00** | 周检用 Lean, T3 低频 |
| **总计** | **$37** | **~$11** | **70% 节省** |

## 五、度量: 什么叫"到了顶级"

| 维度 | 现在 | 顶级 = |
|------|------|--------|
| **诚实测量** | 88.8% (n=1) | 90%+ (n≥3, ±2pp) |
| **人类参照** | 无 | 人类基线 ± 已知 gap |
| **自进化** | 设计好, 未跑 | ≥3 次自动 merge, 0 次退化 |
| **跨会话** | 清零 | 同模式 3+ → 自动 F-rule |
| **多 skill** | 缉凶 only | +铁壁 +火眼 |
| **Judge** | 单模未校准 | Sonnet + 凡哥校准 10 case |
| **诊断精度** | "总分 88.8%" | "Trigger 100%, Solution 70%" |
| **真实 bug** | 8 mined | 20+ mined + hold-out gap <5pp |
| **成本** | $2.15 spent | $0.50/首跑 T2, $0.15/重跑 Lean, $5/月 |
