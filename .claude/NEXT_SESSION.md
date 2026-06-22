# 新对话 — 从这里开始

你是皮特。读 `f:\ClaudeFiles\.claude\CLAUDE.md`。

## 试剑石状态 — Phase 1-3 完成

```
Phase 1 ✅ Inject patches: B01-B10 16/16 OK (was 13)
Phase 2 ✅ Bare baseline: B03/B04/B07 ($0.15)
Phase 3 ✅ SkillAxe 4-dim: D4 weakest, F9/F10 generated
Phase 4 ⏳ B01v2/B02v2 verification ($0.10)
Phase 5 ⏳ 铁壁 baseline ($1.50)
```

## 当前数据

```
缉凶 v2.5: 76.3/80, CI [75.0-78.0], n=3 — solid
Bare:      71.0/80, n=1 (summary), n=2 per-bug (B03/B04/B07)
Skill lift: +5.3pp (SkillsBench SE avg +4.5pp)

Per-bug: 13 entries across 10 bugs
  B03: n=3 (skill=2 + bare=1), root_hit 67%
  B04: n=2 (skill=1 + bare=1), root_hit 50%
```

## 工具

```
python .claude/pete-skill-evolve.py check    成长触发
python .claude/benchmarks/bughunt/verify_injections.py --behavior  构造效度
python .claude/benchmarks/bughunt/bootstrap_ci.py     统计 CI
python .claude/benchmarks/bughunt/skillaxe_diagnose.py --suggest  诊断
python .claude/benchmarks/bughunt/judge_calibrate.py stats       校准
```

## 预算: $3.20/$5.00，剩 $1.80

## 待做
1. Phase 4: B01v2/B02v2 T2 Lean 验证 ($0.10)
2. Phase 5: 铁壁 10 bugs baseline ($1.50)
3. Judge 真校准: double-judge per_bug entries ($0.10)
4. B05 降级: T4→需决定是代码bug还是配置bug
