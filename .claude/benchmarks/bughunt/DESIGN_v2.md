# BugHuntBench v2.0 — 设计蓝图

> 对标 SWE-bench + Agent-as-Judge + AdaRubric + Human-on-the-Bridge。
> 不只是一个 benchmark——是 skill 质量的 CI/CD 管线。

---

## 一、核心架构

```
┌─────────────────────────────────────────────────┐
│                BugHuntBench v2.0                 │
├─────────────────────────────────────────────────┤
│  1. Bug 工厂    →  bug 生产 + 注入 + 验证        │
│  2. Harness     →  自动 spawn agent + 轨迹捕获   │
│  3. Scorer      →  7维自动评分 + 交叉 judge     │
│  4. Leaderboard →  多 skill 多模型 排行榜        │
│  5. CI Gate     →  PR 门禁 + 回归保护            │
└─────────────────────────────────────────────────┘
```

### 工作原理

```
Bug Factory 注入 bug → Harness spawn agent(缉凶) → 轨迹捕获
→ Scorer 自动评分(7维) → Leaderboard 更新 → CI Gate 判定
```

---

## 二、评分体系（7 维 + L3 防骗）

对标 SWE-bench 的 test-pass 验证 + 6-dimension agent rubric。

### 维度定义

| # | 维度 | 分值 | 判据 | 自动化方式 |
|---|------|------|------|-----------|
| 1 | **分类正确** | 1 | T-Type 与 ground truth 一致 | 字符串匹配 T0-T7 vs truth |
| 2 | **链完整** | 1 | 7步产出非空 | 正则检查每步产出字段 |
| 3 | **证据充分** | 1 | 复现步骤 + baseline 可验证 | LLM judge 检查证据具体性 |
| 4 | **根因正确** | 2 | file:line 匹配 + 因果链正确 | Agent-as-Judge vs truth |
| 5 | **CF 真实** | 1 | pre/post 证据非模板 | LLM judge 检查 pre/post 对比 |
| 6 | **修复正确** | 1 | 消除根因不引入新问题 | 自动跑回归测试 |
| 7 | **轨迹合规** | 1 | 无 gate 跳过，无红线违反 | 轨迹解析 + 规则检查 |
| **总分** | — | **8** | — | — |

### L3 防骗标注（不参与分数，随报告）

| 标注 | 含义 |
|------|------|
| REAL | 全维度独立验证通过 |
| REAL* | 主分析正确，次要偏差 |
| TEMPLATE | 格式正确但内容空洞 |
| WRONG | 事实错误 |

---

## 三、三层评估管线

对标 2026 共识的 3-framework hybrid 模式：

### Layer 1: CI Fast (每次 commit, <30s)
```
- 结构完整性 (链完整)
- T-Type 格式正确
- 轨迹可解析
```
**成本:** ~0 tokens (纯规则)

### Layer 2: Nightly Regression (每晚, ~10min)
```
- 全部 7 维评分
- 1 judge per dimension (快速模式)
- 与 baseline 对比
```
**成本:** ~50K tokens/bug

### Layer 3: Adversarial Verify (每周/PR前, ~1h)
```
- 3 judge cross-family consensus
- L3 spot-check
- 注入新 bug 验证无回归
- Mutation testing (对 skill 注入缺陷)
```
**成本:** ~300K tokens/bug

---

## 四、Bug 工厂

SWE-bench 的核心资产：**高质量、人审过的 bug 实例**。

### Bug 生产流水线

```
[真实 bug] → [提取→脱敏→泛化] → [人审] → [注入验证] → [加入数据集]

来源:
1. campus_go git history (真实修过的 bug)
2. 生产事故报告 (.fixes/ 目录)
3. 注入的新 bug (注入→确认 agent 能发现→回滚)
4. AI 生成 + 人审 (LLM 生成候选 bug → 人确认可行性)
```

### Bug 元数据格式

```json
{
  "id": "B11",
  "type": "T1",
  "language": "Go",
  "difficulty": "medium",
  "source": "production-2026-06-15",
  "description": "用户视角描述...",
  "ground_truth": {
    "root_cause": "file:line + 因果链",
    "fix": "正确 diff",
    "classification": "T1",
    "scoring_rubric": {
      "classification": "T1",
      "evidence_required": ["并发测试复现", "时序分析"],
      "root_cause_match": "SELECT+INSERT 窗口期 + 缺锁",
      "cf_required": "加 FOR UPDATE → 不重复",
      "fix_match": "FOR UPDATE + ON CONFLICT + UNIQUE"
    }
  },
  "injection": {
    "method": "revert-commit",
    "commit_to_revert": "abc123",
    "files_affected": ["activities.go"]
  },
  "verification": {
    "test_to_run": "TestSignupConcurrent",
    "expected_failure": "DUPLICATE DETECTED",
    "expected_pass_after_fix": "PASS"
  }
}
```

