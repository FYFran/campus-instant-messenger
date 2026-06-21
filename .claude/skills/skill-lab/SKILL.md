---
name: skill-lab
description: >-
  Skill 实验台 v0.1 — 像训练神经网络一样优化 Agent Skill。核心循环：评估→诊断→有界编辑→执行验证→保留/回滚。
  融合 SkillOpt (bounded edit + rejected buffer) + darwin-skill (人审检查点 + 反例黑名单) + autoresearch (编排器模式)。
  每次只改 ≤4 处，git ratchet 保底，Constitution 锚锁定安全意图。
  触发词：优化skill、skill评分、改进skill、skill lab、skill实验、skill质量、帮我改skill、skill review。
---

# Skill Lab v0.1 — Agent Skill 实验台

> 融合 Microsoft SkillOpt (arXiv 2605.23904) + darwin-skill + Karpathy autoresearch。
> 核心理念：**Skill 是可训练的外部状态。不改模型权重，只改 skill 文本。**
> 每次 ≤4 处修改 → 执行验证 → 好了留/坏了退 → 人类确认。

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

## 5 维评估卡（简化自 SkillLens 9 维）

| # | 维度 | 权重 | 评估方式 |
|---|------|------|---------|
| 1 | **可执行具体性** | 25 | 静态：有无具体参数/格式/示例？有无模糊措辞？ |
| 2 | **失败模式编码** | 25 | 静态：有无 if-then fallback？错误恢复路径？ |
| 3 | **工作流清晰度** | 20 | 静态：步骤是否有序号？输入/输出是否明确？ |
| 4 | **检查点设计** | 15 | 静态：关键决策前有无确认点？是否显性标记？ |
| 5 | **实测表现** | 15 | 动态：跑 test-prompts，对比优化前后输出质量 |

**评分规则：**
- 维度 1-4：静态分析，每个维度 1-10 分 × 权重
- 维度 5：跑 test-prompts，spawn 独立子 agent 对比输出，1-10 分 × 权重
- 总分 = Σ(维度分 × 权重) / 10，满分 100
- 改进后总分必须**严格 >** 改进前才保留

---

## 核心循环

```
Phase 0: 初始化
  ├─ 确认目标 skill（单个 / 列表）
  ├─ 检查 git 仓库状态
  ├─ 创建分支 skill-lab/YYYYMMDD-HHMM
  └─ 初始化 results.tsv（如不存在）

Phase 0.5: 测试 Prompt 设计
  ├─ 读 SKILL.md，理解 skill 功能
  ├─ 生成 2-3 个测试 prompt（覆盖 happy path + 边界 + 歧义场景）
  ├─ 展示给用户确认
  └─ 保存到 {skill目录}/test-prompts.json

Phase 1: 基线评估
  ├─ 维度 1-4：主 agent 静态分析打分
  ├─ 维度 5：spawn 独立子 agent 跑测试 prompt
  │   ├─ with_skill: 带 skill 执行
  │   └─ baseline: 不带 skill 执行（或对比旧版 skill）
  ├─ 计算加权总分
  ├─ 识别最低维度
  └─ 记录基线到 results.tsv
  🔴 CHECKPOINT · 🛑 STOP：展示基线评分 + 最低维度，等用户确认

Phase 2: 优化循环
  round = 0
  while round < MAX_ROUNDS (默认 3):
    round += 1

    Step 1 — 诊断：
      找出得分最低的 1 个维度作为本轮目标
      （注意：维度 2/3 是相关簇，修一个时常带动另一个）

    Step 2 — 提出改进：
      针对目标维度，生成 1 个具体改进方案：
        - 改什么（具体段落/行）
        - 为什么改（对应哪个评估维度）
        - 预期提升多少分
      约束：每次 ≤4 处修改，不碰 CONSTITUTION 段

    Step 3 — 执行改进：
      编辑 SKILL.md
      git add + commit（message: "skill-lab: {skill} round{round} {改进摘要}"）
      检查 150% 体积上限

    Step 4 — 重新评估：
      维度 1-4：主 agent 重新打分
      维度 5：spawn 新独立子 agent 重跑测试（关键！不能复用旧结果）

    Step 5 — 决策：
      if 新总分 > 旧总分:
        status = "keep"
        更新旧总分
        if 连续 2 轮 Δ < 2 分:
          print("触顶信号：连续 2 轮边际收益 < 2 分，停止优化")
          break
      else:
        status = "revert"
        git revert HEAD（创建新 commit 回滚，不用 reset --hard）
        记录失败原因到 rejected buffer
        break  # 该 skill 到瓶颈

    Step 6 — 日志：
      results.tsv 追加行

  🔴 CHECKPOINT · 每个 skill 优化完后强制暂停
  展示：
    - git diff（改前 vs 改后）
    - 分数变化（哪些维度提升/下降）
    - 测试 prompt 输出对比
  等用户确认 OK 再继续下一个 skill。

Phase 3: 汇总
  ├─ 优化 skills 数 / 总实验次数 / 保留率 / 回滚次数
  ├─ 分数变化表（Before / After / Δ）
  └─ 主要改进摘要
  → 写入 memory MCP（skill-lab-{date}）
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

## 使用方式

```
用户："优化 caveman skill"
→ Phase 0-3 完整流程，单个 skill

用户："评估所有 skill 的质量"
→ 只跑 Phase 0.5-1（设计测试 + 基线），不进入优化

用户："看看 skill 优化历史"
→ 读取 results.tsv 展示

用户："优化所有 🟢 skill"
→ 扫描全部 skill，自动优化 🟢 tier，跳过 🟡🔴
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
