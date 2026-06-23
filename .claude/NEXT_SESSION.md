# 下一会话

## 系统状态 (2026-06-23 22:20)

### 本次完成
- ✅ GEPA transcript 审计 — 发现 B03/B04 是基准校准问题，B05 是真缺陷
- ✅ 缉凶 v3.1 → v3.2: Gotcha#9 (T4→infra) + Red Line#7 (T4 gate)
- ✅ auto_scorer valid_alternative: partial credit for finding real bugs (arXiv:2511.10865)
- ✅ Commit: f0d23c3 — all hooks pass, 飞轮 11/11 STABLE
- ✅ 缉凶 adjusted baseline: 6.1 → ~7.0 (estimate, re-benchmark pending)

### 发现的关键阻塞
- **其他 5 个 skill (门神/破阵/布阵/火眼/试金石) 没有 bugset**
  - baselines.json 的 L1_quick 分数只是结构检查，不是行为基准
  - 需要创建 desc.md + truth.md + verify.sh 才能跑 L2 baseline
- Bugset 目录只有 B01-B38 (缉凶专用)，共 61 个目录

### 11 Skill — 0 issues, 0 warnings
| Skill | Baseline | pass@k | Bugset |
|------|---------|--------|--------|
| 铁壁 v2.1 | 8.0 | pass@3 | ✅ S01-S03 |
| 明镜 v2.1 | 8.0 | pass@2 | ✅ C01-C03 |
| 破阵 v2.1 | 8.0 L1 | — | ❌ R01-R03 未创建 |
| 缉凶 v3.2 | ~7.0 (est) | pass@3 | ✅ B01-B38 |
| 布阵 v3.0 | 8.0 L1 | — | ❌ D01-D03 未创建 |
| 门神 v2.1 | 8.0 L1 | — | ❌ Q01-Q03 未创建 |
| 火眼 v1.1 | 8.0 L1 | — | ❌ G01-G03 未创建 |
| 试金石 v1.0 | 8.0 L1 | — | ❌ M01-M08 未创建 |

### 待做 (优先级排序)

1. **创建非缉凶 skill 的 bugset**（最高优先级 — 解锁 L2 baseline）
   - 门神: Q01(False pass) Q02(Check skip) Q03(Threshold bypass)
   - 破阵: R01(Bypass auth) R02(Chain LOW→HIGH) R03(Replay)
   - 布阵: D01(Missing backup verify) D02+03 pending
   - 火眼: G01(Prescan coverage) G02(Dimension cross-validate) G03(TBD)
   - 试金石: M01-M08 (可复用缉凶 bug，测测试生成质量)

2. **缉凶 re-benchmark**（等 bugset 创建完一起跑）
   - 用新 valid_alternative 评分重跑 38 bug
   - 确认调整后基线 7.0±0.3

3. **L2 自动触发**（等 bugset 全了再做）
   - PostToolUse hook: skill .md changed → auto drift check

4. **Python 代码 git 追踪**（submodule 残留）
5. **Flutter app 连接测试**

### 飞轮
- L0+L1: ✅ 自动运行正常
- L2: ❌ 等待 bugset + 自动触发
- L3: ❌ 等待数据积累

### 启动
1. `python -m mempalace mine` → wake-up → search
2. `python .claude/scripts/skill_health.py`
3. 继续创建 bugset 或跑缉凶 re-benchmark
