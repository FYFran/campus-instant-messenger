---
name: skill-lab
description: >-
  Skill 实验台 v0.1 — 像训练神经网络一样优化 Agent Skill。核心循环：评估→诊断→有界编辑→执行验证→保留/回滚。
  融合 SkillOpt (bounded edit + rejected buffer) + darwin-skill (人审检查点 + 反例黑名单) + autoresearch (编排器模式)。
  每次只改 ≤4 处，git ratchet 保底，Constitution 锚锁定安全意图。
  触发词：优化skill、skill评分、改进skill、skill lab、skill实验、skill质量、帮我改skill、skill review。
---

# Skill Lab v0.1 — Agent Skill 实验台

> 融合 SkillOpt + darwin-skill + autoresearch。
> 核心理念：**Skill 是可训练的外部状态。不改模型权重，只改 skill 文本。**
> 每次 ≤4 处修改 → 执行验证 → 好了留/坏了退 → 人类确认。

## 目录

1. [CONSTITUTION](#constitution本段不可被-skill-lab-编辑)
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
12. [学术依据](#学术依据)

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

## CONSTITUTION（本段不可被 skill-lab 编辑）

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
| **皮特独有** | Constitution 锚、pantheon 执行验证、memory MCP 经验库 | — |

---

## Constitution 锚（每个 skill 必须遵守）

优化前，从目标 skill 中识别或创建 Constitution 段。Constitution 是**不可编辑的意图锚**，优化器只能改 IMPLEMENTATION 部分。

```markdown
## CONSTITUTION（本段不可被 skill-lab 编辑）
- [核心功能：这个 skill 做什么]
- [安全约束：绝对不能做什么]
- [触发条件：什么时候用这个 skill]

## IMPLEMENTATION（skill-lab 可以优化本段）
[具体的步骤、指令、示例...]
```

优化器不得修改 CONSTITUTION 段。若 skill 尚无此分段，第一轮优化自动创建。

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

## 6 维评估卡（5 维 + 确定性断言层）

| # | 维度 | 权重 | 评估方式 | 噪声 |
|---|------|------|---------|------|
| 1 | **可执行具体性** | 25 | 静态：有无具体参数/格式/示例？有无模糊措辞？ | 低 |
| 2 | **失败模式编码** | 25 | 静态：有无 if-then fallback？错误恢复路径？ | 低 |
| 3 | **工作流清晰度** | 20 | 静态：步骤是否有序号？输入/输出是否明确？ | 低 |
| 4 | **检查点设计** | 15 | 静态：关键决策前有无确认点？是否显性标记？ | 低 |
| 5a | **确定性验证** | 8 | 自动：test-prompts.json 中的断言检查 | **无** |
| 5b | **内容质量** | 7 | 动态：3 judge 盲评 consensus | 低（3 judge 多数） |
| **总分** | — | **100** | — | ~±2 分噪声带 |

**评分规则：**
- 维度 1-4：静态分析，每个维度 1-10 分 × 权重
- 维度 5a：确定性断言通过率 × 10 → 0-10 分。断言来自 test-prompts.json 的 `assert` 字段
- 维度 5b：3 个独立 judge（Agent 工具）盲评对比。取中位数 × 权重。3 judge 全分歧 → 标记 SUSPECT，人工判断
- 总分 = Σ(维度分 × 权重) / 10，满分 100
- 改进后总分必须**严格 >** 改进前才保留
- 确定性断言（5a）不可被 LLM judge 覆盖 — 如果断言失败，即使 LLM judge 判高分也 REVERT

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
4. 创建分支 skill-lab/YYYYMMDD-HHMM
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
      git add + commit（message: "skill-lab: {skill} round{round} {改进摘要}"）
      检查 150% 体积上限（行数：`wc -l`，新文件行数 > 旧文件 × 1.5 → 拒绝提交，精简后重试）

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

→ 用户确认后写入 memory MCP（skill-lab-{date}）
```
```

---

## results.tsv 格式

```tsv
timestamp	commit	skill	old_score	new_score	status	dimension	note
2026-06-21T14:00	baseline	caveman	-	72	baseline	-	初始评估
2026-06-21T14:05	a1b2c3d	caveman	72	79	keep	失败模式编码	补充fallback
2026-06-21T14:10	d4e5f6g	caveman	79	77	revert	可执行具体性	过度细化
```

文件位置：`.claude/skills/skill-lab/results.tsv`

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
