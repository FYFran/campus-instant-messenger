# BugHuntBench v2.0

> Agent Skill 质量基准 — 像 ML test set 一样测 Skill 文本质量。
> 对标 SWE-bench + AgentBeats + AdaRubric。
> 核心洞察: **Skill 文本改一行，分数就变。SWE-bench 测模型，BugHuntBench 测 Skill。**

## 评分（满分 8/bug）

| 维度 | 分值 | 判定 |
|------|------|------|
| 分类正确 | 1 | T-Type 与 ground truth 一致 |
| 产出链完整 | 1 | 7 步合同链每步产出非空 |
| 证据充分 | 1 | 复现步骤 + baseline 可验证 |
| 根因正确 | 2 | 根因与 ground truth 一致（含 file:line）。部分正确=1 |
| Counterfactual | 1 | CF 有可验证 pre/post 证据 |
| 修复正确 | 1 | 修复消除根因，不引入新问题 |
| 轨迹合规 | 1 | 无 gate 跳过，无红线违反 |

\+ **L3 防骗标注:** REAL / REAL* / TEMPLATE / WRONG（不参与分数）

## Bug 覆盖

| ID | Type | 语言 | 难度 | 场景 |
|----|------|------|------|------|
| B01 | T0 | Go | 易 | nil deref after DB query |
| B02 | T1 | Go | 中 | race condition signup |
| B03 | T2 | Go | 难 | multi-factor permission check |
| B04 | T3 | Python | 中 | silent data miscalculation |
| B05 | T4 | Go | 易 | regression from config change |
| B06 | T5 | Go | 中 | state machine stuck |
| B07 | T6 | Mixed | 难 | CI vs local env mismatch |
| B08 | T7 | Go | 易 | NOT_A_BUG — working as designed |
| B09 | T1 | Python | 中 | missing await in async code |
| B10 | T3 | Go | 难 | N+1 query silent performance bug |

## 快速开始

```bash
# 列出所有 bug
python bughunt_ci.py --list

# 快速评分（规则，零 token）
python bughunt_ci.py --mode quick --bugs B01,B02,B03

# 全量评分（LLM Judge）
python bughunt_ci.py --mode full --bugs all

# 查看历史结果
python bughunt_ci.py --summary

# CI 门禁
python bughunt_ci.py --gate-only --mode quick
```

## 执行流程

```
1. Bug Factory 注入 bug → 代码库
2. Harness spawn 独立 agent（盲测）
3. Agent 用目标 skill 排查 → 输出 bug report
4. Auto Scorer: L1 规则 + L2 LLM Judge + L3 验证
5. CI Gate 判定 PASS/FAIL
```

## 三层管线

| 层级 | 触发 | 成本 | 时间 |
|------|------|------|------|
| Quick | 每次 commit | 0 token | <1s |
| Full | 每晚 | ~50K/bug | ~2min |
| Verify | 每周/PR前 | ~300K/bug | ~5min |

## 文件结构

```
bughunt/
├── README.md                ← 你在这里
├── SCORING.md               ← 评分框架
├── DESIGN_v2.md             ← 设计蓝图
├── bughunt_harness.py       ← 核心库（解析/评分/结果）
├── auto_scorer.py           ← 自动评分引擎
├── bughunt_ci.py            ← CI 门禁脚本
├── results.tsv              ← 历史评分记录
├── RUN_2026-06-21.md        ← 完整跑分报告
├── bugs/                    ← 10 个 bug (描述 + ground truth)
│   ├── B01_T0_nil_deref.md
│   ├── B02_T1_race_condition.md
│   └── ...
└── results/                 ← (待创建) 每次跑的详细输出
```

## 最新成绩

**2026-06-21 完整跑分:** 53/70 = 75.7% (10 bugs, 缉凶 v2.0)

详见 [RUN_2026-06-21.md](RUN_2026-06-21.md)

## 设计依据

- **SWE-bench** (Princeton): 3人审核 + test-pass验证 + 私有集防作弊
- **Agent Evaluation 6-Dimension Rubric** (2026): 工具选择/参数提取/结果利用/错误恢复/计划连贯/任务完成
- **AdaRubric** (ACL 2026): 任务自适应 rubric，Pearson r=0.79
- **Human-on-the-Bridge** (2026): 人类设陷阱 + LLM执行评估
- **AgentBeats** (2026): A2A+MCP 标准化 agent-vs-agent 评估
- **Compliance Gap** (arXiv:2605.01771): LLM 0%指令合规 → L3防骗标注
