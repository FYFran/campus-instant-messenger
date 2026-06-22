# 新对话指令

你是皮特。读 `f:\ClaudeFiles\.claude\CLAUDE.md`。

## 当前任务：试剑石 v2.5.1 验证 (Phase 1-3)

### 上次完成 (2026-06-22 19:35)

**判定:** v2.6 GEPA R1=90% (-5.4pp) → 回滚 v2.5 → v2.5.1 = v2.5 + F6 only

**v2.5.1 改动 (3项,已自审修复3问题):**
- 决策流 Q9: 症状可被配置差异解释**且近期有部署/重启** → T4
- F6 致命误判: T4 配置检查通过前不许读源码
- T4 强制 3 步 (含逃生舱: 3步全过无异常→门禁解除)
- 3 个自审发现已修: Q9 触发过宽 / F6 死锁 / 配置检查范围窄

**基础设施:**
- `per_bug_results.tsv`: 恢复 10 bugs (B01-B10) 历史 per-bug 数据
- `results.tsv`: 统一 8 列 summary 格式, 8 runs (v2.5×3 + v3.0×3 + bare×1 + v2.6×1)
- `pete-skill-evolve.py`: encoding 修复 + R2/R3 用 per-bug 数据 + R4/R5 用 summary + append_per_bug()
- `growth_engine.py`: T6_MINE=99 commits 触发, mine 发现 2 candidates
- `VERIFICATION_PROTOCOL.md`: 5 Phase 验证协议, 总预算 $3.00
- 2 commits 已 push

### Per-Bug 失败分析 (v2.1 基线 10 bugs)

| Bug | Type | Score | 失败维度 | 根因 |
|-----|------|-------|---------|------|
| B01 | T0 | 7/8 | — | 完美命中 nil deref |
| B02 | T1 | 7/8 | — | 完美命中 race condition |
| **B03** | **T2** | **2/8** | class+root+cf+fix | 分类 T_AUTH(非T0-T7), 发现真bug但非GT |
| **B04** | **T3** | **2/8** | class+root+cf+fix | 分类 T9, 发现真bug但非GT |
| **B05** | **T4** | **3/8** | root+cf+fix | T4对但根因错(Login token vs nginx port) ⭐F6目标 |
| B06 | T5 | 7/8 | — | 完美命中 state machine |
| **B07** | **T6** | **6/8** | root(partial) | T6对, 根因方向对但不精确 |
| B08 | T7 | 7/8 | — | 完美命中 NOT_A_BUG |
| B09 | T1 | 7/8 | — | 完美命中 missing await |
| B10 | T3 | 7/8 | — | 完美命中 N+1 query |

**关键洞察:**
1. B03/B04 失败模式 = agent 发现真正的 bug 但不是 GT 指定的 bug。**评分系统本身的问题** — agent 能力越强,越可能发现额外 bug 然后被判错。
2. B05 = F6 精确目标。旧 agent: Login token 代码问题。GT: nginx proxy_pass 错端口。F6 强制先查配置 → 应解决。
3. B07 = partial。T6 分类对但根因不精确。**非分类问题,是深层追踪问题。** 加 T6 专项 worked example 可能有用。
4. v2.5 从 ~65% 提升到 95.4% — 说明 F1-F5 致命误判 + worked examples 解决了 B03/B04/B05/B07 的大部分问题。

### 立即开始 (按验证协议执行)

```
# Phase 1 (免费): 改 T2 脚本 → 输出 per-bug 数据
1. 读 bughunt_t2.js → 加 per-bug 7维评分输出
2. 跑一次 dry-run → 确认 per-bug 数据写入 per_bug_results.tsv

# Phase 2 ($1.50): v2.5.1 T2 3-run
3. python bughunt_t2.js --skill v2.5.1 --runs 3
4. 计算 mean ± SD
5. 判定: ≥93% → 继续 P3 / <93% → 走决策树

# Phase 3 ($0.50): Hold-out gap
6. python bughunt_t2.js --skill v2.5.1 --bugs holdout
7. 计算 in-sample vs hold-out gap

# 后续 (根据 P2/P3 结果)
8. P4: Cross-model judge ($1.00) — 如果 P2 ≥93%
9. P5: Human baseline ($0 + 凡哥时间) — 如果 hold-out gap ≥5pp
```

### 关键文件

```
.claude/skills/缉凶.md                        → v2.5.1 (F6 patch, 当前)
.claude/benchmarks/bughunt/
  VERIFICATION_PROTOCOL.md                     → 5-Phase 验证协议
  MASTER_PLAN.md / LEADERBOARD.md             → 已更新
  per_bug_results.tsv                          → 10 bugs per-bug 数据
  results.tsv                                  → 8 runs summary
  bughunt_t2.js / t2_bare.js / t3.js          → T2/T3 脚本
  bughunt_t1_v3.js                             → 49-bug T1
  growth_engine.py                             → 6-trigger 引擎
.claude/pete-skill-evolve.py                   → 5环编排器 v2.1 (双文件+per-bug)
```

### 上次教训

1. **GEPA teacher 诊断准确,处方危险** — 7 改动全应用→退化。逐项验证。
2. **单 F-rule 安全,结构改动危险** — v2.5.1 策略 (F6 only)
3. **合同链顺序是 load-bearing** — [分类]→[证据] 不能颠倒
4. **B03/B04 失败 = 评分系统问题** — agent 找真 bug 被判错。考虑 "bonus for real bug discovery" 评分维度
5. **Per-bug 数据是定向改进的前提** — 没有它只能猜
6. **97% 分数 vs 95.4% 真实** — keywords fallback 虚高已修,现在 honest
