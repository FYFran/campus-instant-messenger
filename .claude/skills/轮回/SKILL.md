---
name: 轮回
description: >-
  Skill 实验台 v0.3 — 像训练神经网络一样优化 Agent Skill。核心循环：评估→诊断→有界编辑→Lint→Spot-Check→保留/回滚。
  融合 SkillOpt (bounded edit + rejected buffer) + darwin-skill (人审检查点 + 反例黑名单) + autoresearch (编排器模式)。
  每次只改 ≤4 处，git ratchet 保底，Constitution 锚锁定安全意图。
  触发词：优化skill、skill评分、改进skill、skill lab、skill实验、skill质量、帮我改skill、skill review。
---

# Skill Lab v0.1 — Agent Skill 实验台

> 融合 SkillOpt + darwin-skill + autoresearch。
> 核心理念：**Skill 是可训练的外部状态。不改模型权重，只改 skill 文本。**
> 每次 ≤4 处修改 → 执行验证 → 好了留/坏了退 → 人类确认。

## 目录

1. [CONSTITUTION](#constitution本段不可被-forge-编辑)
2. [Quick Reference](#quick-reference-速查)
3. [设计哲学](#设计哲学)
4. [6 维评估卡](#6-维评估卡5-维--确定性断言层)
5. [核心循环](#核心循环) (Phase 0→0.5→1→2→3)
6. [子 Agent 生成机制](#子-agent-生成机制维度-5b-内容质量验证)
7. [收敛循环定义](#收敛循环定义)
8. [反例黑名单](#反例黑名单优化时绝对不要做的事)
9. [异常处理](#异常处理)
10. [红绿灯分级](#红绿灯分级人类介入程度)
11. [使用方式 + 歧义处理](#使用方式--歧义处理)
12. [Phase 4: DISCOVER](#phase-4-discover--从失败中发现新-skillevoskill-模式)
13. [使用追踪](#使用追踪usage-tracker)
14. [学术依据](#学术依据)

## Quick Reference（速查）

| 想做什么 | 怎么做 |
|---------|--------|
| 优化单个 skill | `优化 {skill名}` → Phase 0-3 |
| 评估所有 skill | `评估所有 skill` → Phase 0-1 only |
| 只看不改 | 自动停在 Phase 1，不进 Phase 2 |
| 恢复被拒修改 | `git log` 找 revert commit，不会被 `git reset --hard` 丢 |
| 查看历史 | 读 `results.tsv` |
| 规则速查 | 每次 ≤4 处修改 · 不碰 CONSTITUTION · git revert 不回退 reset · 🔴 必须人审 |

---

## CONSTITUTION（本段不可被 forge 编辑）

### 核心功能
- 像训练神经网络一样优化 Agent Skill 文本（不改模型权重）
- 核心循环：评估→诊断→有界编辑(≤4处)→执行验证→保留/回滚
- 输出优化后的 skill + 完整实验记录 (results.tsv)

### 安全约束
- 绝不修改目标 skill 的 CONSTITUTION 段
- 绝不跳过人类确认就修改 🔴 tier skill
- 绝不使用 LLM judge 替代执行验证（SkillLens: LLM判分准确率 46.4%）
- 绝不使用 `git reset --hard`（只使用 `git revert`）
- 优化后 skill 体积不得超过原始 150%

### 触发条件
- 用户说：优化skill/skill评分/改进skill/skill lab/skill实验/skill质量/帮我改skill/skill review
- 不触发：纯聊天、问概念、不涉及 skill 文件的任务

---

## 设计哲学

| 来源 | 取什么 | 不取什么 |
|------|--------|---------|
| **SkillOpt** | bounded edit、rejected buffer、epoch early stop、best_skill.md 部署 | 全自动（无人审）、单 skill、需外部 API |
| **darwin-skill** | 人审检查点、反例黑名单、150% 体积上限、git ratchet | LLM judge 评分（46.4% 不准）、9 维 rubric 过度复杂 |
| **autoresearch** | 编排器模式、state 持久化、安全不变量 | 通用任务框架（非 skill 专用） |
| **皮特独有** | Constitution 锚、pantheon 执行验证、memory MCP 经验库、DISCOVER 新 skill 发现、使用追踪 | — |

---

## Constitution 锚（每个 skill 必须遵守）

优化前，从目标 skill 中识别或创建 Constitution 段。Constitution 是**不可编辑的意图锚**，优化器只能改 IMPLEMENTATION 部分。

```markdown
## CONSTITUTION（本段不可被 forge 编辑）
- [核心功能：这个 skill 做什么]
- [安全约束：绝对不能做什么]
- [触发条件：什么时候用这个 skill]

## IMPLEMENTATION（forge 可以优化本段）
[具体的步骤、指令、示例...]
```

优化器不得修改 CONSTITUTION 段。若 skill 尚无此分段，第一轮优化自动创建。

---

## Mutation-to-Lint — 合成变异自动发现新 lint 规则

> **原理：** 不等 judge 发现盲区——主动制造缺陷看 lint 能否捕获。类似 mutation testing。
> **目标：** lint 漏报率 < 5%（50 个 mutation 中 <3 个漏报）。

**流程：**
```
1. 取已知高质量 skill（lint 全 PASS）
2. 每类常见错误生成 5 个 mutation：
   M1 删 gate row    M2 改工具名      M3 混平台命令
   M4 删回退链       M5 变量未定义    M6 Mode描述不一致
   M7 断言不对齐     M8 缺终端出口     M9 IP硬编码无注释
   M10 重复内容措辞不同
3. 每个 mutation → 跑 Pre-Judge Lint
4. 漏报（lint PASS 但 mutation 引入了真实缺陷）→ 分析 → 新 lint 规则
5. 追加到 Pre-Judge Lint（L16, L17...）
```

**运行频率：** 每次 lint 规则更新后重跑。新 skill 创建时跑。

**常见错误类型库（持续增长）：**
| # | Mutation 类型 | 示例 | 期望 lint 捕获 |
|---|--------------|------|---------------|
| M1 | 删 gate row | 删 `\| 5 \| 未先写测试 \| BLOCK \|` | L2 |
| M2 | 改工具名 | PREFLIGHT 检测 `python3` 但命令用 `python` | L11 |
| M3 | 混平台命令 | Phase 6 只有 bash 无 PowerShell | L1 |
| M4 | 删回退链 | Phase 3a 删 `codegraph失败→TIER1 rg` | L6 |
| M5 | 变量未定义 | 用 `$UNDEFINED_VAR` | L3 |
| M6 | Mode 不一致 | QuickRef 说 Phase 5 skip 但 Phase 5 prose 没提 | L5 |
| M7 | 断言不对齐 | test 要求 `mustContain: "Silent"` 但 skill 文本无此词 | L4 |
| M8 | 缺终端出口 | Error Recovery 删 `BLOCK immediately` | L8 |
| M9 | 硬编码无注释 | IP 地址无说明 | L14 |
| M10 | 重复内容分歧 | Iron Law 两处措辞不同 | L15 |

**与 Judge-to-Lint 的关系：**
- Judge-to-Lint: 发现**新类别**的盲区（人类/judge 视角）
- Mutation-to-Lint: 发现**已知类别内**的盲区（系统性覆盖）
- 两者互补：Judge 发现 M11 类型 → 追加到 mutation 库 → 所有 skill 受益

---

## L3: Spot-Check Verification — 独立验证 agent

> **原理：** Compliance Gap 论文证明了违规从输出文本本身**无法检测**。必须用独立 agent 做 spot-check——不信任执行 agent 的输出，独立验证关键 Phase。
> **对应：** SkillOpt 的 validation gate（不信任 rollout 结果，独立评估）。
> **频率：** 每 3 轮 forge 优化后跑 1 次（昂贵但必要）。

**流程：**
```
1. 目标 skill 执行后产生输出（如缉凶的 Bug Report）
2. 独立验证 agent 被 spawn——无目标 skill 上下文，无执行 agent 记忆
3. 抽查 2 个关键 Phase 输出：
   Check A — Counterfactual 真实性：
     "修了 X 后 bug 不再出现"——是否有独立验证证据？（不只是声明）
     是否有 pre/post 对比数据？
   Check B — 分类正确性：
     T-Type 分类依据是否成立？是否有证据支持？
     如果分类错误——整个后续链都错了
4. 每项判定：REAL（真实分析）/ TEMPLATE（填模板）/ WRONG（分析错误）
5. 任一 TEMPLATE 或 WRONG → skill 质量标记 SUSPECT → 回 forge Phase 2 优化
```

**验证 Prompt 模板：**
```
你是独立验证 agent。检查以下 bug report 的 Phase {N} 输出。

原始 bug 描述: {bug_description}
Phase {N} 输出: {phase_output}

判定标准：
- REAL: 分析包含具体代码引用/数据/逻辑推理，不是套话
- TEMPLATE: 格式正确但内容空洞。如"修后 OK"无 pre/post 对比。
- WRONG: 分析有事实错误。如引用的代码行不存在。

返回: {"phase": "N", "verdict": "REAL|TEMPLATE|WRONG", "evidence": "具体引用"}
```

**L3 结果记录：**
```
forge Phase 2 Step 3.5 之后追加：
  Step 3.6 — L3 Spot-Check（每 3 轮 1 次）：
    跑 L3 验证 → 全 REAL→进 Step 4。有 TEMPLATE/WRONG→回 Step 1。
    记录结果到 results.tsv 的 L3 列。
```

---

## MEL 分级模板

> **来源：** 航空最低设备清单（MEL）概念。不是所有情况都需要完整流程。

**三级定义（所有 skill 默认支持）：**

| 模式 | 触发 | 内容 | 合规要求 |
|------|------|------|---------|
| **full** | 默认 | 完整审计链 | 全 Phase 输出 |
| **quick** | 用户说"快速/诊断/看看" | 只诊断不修复部分 | 关键 Phase 输出 |
| **emergency** | 用户说"紧急/挂了/立刻" | 只 3 条不可跳过的红线 | 事后 24h 内补全审计链 |

**Emergency 模式的 3 条红线（所有 skill 通用）：**
1. **不可逆操作前确认** — 部署/删除/迁移前必须有人 approve
2. **pre/post 对比** — 改动前后有可验证的差异证据
3. **回退路径** — 如果改坏了，能回到改动前状态

**Skill 作者声明 MEL：** 在 skill 的 Quick Reference 中声明 emergency 模式的具体行为。

---

## 反例黑名单（优化时绝对不要做的事）

这些是真实踩过的坑。每轮改动前对照一次。任一命中 → 改方案重写。

| # | 反模式 | 为什么不要做 | 替代做法 |
|---|--------|-------------|---------|
| 1 | **同 context 自评自改** | 改完立刻在同一 session 打分，有「我刚改的肯定更好」偏差（SkillLens：LLM-as-judge 准确率 46.4%≈随机） | spawn **独立子 agent** 执行测试验证，至少跑 2 次取平均 |
| 2 | **`git reset --hard` 当回滚** | 丢工作树未提交改动，CI 历史断裂 | 用 `git revert HEAD` 创建反向 commit |
| 3 | **为凑分增冗余** | 触顶后硬改加废话让 LLM 觉得更详细，实际质量不变 | 连续 2 轮 Δ < 阈值 → break 见好就收 |
| 4 | **跳过测试直接改** | 没有测试就改 = 没有方向，改对改错全凭运气 | 强制先设计/确认 test-prompts，再改 |
| 5 | **一轮改多个维度** | 多变量同时变，分数升降无法归因 | 每轮 1 个维度 |
| 6 | **静默跳过异常** | git/文件异常时静默继续，破坏 ratchet 完整性 | 异常先告知用户，再按规则处理 |
| 7 | **改 CONSTITUTION** | 破坏 skill 的核心意图和安全约束 | CONSTITUTION 段标记为不可编辑 |
| 8 | **优化安全/部署类 skill 不经人审** | 安全相关 skill 的改动可能有严重后果 | 🔴 tier skill 必须人类敲 "approve" |

---

## 6 维评估卡（Lint-Gated — v0.2）

> **设计原则（2026 学术证据）：** LLM-as-judge 存在结构性天花板——评分压缩(σ_J/σ_H≈0.3-0.5)、误差相关(9 judge≈2 有效票)、高质量输出最难评。
> 因此：LLM judge 只做粗筛（<90 vs ≥90），精细判别交给确定性检查（Pre-Judge Lint + 断言）。

| # | 维度 | 权重 | 评估方式 | 噪声 |
|---|------|------|---------|------|
| 1 | **可执行具体性** | 25 | 静态：L1,L5,L6 检查项覆盖 | 低 |
| 2 | **失败模式编码** | 25 | 静态：L6,L7,L8 检查项覆盖 | 低 |
| 3 | **工作流清晰度** | 20 | 静态：L3,L10 检查项覆盖 | 低 |
| 4 | **检查点设计** | 15 | 静态：L2 检查项覆盖 | 低 |
| 5a | **断言验证** | 10 | 自动：test-prompts.json 断言通过率×10 | **无** |
| 5b | **Lint 门禁** | 5 | 自动：Pre-Judge Lint 10项全 PASS→满分 | **无** |
| **总分** | — | **100** | — | **~±1 分（v0.1 的 ±2→±1）** |

**评分规则（v0.2 核心变更）：**
- 维度 1-4：静态分析，对照 Pre-Judge Lint 逐项打分。不再主观判断——每项 PASS/FAIL 有客观标准
- 维度 5a：test-prompts.json 断言通过率 × 10。这是执行验证，不是 judge 评分
- 维度 5b：Pre-Judge Lint 10项 → 全 PASS = 10 分。每 FAIL 1 项 = -1 分。最低 0 分
- **不再使用 3-judge blind consensus 做精细判别。** Judge 只用于：(a) 粗筛（明显 <90 的 skill 识别）(b) 发现新 lint 规则（L11, L12...）
- 总分 = Σ(维度分 × 权重) / 10，满分 100

**L3 定性标注（不进入分数，但必须随分数报告）：**

> L3 是独立 agent 对执行质量的 spot-check。不参与定量评分——因为 L3 本身是 LLM agent，有天花板（和 dim5b 老问题一样）。但它作为"防骗标签"：100 分 + REAL ≠ 100 分 + TEMPLATE。

| 标注 | 含义 | 对分数的解读 |
|------|------|-------------|
| **REAL** | spot-check 的 Phase 输出是真实分析，所有数据准确 | 分数可信 |
| **REAL\*** | 分析框架正确，根因判断对，但次要细节/数字有偏差 | 分数基本可信，细节需校准 |
| **TEMPLATE** | 格式正确但内容空洞（如"修后 OK"无 pre/post 对比） | **分数虚高**—执行质量未达标 |
| **WRONG** | spot-check 发现事实错误（如引用的代码行不存在） | **分数无意义**—skill 有功能缺陷 |
| **NOT RUN** | L3 本轮未执行（每 3 轮跑 1 次，成本 ~100K token） | 分数待验证 |

**判定逻辑：**
```
主分析(Counterfactual+根因)真实 + 所有数据准确 → REAL
主分析真实 + 次要数据有 1-2 处偏差 → REAL*
主分析真实 + 多处数据错误 或 无验证证据 → TEMPLATE
主分析错误 或 引用不存在的代码 → WRONG
```

**报告格式：**
```
Score: 95.0 [L3: REAL]     ← 真 95
Score: 100.0 [L3: TEMPLATE] ← 假 100
Score: 92.0 [L3: NOT RUN]   ← 待验证
```

**为什么废弃 3-judge 精细评分：**
- Kohli 2026: "9 个 judge 提供 ~2 个有效票的信息量"
- Song 2026: "高质量输出 paradoxical 地收到最不一致的评估"
- Mukherjee 2026: "LLM 评分轴与人类几乎正交(87°-89°)" 
- 我们的实测：5 轮 15 judge，median 始终 8.7-9.0，无法突破 9.0
- **结论：LLM judge 能区分 7 分和 9 分的 skill，但不能区分 9 分和 9.5 分**

### test-prompts.json 格式（含断言）

```json
[
  {
    "id": 1,
    "scenario": "典型场景描述",
    "prompt": "用户会说的话",
    "assert": {
      "mustContain": ["必须包含的文字1", "必须包含的文字2"],
      "mustNotContain": ["禁止出现的文字", "might", "could考虑"],
      "regex": ["匹配模式1", "匹配模式2"],
      "lengthMin": 50,
      "lengthMax": 2000
    },
    "expect": "期望输出的简短描述（给 LLM judge 看的）"
  }
]
```

`assert` 字段是可选的。如果 skill 类型不适合确定性断言（如风格类 skill），5a 自动记满分，5b 承担全部 15 分。

---

## 核心循环

### 子 Agent 生成机制（维度 5b 内容质量验证）

```
用环境中实际存在的 Agent 工具（Tool: Agent）生成独立评估者。
关键：新会话、无编辑记忆、盲评。

# 盲评对比（优化后验证时）
Agent(
  subagent_type: "general-purpose",
  description: "Blind-judge {skill_name} prompt#{id}",
  prompt: '''
    Version A output: {old_output}
    Version B output: {new_output}
    Intent (from test-prompts.json): {expect}
    Which better fulfills the intent?
    Return ONLY: {"winner": "A" or "B" or "tie", "confidence": 0-100, "reasoning": "one sentence"}
  '''
)

# 3 judge consensus（降低方差）
# 3 个独立 judge 盲评 → 取多数（2/3 或 3/3）
# 3 judge 全分歧（A/B/tie 各一）→ 标记 SUSPECT，人工判断
# 单个 judge 置信度 < 50% → 该 judge 投票降权为 0.5
# 最终 score = (判 B 的加权票数 / 总加权票数) × 10

# Judge 评分校准（给 judge prompt 的标准评分指南）：
# 10: 零问题。每个 Phase/Mode/平台/边界完全一致。工具链完整。Gate 全。
# 9.5: 至多 1 个 trivial（如措辞偏好、不影响执行的格式）。Ship immediately。
# 9.0: 1-2 个 minor（如 gate table 缺行、某个工具回退链不完整）。Ship with note。
# 8.5: 多个 minor 或 1 个 medium（如跨平台缺口、mode 行为未定义）。Fix then ship。
# 8.0: 实质性缺口（如缺 Phase、无错误恢复）。Don't ship。
# "Trivial" = 不改也不影响 agent 正确执行。"Minor" = 可能导致某些边界下执行偏差。
# Judge 必须引用 file:line 作为问题证据。无代码引用的问题=无效。

# Critic 强制挑刺（super-fix 模式）：
# 每个 judge 必须至少指出 1 个改进空间。"两个版本都好"/"没问题"= 无效评估，重跑。
# 这防止 judge 偷懒给 B 满分——强制找出差异点。
```

### 收敛循环定义 + 铁律

```
收敛 = 连续 2 次 re-sweep 后总分提升 < 1 分（Δ < 1.0），且无新增维度评分下降。
"零新发现" = re-sweep 过程中未出现新的 FAIL 项或评分退化。
收敛即停。最多 3 个 re-sweep pass（预算保护）。

铁律（systematic-debugging 模式）：
  3+ 轮 re-sweep 无进展 → 停止微调。
  建议探索性重写（Phase 2.5），而非继续改同一个维度。
  微调无效时继续微调 = 浪费 token + 过度优化风险。
```

### Phase 0: 初始化 🔴 CHECKPOINT

```
1. 确认目标 skill：
   - 用户指定名字 → 直接定位 .claude/skills/{name}/SKILL.md
   - 用户说"全部"/"所有"/"all" → Glob(".claude/skills/*/SKILL.md") + Glob(".claude/skills/*.md")
   - 用户说"这个"/"它"/"那个" → 扫描当前对话上下文，找最近提到的 skill 名；找到→确认，找不到→追问
   - 用户没给名字 → 追问："哪个 skill？还是全部扫描？以下是当前可用的：[Glob 扫描结果]"
2. 🔴 CHECKPOINT · 🛑 STOP：展示找到的 skill 列表 + tier 分级，等用户确认范围
3. 检查 git 仓库状态
4. 创建分支 forge/YYYYMMDD-HHMM
5. 初始化 results.tsv（如不存在）
```

### Phase 0.5: 测试 Prompt 设计 🔴 CHECKPOINT

```
for each skill in 范围:
  1. 读 SKILL.md，理解 skill 功能
  2. 生成 2-3 个测试 prompt（覆盖 happy path + 边界 + 歧义场景）
  3. 如果用户说"不要改"/"只评估"/"只看不改" → 🔴 CHECKPOINT: "需要写入 test-prompts.json 才能评估。可以吗？"
     用户同意 → 保存。用户拒绝 → 跳过该 skill，标记 dry_run，维度 5 使用干跑模拟打分。
  4. 如果用户未限制修改 → 保存到 {skill目录}/test-prompts.json
展示所有测试 prompt 给用户，确认后再进入 Phase 1。
如果 test-prompts.json 已存在 → 展示 + 问"复用 / 重写 / 追加"三选一。
```

### Phase 1: 基线评估

```
for each skill in 范围:
  # 静态分析（主 agent）
  1. 读 SKILL.md 全文
  2. 按维度 1-4 逐项打分（附简短理由）

  # 确定性验证（维度 5a — 无 LLM）
  3. 对每个测试 prompt：
     - 用 Read 工具获取 skill 执行后的输出
     - 逐条检查 test-prompts.json 的 assert 规则
     - 通过率 × 10 = 维度 5a 得分

  # 内容质量（维度 5b — 3 judge 盲评）
  4. 对每个测试 prompt，spawn 3 个独立子 agent：
     - Agent(subagent_type="general-purpose"，盲评对比)
     - 取多数 consensus → 维度 5b 得分

  # 汇总
  5. 计算加权总分
  6. 记录基线到 results.tsv

🔴 CHECKPOINT · 🛑 STOP：展示所有 skill 的基线评分排名表 + 各 skill 最低维度
| Skill | Score | 最低维度 | 是否需要优化 |
|-------|-------|---------|-------------|
等用户确认优化范围，再进入 Phase 2。
```

### Phase 2: 优化循环

```
for each skill in 优化范围 (按基线分数从低到高排序):
  round = 0
  while round < MAX_ROUNDS (默认 3):
    round += 1

    Step 1 — 诊断：
      🔴 CHECKPOINT：展示本轮目标维度 + 改进方案，等用户确认
      找出得分最低的 1 个维度作为本轮目标
      （注意：维度 2/3/4 是相关簇，修一个时常带动另一个）

    Step 2 — 提出改进：
      生成 1 个具体改进方案（改什么 + 为什么 + 预期提升）
      约束：每次 ≤4 处修改，不碰 CONSTITUTION 段

    Step 3 — 执行改进：
      编辑 SKILL.md
      git add + commit（message: "forge: {skill} round{round} {改进摘要}"）
      检查 150% 体积上限（行数：`wc -l`，新文件行数 > 旧文件 × 1.5 → 拒绝提交，精简后重试）

    Step 3.5 — 🔴 Pre-Judge Lint（新增：防吹牛逼门禁）：
      **必须跑完以下检查清单才能进 Step 4。跳过=自评分=吹牛逼。**
      
      | # | 检查项 | 来源 |
      |---|--------|------|
      | L1 | 跨平台一致性：Win/Linux 命令是否都有等价实现？ | J4,J7,J9 |
      | L2 | Gate table 完整性：每 Phase 🔴 gate 是否在门控表有对应行？ | J10,J11 |
      | L3 | 变量定义：所有 `{var}` / `$VAR` 模板变量是否已定义？ | J2,J8 |
      | L4 | 断言对齐：test-prompts 的 mustContain/regex 是否匹配 skill text 实际措辞？ | J12 |
      | L5 | Mode 一致性：QuickRef mode 描述 ↔ per-phase table ↔ 各 Phase 内 prose 三方一致？ | J1,J5,J10 |
      | L6 | 工具回退链：TIER2 失败→TIER1 回退是否在每个 Phase 都写明？ | J3,J6 |
      | L7 | Gotcha 覆盖：每个 `禁止`/`别做` 是否有对应 Gotcha 条目？每个 Gotcha 是否与正文细节一致？ | J7 |
      | L8 | 终端升级路径：最坏情况（所有工具都不可用）是否有明确的 BLOCK/MANUAL 出口？ | J3 |
      | L9 | test-prompts 覆盖：每个 T-Type / Phase / Mode 是否有至少 1 个 test prompt？ | J12 |
      | L10 | 生产安全：print()/写操作是否区分 dev/prod？ | J13,J15 |
      | L11 | 工具名一致性：PREFLIGHT 检测的工具名与下游命令使用的名是否一致？（如检测python3但命令用python） | J16,J18 |
      | L12 | Quick/skip mode 依赖完整性：跳过的 Phase 产出是否被后续 Phase 硬编码引用？（如跳过3b但4a引用其输出） | J16,J17,J18 |
      | L13 | 测试断言跨平台：assert 中的工具名/命令是否在所有平台都有效？（如 strace 仅 Linux） | J16 |
      | L14 | 环境配置抽象：是否有硬编码 IP/端口/路径？至少标注说明 | J18 |
      | L15 | 重复内容一致性：同一规则/法律出现多次时措辞完全一致？标注权威版本 | J16,J17 |
      | L16 | Gate 语义正确性：gate 表动作(BLOCK/回 Phase N/STOP)与 Phase prose 实际指令一致？(不只是存在，而是正确) | M11 |
      | L17 | 错误路径测试覆盖：每个 Error Recovery 类别是否有 ≥1 test prompt？ | M12 |
      | L18 | 控制流清晰度：条件分支(only/skip/非T4)的进入/退出条件是否显式？无歧义重排风险 | M13 |
      | L19 | 否定断言覆盖：STOP/SKIP gate 的 test prompt 是否验证下游 Phase 不出现？ | M14 |
      | L20 | 升级可执行性：BLOCK/上报动作是否指定通道(console/file/git issue)？不只是说"上报" | M15 |

      任一 FAIL → 修 → 重跑该检查。全 PASS → 进 Step 4。
      此清单随 judge 新发现持续增长（Growability 模式）。

    Step 4 — 重新评估：
      维度 1-4：主 agent 重新打分
      维度 5a：确定性断言重跑（自动化，无噪声）
      维度 5b：spawn 3 个新独立 judge，盲评对比（见"子 Agent 生成机制"）
      关键：judge 不知道哪个是旧版、哪个是新版

    Step 5 — 决策：
      if 新总分 > 旧总分:
        status = "keep"，更新旧总分
        if 连续 2 轮 Δ < 2 分:
          print("触顶信号：连续 2 轮边际收益 < 2 分，避免过度优化")
          break
      else:
        status = "revert"
        git revert HEAD（创建新 commit，保留追溯链）
        记录失败原因到 rejected buffer
        break

    Step 6 — 日志：results.tsv 追加行

    # 收敛循环（production-audit 模式）：
    如果本轮 KEEP → 再跑一遍 Step 4 作为验证 pass
    验证 pass 扫出新问题 → 回到 Step 1 继续
    验证 pass 零新发现 → 该 skill 收敛，退出循环

  🔴 CHECKPOINT · 🛑 STOP：每个 skill 优化完后强制暂停
  展示：git diff + 分数变化 + 测试输出对比
  等用户确认 OK 再继续下一个 skill。
```

### Phase 3: 汇总报告 🔴 CHECKPOINT

```
🔴 CHECKPOINT · 🛑 STOP：展示汇总报告，等用户确认

### 总览
- 优化 skills 数：N / 总实验次数：M
- 保留改进：X（Y%）/ 回滚：Z
- 实测验证：A 完整测试 / B 干跑

### 分数变化
| Skill | Before | After | Δ | Rounds |
|-------|--------|-------|---|--------|
| {name} | 68 | 85 | +17 | 2 |

### 主要改进
1. [skill-A] {改进摘要} — +{Δ} 分

→ 用户确认后写入 memory MCP（forge-{date}）
```

---

## Phase 4: DISCOVER — 从失败中发现新 Skill（EvoSkill 模式）

当现有 skill 无法处理某个任务时，DISCOVER 分析是否需要**新 skill**。

```
触发条件：
  - 任务执行失败，且失败原因不是"skill 不够好"而是"没有对应的 skill"
  - 用户说"这个应该有个 skill" / "能不能自动做这个" / "缺个 skill"
  - 某个任务类型被手动执行了 3+ 次（重复劳动信号）

流程：
  1. Failure Analyzer — 分析最近的失败/手动任务：
     问：这个任务有 skill 覆盖吗？
     有 → 用 EVOLVE 优化那个 skill
     没有 → 继续

  2. Skill Proposer — 生成新 skill 提案：
     - 功能：这个 skill 做什么
     - 触发词：什么时候该用
     - 核心指令（草稿）
     - 与其他 skill 的关系（互补/依赖/独立）

  3. 🔴 CHECKPOINT · 🛑 STOP — 展示提案，等用户确认
     用户确认 → 创建 SKILL.md + test-prompts.json
     用户拒绝 → 记录到 rejected proposals

  4. Skill Builder — 自动生成：
     - .claude/skills/{name}/SKILL.md（含 CONSTITUTION）
     - .claude/skills/{name}/test-prompts.json（2-3 用例）
     - 更新 CLAUDE.md 路由表

  5. 创建完成后 → 自动进入 Phase 1（基线评估）
     然后可进入 Phase 2（优化循环）
```

### 重复劳动信号检测

```
扫描 forge/skill-usage.jsonl：
  如果同一 task_type 出现 3+ 次且无对应 skill →
  🔴 CHECKPOINT："我注意到你手动做了 3 次 {task_type}。要我创建一个 skill 来自动化吗？"
```

---

## 使用追踪（Usage Tracker）

每次 skill 被调用时，追加到 `.claude/skills/forge/skill-usage.jsonl`：

```json
{"timestamp": "2026-06-21T15:00", "skill": "campus-code-review", "task": "review auth.go changes", "outcome": "success", "tokens": 3200, "notes": "found 2 HIGH findings"}
```

**追踪维度：**
| 字段 | 用途 |
|------|------|
| timestamp | 使用频率分析 |
| skill | 哪个 skill 被触发 |
| task | 任务描述 |
| outcome | success/failure/partial |
| tokens | 消耗 token 数 |
| notes | 简要备注 |

**forge 如何使用追踪数据：**
- 按使用频率排序 → 优先优化高频 skill
- 按失败率排序 → 优先修复高失败率 skill
- 检测 180 天未使用的 skill → 提议退役
- 检测重复劳动信号 → 触发 DISCOVER

---

## results.tsv 格式

```tsv
timestamp	commit	skill	old_score	new_score	status	dimension	note
2026-06-21T14:00	baseline	caveman	-	72	baseline	-	初始评估
2026-06-21T14:05	a1b2c3d	caveman	72	79	keep	失败模式编码	补充fallback
2026-06-21T14:10	d4e5f6g	caveman	79	77	revert	可执行具体性	过度细化
```

文件位置：`.claude/skills/forge/results.tsv`

---

## 红绿灯分级（人类介入程度）

| Tier | Skill 类型 | 优化策略 | 人类角色 |
|------|-----------|---------|---------|
| 🟢 | 风格/UI/日志类 | 自动优化 + 通知 | 事后 review |
| 🟡 | 诊断/代码生成类 | 优化后暂停确认 | 每轮确认 |
| 🔴 | 安全/部署/支付/认证类 | 每步暂停 | 必须敲 "approve" |

默认所有 skill 从 🟡 开始。用户可将信任的 skill 降级到 🟢。

---

## 异常处理

| 场景 | 处理 |
|------|------|
| 不在 git 仓库 | 询问：`git init` 或文件备份 `.bak.YYYYMMDD-HHMM` |
| results.tsv 缺失 | 新建并写表头 |
| 分支已存在 | 分支名加 `-2`/`-3`，3 次失败则切回现有分支询问 |
| git revert 失败 | `git stash` 后重试；仍失败则从上个 commit 手动恢复 SKILL.md |
| 优化后 > 150% 体积 | 拒绝提交，精简后再评 |
| test-prompts.json 缺失 | Phase 0.5 自动生成，展示用户确认 |
| MAX_ROUNDS 触顶 | 展示当前最弱维度，问用户「加 1 轮 / 收工」 |

---

## 使用方式 + 歧义处理 + 分级执行

### 分级执行（super-fix 模式）
| 模式 | 触发 | 行为 |
|------|------|------|
| **full** | `优化 {skill}` (默认) | Phase 0→0.5→1→2→3 全流程，3 judge 盲评 |
| **quick** | `快速评估 {skill}` | Phase 0→1 only，1 judge，跳 test-prompts 生成 |
| **safe** | `安全优化 {skill}` | full 流程但跳过 🔴 tier 的自动编辑，每步人审 |

### 使用方式

```
用户："优化 {skill名}" 或 "{skill名} skill评分"
→ Phase 0-3 完整流程，单个 skill (full 模式)

用户："优化全部" / "优化所有" / "全部skill"
→ Phase 0: Glob(".claude/skills/*/SKILL.md") + Glob(".claude/skills/*.md")
→ 展示找到的 skill 列表，确认范围 → Phase 0.5-3

用户："评估所有 skill 的质量" / "skill评分" / "skill质量"
→ 只跑 Phase 0-1（扫描 + 基线），不进入 Phase 2

用户：没说具体 skill 名（"优化skill" / "帮我看下skill" / "{模糊}"）
→ 回问："哪个 skill？还是全部扫描？以下是当前可用的 skill 列表：[扫描结果]"
→ 绝不默认假设某个 skill 或盲目进入优化

用户：代词("这个/它/那个") + 模糊意图("怎么样/行不行")
→ 两步分解（不合并成一个问题）：
  Step A: 代词解析 → 扫描对话上下文找最近提到的 skill 名
    找到 → "你是指 {skill_name} 吗？"
    找不到 → "哪个 skill？以下是当前可用的：[扫描结果]"
  Step B: 用户确认 skill 后 → "要评估（只看不改）还是优化（改进它）？"
→ 先解析对象，再确认动作。避免一次问两个问题让用户困惑。

用户："看看 skill 优化历史"
→ 读取 results.tsv 展示

用户："优化所有 🟢 skill"
→ Glob 扫描 → 筛选 🟢 tier → 自动优化，跳过 🟡🔴
```

### 批处理机制

```
当范围 = 多个 skill 时：
1. Glob 扫描 .claude/skills/：
   - 目录型: .claude/skills/{name}/SKILL.md
   - 文件型: .claude/skills/{name}.md
2. 读取每个 skill 的 frontmatter（name + description）→ 列出清单
3. 确认范围后，逐个处理（串行，非并行 — git 分支冲突风险）
4. 每个 skill 结果记录到同一 results.tsv
5. Phase 3 汇总报告聚合所有 skill 数据
```

---

## 学术依据

- **SkillOpt** (arXiv 2605.23904): validation-gated bounded edit 形式化框架。代码 [microsoft/SkillOpt](https://github.com/microsoft/SkillOpt)
- **SkillLens** (arXiv 2605.23899): LLM-as-judge 准确率 46.4%，加 meta-skill 维度 → 73.8%
- **autoresearch** (Karpathy): 自主实验循环，630 行 Python。`github.com/karpathy/autoresearch`
- **darwin-skill**: 首个 Claude Code SkillOpt 集成，微软官方 2026-06-03 列入集成名单。`github.com/alchaincyf/darwin-skill`

---

## 版本

v0.1 · 2026-06-21 · 皮特 Skill Lab 初始版本。
核心循环可用。DISCOVER/CURATE/通宵自主模式 规划在 v0.2+。
