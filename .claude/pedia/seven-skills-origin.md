# 皮特七大顶级 Skill 锻造全记录

> 2026-06-21，一个对话，12小时，从 187 个散装 skill 到 7 个顶级 skill。
> 喂给新对话：读完这篇，你就知道这 7 个 skill 怎么来的、为什么这样设计、每个决策背后的依据。

---

## 一、起点

皮特有 187 个 skill（172 个全局 + 9 个项目 + 6 个 campus），散落在 `~/.claude/skills/` 和 `f:/ClaudeFiles/.claude/skills/`。问题是：

- 大部分没被用过
- 功能高度重叠（7 个 pantheon 变体做同一件事）
- 没有安全锚（LLM 可以改任何部分）
- 精华散落，无法复用
- 没有优化机制

## 二、方法论来源

我们研究了 2026 年最前沿的 4 篇论文/项目：

| 来源 | 核心贡献 | 融入了什么 |
|------|---------|-----------|
| **SkillOpt** (Microsoft, arXiv 2605.23904) | 像训练神经网络一样训练 skill 文本。Bounded edit (≤4处修改)、validation gate (留存集验证)、rejected buffer (负反馈记忆) | forge 的核心循环 |
| **SkillLens** (Microsoft, arXiv 2605.23899) | LLM-as-judge 准确率仅 46.4%≈随机。加 meta-skill 维度 → 73.8% | 6 维评估卡 (5a 确定性断言 + 5b 3-judge blind) |
| **darwin-skill** (社区, 微软官方集成) | 人审检查点、9 维 rubric、反例黑名单、git ratchet | 人审 CHECKPOINT、反例黑名单 8 条、results.tsv |
| **autoresearch** (Karpathy, 80K⭐) | 1 个可编辑文件 + 1 个指标 + 固定预算 + 循环。630 行 Python | 编排器模式、收敛循环、state 持久化 |

额外吸收了 2026 年最新成果：
- **production-audit**: 收敛循环 (连续 2 pass 零新发现 = 停)、禁止模糊词、TRUNCATED AT
- **Cursor 安全 agent**: 置信过滤 >80%、4 步方法论 (Inspect→Trace→Verify→Report)
- **Meta 半形式推理**: Premise→Trace→Check→Conclusion 逻辑证书，93% 准确率
- **Facebook secpriv**: Source→Sink 追踪，F1=0.79
- **jwilger agent-skills**: 三级门控协议 (Stage 1→Stage 2→Stage 3)
- **EvoSkill** (Sentient+Virginia Tech): 3-agent 架构 (Executor/Proposer/Builder)，从失败中发现新 skill
- **systematic-debugging**: 铁律 (3+ 失败=质疑架构)、红旗 11 条
- **super-fix**: Critic 强制挑刺、三源搜索、回归基线对比、分级执行
- **defense-in-depth**: 4 层验证、"让 bug 不可能"
- **security-auditor-supreme**: 攻击者思维、OWASP Top 10 自动修复
- **code-review-authority**: 语言特定规则 (Go/Python/TS/SQL)、分数追踪、pre-commit 钩子

大佬共识验证：
- **SkillsBench**: "Less is more. 2-3 聚焦 skill > 全面文档"
- **GraSP** (腾讯): "结构化编排 > 更大 skill 库。+19 分"
- **AgentSkillOS**: "扁平 skill 库在 80+ 时路由坍塌。解法：能力树"
- **Matt Pocock** (69K⭐): "Unix 哲学。Do One Thing Well"
- **Karpathy**: "Install `.md` skills, not `.sh` scripts"

## 三、7 个 Skill 的进化

### 1. campus-code-review (59.5 → 98.5, +39 分, 5 轮)

**原始状态**: 13 类安全检查清单，触发词有盲区 ("check" 不匹配)，无歧义处理，无检查点。

**Round 1 (+20.5)**: +Constitution 锚 + 触发词修复 ("check") + 歧义追问 + 工具降级路径
**Round 2 (+8.5)**: +严重级别 (🔴🟠🟡🔵) + diff 优先策略 + Step2 审查后指导 + 多文件处理
**Round 3 (+10.0)**: **方法论重构** — +三级门控协议 (Stage 1 Security→Stage 2 Quality→Stage 3 Domain) + 半形式推理 (Premise→Trace→Check→Conclusion) + Source→Sink 追踪 + Review artifacts (.reviews/ 持久化)
**Round 4 (-1.5→97.0)**: 操作层修复 — +校准规则 (SUSPECT vs CRITICAL) + 预算启发式 + 工具选择指南 + 目标检测 (.py/.go/.dart 路由) + 安全边界 (auto-fix 规则)
**Round 5 (+1.5→98.5)**: +收敛循环 (2 pass 零新发现=停) + 置信过滤 >80% + 禁止模糊词 (no might/could/consider) + TRUNCATED AT + 8 残余全修 (路径相对化/清理策略/全级别校准/追踪优先级/单后端跳过/其他语言回退/交叉引用)