---

## 五、自动评分引擎

### 评分流程

```
1. Agent 执行排查 → 输出 bug_report.md + 轨迹 JSONL
2. 轨迹解析器: 检查 gate 跳过、红线违反 → 维度 2,7 (规则)
3. T-Type 匹配: 正则提取 "Type: T___" → 维度 1 (规则)
4. Agent-as-Judge: 
   - 维度 3 (证据): "证据包含具体复现步骤吗？有可验证的 baseline 输出吗？"
   - 维度 4 (根因): "根因是否与 ground truth 一致？file:line 匹配吗？"
   - 维度 5 (CF): "CF 有 pre/post 可验证证据吗？还是模板文字？"
5. 修复验证: apply diff → run regression test → 维度 6 (自动)
6. 汇总: 总分 + L3 标注
```

### Judge 设计原则（来自 2026 研究）

| 原则 | 做法 |
|------|------|
| 跨模型家族 | Judge 必须不同于 worker model |
| 3-judge consensus | 多数投票，全分歧→标记 SUSPECT |
| Per-dimension | 每个维度独立 judge prompt |
| 证据引用 | Judge 必须引用 file:line |
| 置信度加权 | 低置信 judge 降权 |

### Judge Prompt 模板

```
你是独立评分 agent。对照 ground truth 评估以下 bug report 的【维度 4: 根因正确性】。

Ground Truth 根因: {truth_root_cause}
Agent 根因: {agent_root_cause}
Agent 证据: {agent_evidence}

评分标准:
- 2: 根因与 truth 一致，file:line 匹配，因果链正确
- 1: 方向对但细节偏差（如正确的函数但错误的行号）
- 0: 根因错误或完全不同

返回: {"score": 0|1|2, "confidence": 0-100, "reasoning": "一句话", "evidence_ref": "file:line"}
```

---

## 六、Harness（执行引擎）

### 架构

```python
# bughunt_harness.py
class BugHuntHarness:
    def run_benchmark(
        self,
        bugs: List[str],        # bug IDs
        skill: str,             # "缉凶" or other skill
        model: str,             # model to use
        mode: str = "full"      # full | quick | verify
    ) -> BenchmarkResult:
        """
        1. For each bug:
           a. Inject bug into codebase (if injection method)
           b. Spawn agent with bug description + skill
           c. Capture trajectory (all tool calls + outputs)
           d. Collect agent's bug report
           e. Revert bug injection
        2. For each bug report:
           a. Parse trajectory → dimensions 2,7 (rule-based)
           b. Match T-Type → dimension 1 (rule-based)
           c. Agent-as-Judge → dimensions 3,4,5 (LLM)
           d. Apply fix + run tests → dimension 6 (automated)
        3. Aggregate scores + L3 spot-check
        4. Update results.tsv + leaderboard
        """
```

### 轨迹捕获

```jsonl
{"step": "classification", "output": "Type: T1 依据: 每20-30次出现一次", "tool": "none", "ts": "..."}
{"step": "evidence", "output": "复现步骤: ...", "tool": "codegraph_context", "ts": "..."}
{"step": "trace", "output": "调用链: Signup→SELECT→INSERT", "tool": "codegraph_trace", "ts": "..."}
```

---

## 七、Leaderboard

### 排行榜维度

| 维度 | 说明 |
|------|------|
| **总分** | 加权总分 (满分 80) |
| **T-Type 覆盖率** | 正确分类的 bug 类型 / 8 |
| **根因命中率** | 根因正确的 bug / 总数 |
| **链完整率** | 合同链完整的 bug / 总数 |
| **L3 REAL 率** | REAL/REAL* / 总 L3 spot-check |

### 排行榜项

```
Rank  Skill     Model        Score  T-Cov  Root%  Chain%  L3
1     缉凶 v2.0  deepseek-v4  75.7   7/8    5/10   10/10   REAL*(7/10)
2     缉凶 v2.0  claude-opus4  XX.X   ...    ...    ...     ...
3     铁壁 v2.0  deepseek-v4   XX.X   ...    ...    ...     ...
```

### 多 Skill 对比

BugHuntBench 不只为缉凶设计。任何 debug skill 都可以跑：
- 缉凶: 合同框架
- 裸 agent: 无 skill
- SWE-agent: 通用 SWE skill
- 自定义 skill: 任何 .md 文件

