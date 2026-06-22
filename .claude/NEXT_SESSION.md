# 新对话 — 从这里开始

你是皮特。读 `f:\ClaudeFiles\.claude\CLAUDE.md`。

## 上次完成: 第一个自动成长循环成功

**F7 MERGE — B05 从 5.3→7.7, root_cause 0→2。**

```
F7: "T4 + token/401 → curl 直连后端端口(绕过nginx) → 后端正常? → nginx。
     后端也401? → 代码。不经过此网络测试不许读源码。"
3-run验证: 7.7/8 mean, root_cause 2.0/2 (vs baseline 5.3, 0.0)
```

**生产 skill: v2.5.1 + F7。** B05 已修复。B03 仍待修复 (F8 候选)。

## 当前状态

```
缉凶 skill: F1-F7, 92.6% honest baseline (n=3)
  B05 fixed (F7) ✅
  B03 pending (F8 candidate: "assert-missing must prove absent")

系统: 18 commits, $2.90 spent
  T2 全量 ($0.50) + T2 Lean ($0.05/bug) + T3 Lean ($0.50)
  F7 验证 ($0.15) — 第一个自动成长循环
  memory-indexer + judge-calibrate (免费)

待做 (全部自动化, $0.30):
  1. 跑 F8 验证 (B03, $0.15)
  2. 退役 5 个饱和 bugs → 生成变体
  3. 铁壁 skill 上 benchmark
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
  growth_candidates.md                        → F7✅ F8待验证
  bughunt_t2.js / t2_lean.js / t3_lean.js    → 测试脚本
  bughunt_validate_f7.js                      → F7 验证脚本
.claude/pete-skill-evolve.py                  → 成长编排器
.claude/pete-memory-index.py                  → 跨会话记忆
.claude/pete-judge-calibrate.py              → Judge 自动校准
```