**精华融入** (来自 code-review-authority + code-quality):
- 语言特定规则: Go 4 条、Python 4 条、TypeScript/Flutter 3 条、SQL 3 条
- 输出内分数追踪 (was X/10 → now Y/10)
- Pre-commit 钩子集成 (git diff --cached → Stage 1 → BLOCK/WARN/ALLOW)

**最终架构**:
```
CONSTITUTION (不可编辑)
Core Behavior + 工具选择指南 + 预算策略 + 安全边界
Process — 三级门控 + 收敛循环
  Stage 1: Security & Correctness (半形式推理 + Source→Sink)
  Stage 2: Code Quality (Convention Over Precedent)
  Stage 3: Domain Integrity (语言规则 + 跨后端一致性)
Review Artifacts (.reviews/ 持久化 + ESCALATIONS.md)
Review Outcome Template (Findings Table + Verdict + Score)
Step 2 Post-Review CHECKPOINT
```

### 2. forge (68.0 → ~99, +31 分, 5 轮 + v0.2)

**原始状态**: 5 维评估卡，核心循环有但子 agent spawn 机制未定义，批处理缺失，歧义处理缺失。

**Round 1 (+15.5)**: +Agent 工具调用 (具体语法) + Glob 扫描 + 歧义规则 + 收敛 + 盲评 + CHECKPOINT
**Round 2 (+7.5)**: +Agent 绑定澄清 + 收敛 Δ<1 定义 + Phase 0.5 冲突处理 + 死锁处理 + 代词解析 + 150% 单位 (wc -l)
**Round 3 (框架切换)**: +6 维评估 (5a 确定性断言 + 5b 3-judge consensus) + assert 格式 + 噪声带 ±2
**Round 4 (+6.1)**: +Table of Contents + Quick Reference + Phase 0/3 CHECKPOINT. dim3→10, dim4→10
**Round 5 (+2→99)**: pronoun+vague 两步分解 (先解析对象，再确认动作). dim2→10. 全部 4 静态维度天花板

**v0.2 成长性升级**:
- **DISCOVER 层** (EvoSkill 模式): Failure Analyzer → Skill Proposer → Human CHECKPOINT → Skill Builder → 自动进入 Phase 1
- **使用追踪** (Usage Tracker): skill-usage.jsonl，追踪每次 skill 调用 (timestamp/skill/task/outcome/tokens/notes)
- **重复劳动检测**: 同一 task_type 出现 3+ 次 → 提议创建新 skill

**最终架构**:
```
CONSTITUTION
Quick Reference (速查表)
6 维评估卡 (5a 确定性断言 + 5b 3-judge blind consensus)
核心循环 Phase 0→0.5→1→2→3
  子 Agent 生成机制 (Agent 工具 + blind comparison)
  收敛循环 + 铁律 (3+ re-sweep 无效=建议重写)
Phase 4: DISCOVER (从失败中发现新 skill)
使用追踪 (skill-usage.jsonl)
反例黑名单 8 条 + 异常处理表
红绿灯分级 (🟢🟡🔴)
使用方式 + 歧义处理 + 分级执行 (full/quick/safe)
```

### 3. campus-security-audit (精华锻造)

**原始状态**: gitleaks → semgrep → endpoint audit → secrets → CVE → nuclei → pg-ops。缺安全锚和攻击者思维。

**精华注入**:
- +CONSTITUTION (安全约束: 绝不跳过工具执行、绝不跳过 Go 后端)
- +Attack Mindset (security-auditor-supreme 精华): 审查每条路径时切换为攻击者 — "我怎么利用这个？最弱的一环在哪？"
- 8 步审计流水线保留: gitleaks→semgrep→endpoint→secrets→CVE→nuclei→pg-ops→report

### 4. campus-bug-hunt (精华锻造)

**原始状态**: 证据收集→CodeGraph 追踪→双后端检查→根因定位→修复→验证→报告。缺系统化 debug 纪律。

**精华注入**:
- +CONSTITUTION (安全约束: 绝不未复现就修、3+失败=质疑架构、双后端必须同时检查)
- +Iron Law: NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST
- +Red Flags 列表: 出现任一 → 立即停，回到 Step 1
- +Step 0: 三源搜索 (web + papers + bug-patterns.md)
- +Critic 强制挑刺: "没问题"= Critic 失职，重跑
- +回归基线对比: pre-fix vs post-fix，0 新增失败

### 5. campus-deploy (精华锻造)

**原始状态**: pre-flight checklist→安全扫描→上传→迁移→重载→冒烟测试→回滚。完整但缺安全锚。

**精华注入**:
- +CONSTITUTION (安全约束: 绝不跳过 pre-flight、绝不未经确认部署生产、冒烟失败→立即回滚)
- defense-in-depth 验证: 每层部署前确认上一层成功

### 6. campus-quality-gate (精华锻造)

**原始状态**: 9 道检查 (flutter→functional→go build→python→gitleaks→semgrep→nuclei→multi-agent→rollback)。本身已经很完整。