---

## 八、CI 集成

### PR 门禁

```yaml
# .github/workflows/bughunt-gate.yml
bughunt-gate:
  steps:
    - run: bughunt_harness.py --mode quick --bugs all
    - assert: "total_score >= baseline_score"
    - assert: "root_cause_accuracy >= 0.5"
    - assert: "no L3 WRONG"
```

### 回归保护

```yaml
# 每周或每次 skill 重大改动后
bughunt-regression:
  steps:
    - run: bughunt_harness.py --mode full --bugs all
    - assert: "total_score >= baseline_score - 5%"
```

---

## 九、实现路线图

### Phase 1: Harness (1-2天)
- [ ] `bughunt_harness.py` — 自动 spawn agent + 收集输出
- [ ] 轨迹解析器 — 从 agent 输出提取 7 步
- [ ] 规则评分器 — 维度 1,2,7 (零 token 成本)

### Phase 2: Judge (1-2天)
- [ ] Agent-as-Judge 评分器 — 维度 3,4,5
- [ ] Cross-model judge 支持
- [ ] 3-judge consensus + 置信度加权

### Phase 3: 自动化 (1天)
- [ ] CI 集成 (GitHub Actions)
- [ ] results.tsv 自动更新
- [ ] Leaderboard 生成 (markdown)

### Phase 4: 扩展 (1-2天)
- [ ] Bug 工厂 (bug 生产流水线)
- [ ] 多 skill 支持
- [ ] 多 model 对比

### Phase 5: 公开 (1天)
- [ ] README + 使用文档
- [ ] 公开 leaderboard
- [ ] 社区贡献指南

---

## 十、2026 大佬智慧（设计依据）

### SWE-bench (Princeton/OpenAI)
- **3 人独立审核**每个 bug 确保质量
- **私有测试集**防作弊（只公开 bug 描述，不公开 ground truth）
- **test-pass 验证**为最终判定（不是 LLM judge）
- **弃用 SWE-bench Verified** → SWE-bench Pro（更长 horizon，更多步骤）

### Agent Evaluation 6-Dimension Rubric (2026 consensus)
- **Tool Selection** / **Argument Extraction** / **Result Utilization**
- **Error Recovery** / **Plan Coherence** / **Task Completion**
- **关键洞察**: 端到端成功率 ≈ 每步成功率的乘积。8 步各 95% → 66% 端到端

### AdaRubric (ACL 2026)
- 任务自适应 rubric: 从任务描述自动生成评分标准
- Pearson r=0.79 与人相关（比基线 +0.15）
- DPO 训练后下游任务提升 6.8-8.5%

### Human-on-the-Bridge (2026)
- 人类设置陷阱 (red-team traps)、评审角色、评分指南
- 小 LLM 可以有效 judge 前沿模型 agent
- 多轮对抗评估 harness

### AgentBeats (2026)
- 标准 A2A + MCP 协议做 agent-vs-agent 评估
- 298 judge agent × 467 subject agent，5 个月公开竞赛

### Amazon Production Framework
- 三层评估: foundation model → component → final response
- 从历史 API 日志合成 golden dataset
- 覆盖率: 工具选择准确度 + 意图检测 + 故障恢复

### LLM-as-Judge 7 Best Practices (Monte Carlo AI)
- 1. 始终提供参考示例
- 2. 使用成对比较而非单输出评分
- 3. 控制位置偏差（交换顺序）
- 4. 允许 judge 说"我不知道"
- 5. 使用 chain-of-thought 推理
- 6. 独立评分每个维度
- 7. 定期校准 vs 人类标注

---

## 十一、BugHuntBench 独有优势

对比现有 benchmark:

| 特性 | SWE-bench | τ-bench | BugHuntBench v2.0 |
|------|-----------|---------|-------------------|
| 测什么 | 模型代码能力 | 工具调用 | **Skill 质量 + Agent 执行** |
| 评分 | test-pass | task-complete | **7维 + L3防骗 + 轨迹审计** |
| 自动化 | ✅ | ✅ | ✅ |
| 防作弊 | 私有集 | 公开 | **L3 spot-check (独立agent盲测)** |
| 多 skill | ❌ | ❌ | **✅ (缉凶/铁壁/火眼/任意skill)** |
| 多模型 | ✅ | ✅ | **✅ + cross-family judging** |
| CI集成 | ✅ | ✅ | **✅ 3层管线 (fast/nightly/adversarial)** |
| 可成长 | ❌ | ❌ | **✅ Bug Factory + Mutation-to-Lint** |
