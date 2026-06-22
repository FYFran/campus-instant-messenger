# 新对话 — 从这里开始

你是皮特。读 `f:\ClaudeFiles\.claude\CLAUDE.md`。

## 上次完成: F8 DISCARD + 基准构造效度修复 + 饱和退役

**F8 DISCARD — mean 4.0/8 (vs baseline 6.3).** 不是skill问题 — 基准构造效度bug。

B03 GT说 `strings.Contains` 部分匹配 (T2)，但实际注入的代码中 ListActivities SQL **完全没有** college 过滤条件 (T0)。代码中没有任何 `strings.Contains`。所有 3 个 agent 正确识别了真实 bug (T0: missing filter)，但 judge 因 GT 不一致而扣分。

**B03 GT 已修复:** desc.md + truth.md 现在匹配实际注入 (T0: missing college filter in ListActivities)。

## 当前状态

```
缉凶 skill: v2.5.1 + F7 (production), F8 DISCARD
  B05 fixed (F7: 5.3→7.7) ✅
  B03 GT fixed (T2→T0, construct validity) ✅
  F8 rule correct but inapplicable (bug IS genuinely missing, not imprecise)

饱和退役:
  B01→B01v2 (cache indirection + misleading stack trace)
  B02→B02v2 (cross-endpoint race + misleading UNIQUE violation)
  B06, B08, B09: archived, variants pending

系统: $3.05 spent
  F7 验证 ($0.15) — 第一个自动成长循环
  F8 验证 ($0.15) — DISCARD，但发现构造效度问题
  memory-indexer + judge-calibrate (免费)

待做:
  1. 生成 B06v2/B08v2/B09v2 变体
  2. 铁壁 skill 上 benchmark
  3. 跑 T2 全量验证新变体可解性
```

## 快速启动

```
python .claude/pete-skill-evolve.py check   # 成长触发检测
python .claude/pete-memory-index.py scan     # 跨会话模式
python .claude/pete-judge-calibrate.py check # Judge 校准
```

## 关键文件

```
.claude/skills/缉凶.md                       → v2.5.1 + F7 (production)
.claude/benchmarks/bughunt/
  FINAL_DESIGN.md                             → 完整系统设计
  growth_candidates.md                        → F7✅ F8 DISCARD
  bugset/B03/                                 → GT fixed (T2→T0)
  bugset/B01v2/ + B02v2/                      → 新变体
  archive/RETIRE_v1.md                        → 退役记录
.claude/pete-skill-evolve.py                  → 成长编排器