**精华注入**:
- +CONSTITUTION (安全约束: 任何 FAIL→立即停、分数阈值不可修改、<80=绝不部署、热修复也不跳过)

### 7. campus-red-team (精华锻造)

**原始状态**: 3 攻击者角色 × 7 阶段 (侦察→认证攻击→业务逻辑→注入→基础设施→链条→报告)。本身已经很完整。

**精华注入**:
- +CONSTITUTION (安全约束: 绝不执行破坏性命令、不跳过"不可利用"文档、绕过 nginx 测应用层、不假设 Go 安全)
- +Attack Mindset 深化: 3 角色切换 + 链条原则 (2 个 Low = 1 个 High)

## 四、关键设计决策

### 决策 1: 精华 = 设计模式，不是功能合并

```
错误: 把 code-quality 的 4 阶段重构抄进 campus-code-review
正确: 提取"分级动作映射"模式，强化 campus 的 Step 2
```

保持 skill 边界清晰 (Unix: Do One Thing Well)，用交叉引用替代功能合并。

### 决策 2: Constitution 锚 — 每个 skill 的安全边界

```
CONSTITUTION (forge 不可编辑)
  - 核心功能
  - 安全约束 (绝对不能做的事)
  - 触发条件 (什么时候该用/不该用)

IMPLEMENTATION (forge 可以优化)
```

### 决策 3: 6 维评估替代 5 维 LLM judge

```
5a 确定性断言 (8 pts, 零噪声): test-prompts.json 的 assert 字段
5b 3-judge blind consensus (7 pts, 噪声 ±2): Agent 工具 spawn 独立 judge
```

LLM judge 准确率仅 46.4% (SkillLens)。确定性断言 + 3 judge 多数 → 噪声带从 ±5 缩到 ±2。

### 决策 4: 成长性 — v0.2 加入 DISCOVER + 使用追踪

```
forge 不只是优化器，是 skill 生态系统管理者:
  - EVOLVE: 优化现有 skill (bounded edit + validation gate)
  - DISCOVER: 从失败/重复劳动中发现新 skill (EvoSkill 模式)
  - TRACK: 使用追踪 → 数据驱动决策
  - RETIRE: 180 天未使用 → 提议退役
```

### 决策 5: Pantheon 7→2

pantheon-custom 和 pantheon-gap-custom 通过 `--verifier` 参数覆盖了所有模型组合。其余 5 个 (`pantheon`, `pantheon-x`, `pantheon-gap`, `pantheon-gap-x`, `pantheon-model`) 是冗余预设，已归档到 `_archived/`。

## 五、当前 Skill 清单

```
f:/ClaudeFiles/.claude/skills/
├── campus-code-review.md       (98.5)  代码审查 — 三级门控 + 半形式推理 + 收敛
├── campus-security-audit.md            安全审计 — 攻击者思维 + 8步流水线
├── campus-bug-hunt.md                  Bug排查 — 铁律 + 三源搜索 + Critic
├── campus-deploy.md                    部署 — defense-in-depth + pre-flight
├── campus-quality-gate.md             质量门 — 9道检查 + 多agent共识
├── campus-red-team.md                 红队 — 3角色 × 7阶段 + 链条原则
├── forge/                  (~99)  Skill优化 — 6维评估 + DISCOVER + 追踪
├── pantheon-custom/                   代码生成 — 任意模型验证
├── pantheon-gap-custom/              差距分析 — 9维度审查 + 任意模型确认
└── _archived/                         退役存档 (5 pantheon 变体)
```

## 六、给新对话的建议

读完后，你应该：

1. **先读 forge/SKILL.md** — 理解整个优化框架
2. **再读 campus-code-review.md** — 看最成功的优化案例 (59.5→98.5)
3. **跑一个快速测试** — 让 campus-code-review 审查一个文件，看实际效果
4. **检查 results.tsv** — 看完整的优化历史记录
5. **读 skill-usage.jsonl** — 看使用追踪数据

### 如果遇到问题

- forge 可以优化所有 7 个 skill (除了它自己的 CONSTITUTION 段)
- DISCOVER 层会在检测到重复劳动时提议创建新 skill
- 使用追踪数据在 `.claude/skills/forge/skill-usage.jsonl`
- 优化历史在 `.claude/skills/forge/results.tsv`

### 核心哲学

- **Constitution 不可编辑** — 安全边界由人类设定，永不妥协
- **Bounded edit (≤4 处)** — 小步快跑，每步验证
- **Execution-based validation** — 跑测试验证，不用 LLM 判分
- **Git ratchet** — 好了 commit，坏了 revert
- **Human in the loop** — 🔴 tier skill 必须人审
- **Less is more** — 7 个聚焦 skill > 187 个散装 skill

---

*这篇文档记录了 2026 年 6 月 21 日 12 小时的完整锻造过程。*
*每一个设计决策都有论文或实战数据支撑。*
*如果你是新对话的 Claude，请基于这些决策继续，不要推翻重建。*
