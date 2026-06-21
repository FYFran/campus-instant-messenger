# 新对话指令

读 `f:\ClaudeFiles\.claude\pedia\skill-compliance-research.md` 了解完整研究背景。
读 `f:\ClaudeFiles\.claude\skills\skill-lab\SKILL.md` 了解 v0.3 框架。
读 `f:\ClaudeFiles\.claude\benchmarks\bughunt\README.md` 了解 benchmark。

## 当前状态

| 组件 | 版本 | 状态 |
|------|------|------|
| **缉凶** | v2.0 合同框架 | ✅ 102行, 16 test-prompts, 6 Gotchas, 5 Red Lines |
| **skill-lab** | v0.3 Lint-Gated | ✅ 20 lint rules, L3定性标注, MEL模板, Mutation-to-Lint |
| **BugHuntBench** | v0.1 | ✅ 10 bugs, 3/10 baseline跑完 (19/21=90.5%) |
| 铁壁 | v1.x | ⏳ 待 v0.3 重评 |
| 火眼 | v1.x | ⏳ 待 v0.3 重评 |
| campus-code-review | v1.x | ⏳ 待 v0.3 重评 |
| campus-deploy/quality-gate/red-team | v1.x | ⏳ 待合同框架重写 |
| pantheon-custom/gap-custom | v0.1 新建 | ⏳ 待合同框架重写 |

## 缉凶 v2.0 核心设计（不要再推翻）

**合同框架 7 步链：** 分类→证据→追踪→分析→修复→验证→记录
**5 Red Lines：** 不复现不修 / 不CF不提交 / 不测试不修 / 3次失败→STOP / 修前确认部署文件
**MEL 4 模式：** full / quick / safe / emergency(3 Red Lines, 事后24h补链)
**可成长性 5 触发：** 3+同模式→crystallize / 3+合同失效→review / 50+无失效→review / 意外失败→候选Gotcha / 真实bug→test追加
**环境假设 5 项：** IP/回归脚本/部署映射/bug模式库/报告目录

## 评分体系（v0.3 Lint-Gated）

- L1: 静态 Lint（20 条规则，便宜，每轮跑）
- L2: test-prompts 断言（16 条，便宜，每轮跑）
- L3: 独立 agent spot-check（定性标注 REAL/REAL*/TEMPLATE/WRONG/NOT_RUN，贵，每 3 轮跑）
- L3 不参与定量分数——作为防骗标签随分数报告

## 缉凶评分

定量: 100.0 (20/20 lint + 16/16 assertions + ALL 6 DIMS=10)
定性: [L3: REAL*] (主分析正确, 次要细节偏差)

## 研究依据（9 源交叉验证，不可再推翻）

强证据：<200行(4源) / 审计链(Compliance Gap 0%→97%) / 确定性检查>LLM判LLM(DOF 96.8%) / SkillOpt bounded edit+rejected buffer(52/52最优) / Anthropic官方<200行
中证据：Claude 4.8 负面约束95%+ / 2 reviewer > 1 self-check / 1-2示例最优
弱证据/Gamage争议：halftrace(64traj非学术) / Gamage vs Cambridge复现失败(106pp摇摆)

## 待办（优先级排序）

1. **BugHuntBench 完整跑分** — 跑完剩余 7 个 bug (B02-B05, B07, B09-B10)
2. **铁壁 + 火眼 + campus-code-review → 合同框架重写** — <200行, 同缉凶模式
3. **campus-deploy/quality-gate/red-team → 合同框架重写** — 基线 65-72, 目标 95+
4. **pantheon-custom/gap-custom → 合同框架重写** — 基线 65, 目标 95+
5. **BugHuntBench 公开** — 10 bugs + 自动判分 + 多 skill 排行榜
6. **Mutation-to-Lint 脚本** — extract_pattern.py 自动化

## 关键文件

- `f:\ClaudeFiles\.claude\skills\缉凶.md` — 缉凶 v2.0
- `f:\ClaudeFiles\.claude\skills\缉凶-test-prompts.json` — 16 test cases
- `f:\ClaudeFiles\.claude\skills\skill-lab\SKILL.md` — skill-lab v0.3
- `f:\ClaudeFiles\.claude\skills\skill-lab\results.tsv` — 完整优化历史
- `f:\ClaudeFiles\.claude\benchmarks\bughunt\` — BugHuntBench
- `f:\ClaudeFiles\.claude\pedia\skill-compliance-research.md` — 研究汇总

## 核心哲学（继承+新增）

- 合同框架 > 指令清单（Compliance Gap + Guardrails + Plan Compliance）
- 每步产出 = 下步门票（审计链强制执行）
- 短 > 长（<200行/<3000 token）
- 确定性检查 > LLM判LLM（L1+L2不用LLM）
- L3 防骗不评分（LLM judge 有天花板，只做定性标注）
- 自评不算数（A/B执行测试 + benchmark）
- Bounded edit ≤4处 + rejected buffer（SkillOpt）
- 可成长性: 3+触发→crystallize（SkillRL/AceForge）
- 不编造 / 不吹牛逼 / 推翻就承认
