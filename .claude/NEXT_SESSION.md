# 新对话指令

你是皮特。读 `f:\ClaudeFiles\.claude\CLAUDE.md`。

## 当前任务：试剑石 v2.5.1 验证 + 成长引擎驱动

### 背景

两天跑了 ~20 次 Workflow，$~20。缉凶 v2.5 封版 95.4±1.9pp。v2.6 GEPA 退化→回滚。当前 v2.5.1 = v2.5 + F6(T4配置检查)。

### 最终状态 (2026-06-22 19:20)

**缉凶 Skill:**
- **v2.5 = 95.4±1.9pp (n=3) — 封版基线**
- v2.6 GEPA R1 = 90% — **退化 -5.4pp，已回滚**
- **v2.5.1 (当前) = v2.5 + F6 only** — 待 T2 验证
- Bare = 89.6±4.7pp (n=3) → skill lift +5.8pp

**v2.6 退化根因:**
- 合同链重排序 ([分类]→[证据] 改为 [证据]→[分类]) — 主退化源
- F7 (断言前搜索) + F8 (跨bug RESET) — 过度约束
- GEPA teacher 诊断准确，但 7 项改动全应用导致退化。应逐项验证

**v2.5.1 改动 (仅 F6):**
- 决策流 Q9: 症状可被配置差异(nginx/proxy_pass/port/env)解释 → T4
- F6 致命误判: T4 专属配置检查通过前不许读源码
- T4 强制 3 步: config diff / port check / startup log

**试剑石 Benchmark:**
- 49 bugs: B01-B35 + B36-B38(trap) + M01-M08(git-mined) + T01-T03(TokenLine)
- 8 T-Types, 5 languages, 2 projects
- 4层管线: T0($0)→T1($0.03)→T2($0.50)→T3($5)
- Hold-out: B16,B18,B25,B28,B31,B33,B36,B38,M05,T03 (10 hardest)
- 预注入分支: `bughunt/bug-branch` (B02/B06/B10 pre-applied)

**Growth Engine:**
- `pete-skill-evolve.py` v2 — 5环成长编排器 (已修: encoding + TSV格式)
- `results.tsv` — 8次 run (v2.5×3, v3.0×3, bare×1, v2.6×1)
- R1_MINE 触发: 98 fix commits → `python growth_engine.py mine`
- R2/R3/R4/R5 需要 per-bug 数据格式 (当前 summary 格式不兼容)

### 立即开始

```
1. 跑 v2.5.1 T2 验证 (3 runs, $1.50) → 确认 ≥93%
2. 跑 growth_engine.py mine → 从 98 fix commits 挖 5-10 新 bugs
3. 人审新 bugs → 加入 bugset/ → 更新题库计数
4. 如果 v2.5.1 ≥93%: 更新 leaderboard, 封版
5. 如果 v2.5.1 <93%: 回滚 v2.5 (去掉 F6), 标记 F6 单独验证
6. T3 cross-model 对比 (Opus vs Sonnet vs DeepSeek)
7. 补 human baseline (凡哥手动做 3-5 bugs)
8. evolve.py R2/R3/R4/R5 适配 per-bug 格式
```

### 关键文件

```
.claude/skills/缉凶.md                    → v2.5.1 (F6 patch, 当前)
.claude/benchmarks/bughunt/
  bughunt_t0.js / t1.js / t1_full.js     → T0/T1 脚本
  bughunt_t2.js / t2_bare.js / t3.js     → T2/T3 脚本
  bughunt_t1_v3.js                        → 49-bug 批次 T1 (最新)
  bughunt_gepa.js                         → GEPA 反射优化器
  bughunt_mine.js                         → Git 挖矿
  MASTER_PLAN.md / LEADERBOARD.md         → 已更新
  results.tsv                             → 已修 (8 run, summary格式)
  bugset/B01-B38/ + M01-M08/ + T01-T03/  → 49 bugs
  growth_engine.py                        → 6-trigger 引擎
.claude/pete-skill-evolve.py              → 成长编排器 v2 (已修encoding)
```

### 上次对话关键教训

1. **Skills reduce variance 2.5x**, not just raise ceiling
2. **Worked examples are load-bearing** — 砍掉方差暴增 4x
3. **Contract chain order matters** — 重排序导致 -5.4pp 退化
4. **GEPA: diagnosis accurate, prescription dangerous** — 逐项验证,不全应用
5. **Single F-rule safe, structural change dangerous** — v2.5.1 策略
6. **Evolve.py R2/R3/R4/R5 need per-bug format** — 当前 summary TSV 不兼容,需修复
7. **98 fix commits in 14 days** — 大量未挖掘 bug 素材
8. **Human baseline + multi-model 是"顶级"的剩余缺口**

### 已修基础设施

- `results.tsv`: 统一为 8 列 summary 格式 (旧 per-bug 数据已替换)
- `pete-skill-evolve.py`: 修复 subprocess encoding + emoji/Unicode print 错误
- `缉凶.md`: v2.6 → 回滚 v2.5 + F6 → v2.5.1
