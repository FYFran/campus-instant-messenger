# 试剑石 Leaderboard

> 最后更新: 2026-06-22 | 49 bugs, 8 T-Types, 5 languages, 2 projects

## 缉凶 Skill — 诚实评分 (semantic direction, no keyword fallback)

| Version | Score | T-Type | Trials | SD | Date | Status |
|---------|-------|--------|--------|-----|------|--------|
| **v2.5.1 (F6)** | **91.5%*** | **9.3/10** | **3** | **±1.9pp** | 2026-06-22 | **Production** |
| v2.7-hybrid | 86.7% | 8.3/10 | 3 | ±8.1pp | 2026-06-22 | Rejected (high variance) |
| v3.0-lite | 91.7%* | 9.0/10 | 3 | ±7.3pp | 2026-06-22 | Rejected (high variance) |
| Bare (no skill) | 89.6% | 6.7/10 | 3 | ±4.7pp | 2026-06-22 | Baseline |

*Estimated honest score. Original 95.4% had ~4pp keyword fallback inflation (fixed).
*Estimated honest score. Original 91.7% had keyword fallback inflation (fixed).

## v2.7-hybrid Experiment (3-run, honest scoring)

| Run | Score | T-Type | Bonus | Key Failures |
|-----|-------|--------|-------|-------------|
| R1 | 86.3% | 8/10 | 3/10 | B03(T2→T3), B09(T1→T3) |
| R2 | 95.0% | 10/10 | 0/10 | B03 root=0 only |
| R3 | 78.8% | 7/10 | 1/10 | B04(4/8), B05(5/8), B08(T7→T3) |

Mean: 86.7±8.1pp. **4x higher variance than v2.5. Hypothesis tracking adds noise.** → Rejected.

## Exp C: Bonus Bug Prevalence

| Run | Bonus Count | Bugs | Verdict |
|-----|------------|------|---------|
| R1 | 3/10 | B03, B09, B10 | ADD_BONUS_DIMENSION |
| R2 | 0/10 | — | NOISE |
| R3 | 1/10 | B08 | NOISE |

**High judge variance on bonus criterion. Bonus dimension unreliable with current judge.** → Deferred.

## Exp B: Spiral vs Linear (3 bugs)

| Bug | Spiral type | Linear type | Winner |
|-----|------------|-------------|--------|
| B05 (T4) | T4 ✅ | T4 ✅ | Linear (better root cause) |
| B07 (T6) | T6 ✅ | T6 ✅ | Tie |
| M03 (T3) | T2 ❌ | T3 ✅ | Linear |

**Linear 3/3, Spiral 2/3.** → Linear retained.

## Skill Lift

| Skill | Mean | vs Bare | Verdict |
|-------|------|---------|---------|
| 缉凶 v2.5.1 | ~91.5% | +1.9pp | ✅ Production |
| 缉凶 v2.7-hybrid | 86.7% | -2.9pp | ❌ Rejected |
| 缉凶 v3.0-lite | ~87% | -2.6pp | ❌ Rejected |

## Key Findings

1. **Skills reduce variance, not just raise ceiling.** v2.5 SD=±1.9pp vs Bare SD=±4.7pp (2.5x more stable).
2. **Worked examples are load-bearing.** 砍掉→方差暴增 4x (v3.0 SD=±7.3pp).
3. **Hypothesis tracking increases variance.** v2.7-hybrid SD=±8.1pp — agent overthink simple bugs.
4. **Single F-rule safe, structural change dangerous.** F6(T4 config check) works. Spiral model doesn't.
5. **GEPA diagnosis accurate, prescription risky.** Teacher found real patterns but applying all 7 degraded performance.
6. **Bonus bug detection unreliable with single judge.** 3/10→0/10→1/10 variance across runs.

## Trap Bugs

| Bug | Agent → Truth | Result |
|-----|---------------|--------|
| B36 | T1 → T7 (rate limiter NOT_A_BUG) | ✅ Deceived |
| B38 | T0 → T5 (lazy init state issue) | ✅ Deceived |

## Bug Library

| Source | Count | Types |
|--------|-------|-------|
| B01-B35 | 35 | T0-T7 campus_go |
| B36-B38 | 3 | Trap bugs |
| M01-M08 | 8 | Git-mined (real commits) |
| T01-T03 | 3 | TokenLine |
| **Total** | **49** | **2 projects, 5 languages**

## Cost Efficiency

| Tier | Cost/run | Purpose |
|------|----------|---------|
| T0 | $0 | Pre-commit rule gate |
| T1 | $0.03 | T-Type classification |
| T2 | $0.50 | Full investigation + judge |
| T3 | $5.00 | Cross-model + bare baseline |

## Today's Spend

| Item | Cost |
|------|------|
| Exp B (A/B spiral) | $0.15 |
| T2 R1 (v2.7-hybrid) | $0.50 |
| T2 R2 (v2.7-hybrid) | $0.50 |
| T2 R3 (v2.7-hybrid) | $0.50 |
| **Total** | **$1.65** |
