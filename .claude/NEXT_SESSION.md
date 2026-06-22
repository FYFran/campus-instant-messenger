# 新对话指令

你是皮特。读 `f:\ClaudeFiles\.claude\CLAUDE.md`。

## ⚠ 先读这个

**上轮发现当前方法有4个致命缺陷。写了修正计划：[CORRECTED_PLAN.md](.claude/benchmarks/bughunt/CORRECTED_PLAN.md)**

**核心结论：注入bug≠真实bug。线性的[分类]→[追踪]≠人类的螺旋假设→验证。**

**下一步不是继续v2.5.1验证。是先做Phase 0(人类基线) + Phase 1(真实bug+螺旋模型)。**

---

## 当前任务：CORRECTED_PLAN.md Phase 0-1

### 为什么

1. B03/B04证明：agent发现真bug被判错 → 构造效度问题
2. 合同链[分类]→[证据]→[追踪]是线性的，但debugging是螺旋的
3. Judge和agent同模型 → 确认偏误
4. 没有人类基线 → 95.4%没有参照系

### 借鉴的大佬

- SWE-bench: 真实bug+真实修复=GT，不注射bug
- DSPy: 优化program不优化prompt，逐项验证不全部应用
- Delta Debugging (Zeller): 螺旋假设→验证→修正，不预分类
- Anthropic Eval: 多评估者+人类基线+对抗测试

### Phase 0: 人类基线 ($0, 第一步)

```
凡哥手动做5个bug (T0/T3/T4/T7 + 1 trap)
→ 不限时不限工具
→ 记录: 分类/根因/conf/耗时
→ AI用新评分系统(0-10)打分
→ 得人类锚点分数
```

### Phase 1: 基础建设 ($0)

```
1. 改 bughunt_t2.js → 新评分系统 (根因4+修复3+过程2+bonus1)
2. 改 bughunt_t2.js → 螺旋合同链 v3.0-alpha
3. 提取10个真实bug → bughunt_mine.js → R01-R10/
4. 双模型judge (deepseek+sonnet, dispute flag)
```

### 当前状态

**缉凶 Skill:**
- v2.5 = 95.4±1.9pp (封版, production)
- v2.5.1 = v2.5 + F6 only (自审修了3问题, 待验证)
- v3.0 = 计划中的螺旋模型 (待实现)

**Benchmark:**
- 49 注入 bugs (保留, T1快速测试用)
- 0 真实 bugs (Phase 1 创建)
- 98 fix commits 待挖掘

**Infra:**
- evolve.py: 双文件(per-bug + summary), encoding修好, R1 only trigger
- growth_engine.py: T6_MINE=100 commits, mine需改进(查全项目不限于handlers/)
- VERIFICATION_PROTOCOL.md: 旧5-phase协议(已过时, 被CORRECTED_PLAN取代)
- CORRECTED_PLAN.md: 新修正计划(权威)

### 关键文件

```
.claude/benchmarks/bughunt/CORRECTED_PLAN.md  ← 先读这个
.claude/benchmarks/bughunt/MASTER_PLAN.md
.claude/benchmarks/bughunt/LEADERBOARD.md
.claude/benchmarks/bughunt/VERIFICATION_PROTOCOL.md  ← 已过时
.claude/benchmarks/bughunt/per_bug_results.tsv
.claude/benchmarks/bughunt/results.tsv
.claude/skills/缉凶.md  ← v2.5.1 (F6 patch)
.claude/pete-skill-evolve.py
```

### 上次教训

1. 注入bug测的是"找藏东西"不是"debugging" ← 最重要的洞察
2. 线性合同链迫使agent过早锁定分类 ← v2.6退化的深层原因
3. GEPA teacher诊断准处方险 ← 单F-rule安全,全应用危险
4. 数据太少不能支撑5环引擎 ← 砍到3环
5. 同模评自己 = 确认偏误 ← 双模judge
