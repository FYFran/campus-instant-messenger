# BugHuntBench v2.0 评分框架

> 对标 SWE-bench test-pass + 2026 Agent 6-Dimension Rubric。
> 三层管线: L1 规则(零token) → L2 LLM Judge → L3 Cross-Model Verify。

## 执行流程

```
1. Bug Factory 注入 bug → 代码库
2. Harness spawn 独立 agent（盲测，无 ground truth）
3. Agent 用目标 skill 排查 → 输出 bug report + 轨迹 JSONL
4. Auto Scorer 评分（7维 + L3防骗）
5. CI Gate 判定 PASS/FAIL
6. Leaderboard 更新
```

## 7 维评分（满分 8）

| # | 维度 | 分值 | 判据 | 评分方式 |
|---|------|------|------|---------|
| 1 | **分类正确** | 1 | T-Type 与 ground truth 一致 | 规则 |
| 2 | **链完整** | 1 | 7 步产出非空（或 T7/emergency 正确缩短） | 规则 |
| 3 | **证据充分** | 1 | 复现步骤 + baseline 可验证 | LLM Judge |
| 4 | **根因正确** | 2 | 与 truth 一致（含 file:line）。部分正确=1 | LLM Judge |
| 5 | **CF 真实** | 1 | 有可验证 pre/post 证据（非模板文本） | LLM Judge |
| 6 | **修复正确** | 1 | 消除根因 + 不引入新问题 | 执行验证 |
| 7 | **轨迹合规** | 1 | 无 gate 跳过，无红线违反 | 规则 |

## L3 防骗标注（不参与分数）

| 标注 | 含义 | 对分数的解读 |
|------|------|-------------|
| **REAL** | 全维度独立验证通过 | 分数可信 |
| **REAL\*** | 分析框架正确，次要偏差 | 分数基本可信 |
| **TEMPLATE** | 格式正确但内容空洞 | **分数虚高** |
| **WRONG** | 发现事实错误 | **分数无意义** |
| **NOT RUN** | L3 本轮未执行 | 分数待验证 |

## 自动判分规则

### 维度 1: 分类（规则，零 token）

```
提取 agent 输出的 "Type: T___" → 与 ground truth T-Type 比较
- 完全匹配 → 1
- T7 对应 NOT_A_BUG → 1
- 不匹配 → 0
```

### 维度 2: 链完整（规则，零 token）

```
检查 7 个合同步是否都有非空产出:
  分类 | 证据 | 追踪 | 分析 | 修复 | 验证 | 记录
- 全部非空 → 1
- 缺 ≥1 步 → 0
```

### 维度 3: 证据（LLM Judge）

```
Judge prompt: "证据包含具体复现步骤吗？有可验证的 baseline 输出吗？"
- 1: 具体复现步骤 + 可验证 baseline（如 curl + 响应）
- 0: 笼统描述或无 baseline
```

### 维度 4: 根因（LLM Judge，0-2分）

```
Judge prompt: "根因是否与 ground truth 一致？file:line 匹配吗？"
- 2: 根因一致，file:line 匹配，因果链完整
- 1: 方向对但细节偏差
- 0: 根因错误
```

### 维度 5: CF（LLM Judge）

```
Judge prompt: "CF 有 pre/post 可验证证据吗？还是模板文字？"
- 1: 具体 pre/post 对比数据
- 0: 声明性语句（如"修后 OK"）
```

### 维度 6: 修复（执行验证）

```
Apply diff → run regression test
- 测试 PASS + 无回归 → 1
- 测试 FAIL 或引入新问题 → 0
```

### 维度 7: 轨迹（规则）

```
解析轨迹 JSONL → 检查:
- 无 gate 跳过
- 无红线违反（不复现不修/不CF不提交/不测试不修/3次失败STOP/修前确认部署文件）
- 全部合规 → 1
- ≥1 违反 → 0
```

## 三层管线

| 层级 | 触发 | 评分方式 | 成本 | 时间 |
|------|------|---------|------|------|
| **L1 Quick** | 每次 commit | 规则 (维度 1,2,7) | 0 token | <1s |
| **L2 Full** | 每晚 | 规则 + LLM Judge (全维度) | ~50K/bug | ~2min |
| **L3 Verify** | 每周/PR前 | Full + 3-judge cross-model | ~300K/bug | ~5min |

## CI 门禁阈值

| 指标 | Quick | Full | Verify |
|------|-------|------|--------|
| T-Type 正确率 | ≥60% | ≥70% | ≥80% |
| 链完整率 | ≥90% | ≥95% | 100% |
| 平均分 | ≥4/8 | ≥5/8 | ≥6/8 |
| 根因命中率 | — | ≥50% | ≥70% |
| L3 TEMPLATE | — | ≤2 | 0 |
| L3 WRONG | 0 | — | — |

## 汇总

```
总分 = Σ(bug得分) / (bug数 × 8) × 100

速率指标:
  T-Type 覆盖率 = 分类正确的 bug 类型数 / 8
  链完整率 = 产出链完整的 bug 数 / 总数
  根因命中率 = 根因正确的 bug 数 / 总数
  CF 真实率 = CF 有证据的 bug 数 / 总数
```

## Judge 设计原则

| 原则 | 做法 |
|------|------|
| 跨模型家族 | Judge 必须不同于 worker model |
| 3-judge consensus | 多数投票，全分歧→标记 SUSPECT |
| Per-dimension | 每个维度独立 judge prompt |
| 证据引用 | Judge 必须引用 file:line |
| 置信度加权 | 低置信(<50%) judge 降权 0.5 |
