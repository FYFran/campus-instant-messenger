# 新对话指令

读 `f:/ClaudeFiles/.claude/pedia/seven-skills-origin.md` 了解背景。
读 `f:/ClaudeFiles/.claude/skills/skill-lab/SKILL.md` 了解锻造框架。
读 `f:/ClaudeFiles/.claude/skills/skill-lab/results.tsv` 看完整优化历史。

## 当前状态

| Skill | 分数 | 状态 |
|-------|------|------|
| campus-code-review | 98.5 | ✅ 顶级 |
| skill-lab | ~99 | ✅ 顶级 |
| 铁壁 | 98.5 | ✅ 顶级 |
| 火眼 | 97.5 | ✅ 顶级 |
| **缉凶** | **91.1→~93** | **🔄 锻造中** |
| pantheon-custom | 未评估 | ⏳ 待评估 |
| pantheon-gap-custom | 未评估 | ⏳ 待评估 |
| campus-deploy | 未评估 | ⏳ 待升级 |
| campus-quality-gate | 未评估 | ⏳ 待升级 |
| campus-red-team | 未评估 | ⏳ 待升级 |

## 本次目标

**1. 缉凶冲刺 99。** 当前 ~93，gap ~6 分。三 judge 盲评 median 8.4，要推高到 9.5+。

**2. 用缉凶锻造剩余 5 个 skill。** 缉凶的 Skill Text Audit（删除/替换/覆盖/一致四测试）查杀每个 skill → skill-lab 6维评估 → 循环到收敛。

## 缉凶已知问题（13个）

### Judge 明确指出的（3个）
1. **Skill Text Audit 未接入主流程** — 独立章节，无桥接。Phase 1 应判断"目标是skill文件→跳到 Skill Text Audit"
2. **Phase 5 "先写测试"缺框架指引** — `pytest`/`Hypothesis`/`go test`/`flutter test` 已补，但 Hypothesis setup 仍无具体说明
3. **PREFLIGHT 输出未被任何 Phase 消费** — 检测完能力但没用到。Phase 2a 应根据 `cap.rg` 选 TIER1/TIER2

### 结构性短板（5个）
4. **Phase 2 三者交织混乱** — 2a/2b/2c 有条件分支（T4→bisect），agent 可能迷失
5. **Phase 3d Property-Based Test 太薄** — 一行"推断不变量→写Hypothesis测试"。agent 不会。需要写 Hypothesis strategies 选择指南
6. **Skill Text Audit 引用了不存在的 test-prompts** — 大部分 skill 没有 test-prompts.json。需要处理"test-prompts 不存在"的情况
7. **Gotchas 27行含非Gotcha行** — 正则把 Skill Text Audit 表也抓进来了，视觉上 Gotcha 表尾部应更清晰
8. **Phase 5 Critic "换角度重跑" 无枚举角度** — 虽然原版 Phase 5 写了"崩溃/简化/安全/边界/竞态"五个角度，但 judge 说不够明确

### 边界盲区（3个）
9. **Docker/CI/k8s 环境 bug 无覆盖** — T6 只到"容器→docker inspect"，缺 Dockerfile/CI log/k8s pod 诊断
10. **依赖版本冲突 bug 无覆盖** — `pip freeze` diff 有了，但无"哪个版本引入了bug"的 bisect
11. **MCP 工具交互 bug 无覆盖** — Agent 工具链本身的故障模式

### 执行性缺口（2个）
12. **无 worked example** — 最好加一个完整案例（如 main_remote:222）
13. **Growability 纯手工** — CHECKPOINT 说未记录→BLOCK，但无自动化脚本

## 缉凶冲刺 99 的路径

按边际收益排序：

| # | 改什么 | 预期提分 | 难度 |
|---|--------|---------|------|
| 1 | Phase 3d 补 Hypothesis strategies 选择指南 | +0.5 | 中 |
| 2 | PREFLIGHT 输出接入 Phase 2a TIER 选择 | +0.5 | 易 |
| 3 | Phase 5 Critic 枚举 5 个角度 | +0.3 | 易 |
| 4 | Phase 2 三者重排：2a 搜索→2b bisect→2c 证据 | +0.3 | 易 |
| 5 | Skill Text Audit 处理"无test-prompts" → Phase 0.5 自动生成 | +0.5 | 中 |
| 6 | Phase 1 加"目标=skill→Skill Text Audit"桥接 | +0.3 | 易 |
| 7 | 补 1 个 worked example | +0.3 | 中 |
| 8 | T6 扩 Docker/CI log/k8s pod 诊断 | +0.3 | 中 |
| 9 | Growability 写 extract_pattern.py 脚本 | +0.5 | 难 |
| 10 | 依赖版本 bisect (git bisect 的 pip 版) | +0.2 | 易 |

理论天花板：补 1-6 → 95-96。再补 7-10 → 97-98。三 judge blind 没跑过 9.5。
**99 需要三 judge 全给 9.5+，很难但不是不可能。**

## 剩余 skill 锻造计划

用缉凶 + skill-lab 双管齐下：

```
缉凶 Skill Text Audit → 找缝 → skill-lab Phase 1 基线 → Phase 2 优化 → 循环到收敛
```

| 优先级 | Skill | 预估起点 | 目标 |
|--------|-------|---------|------|
| 1 | campus-deploy | ~65-70 | 95+ |
| 2 | campus-quality-gate | ~60-65 | 95+ |
| 3 | campus-red-team | ~65-70 | 95+ |
| 4 | pantheon-custom | ~70-75 | 95+ |
| 5 | pantheon-gap-custom | ~70-75 | 95+ |

## 核心哲学（继承）

- **执行型 > 思考型** — 教 agent 跑命令，不教方法论
- **填空模板 = 强制执行** — 每 Phase 产出给下 Phase，跳步=链断
- **双端 Iron Law** — 头尾各放一次，U 型注意力
- **删除测试** — 删一行输出不变=冗余，砍
- **不编造** — 自评分不算数，只信 3-judge blind consensus
- **Bounded edit** — 每轮 ≤4 处修改

## 交付物

- 缉凶 ≥95（冲刺99）
- 5 个 skill 全部 ≥95
- results.tsv 完整记录
- 每个 skill 的 test-prompts.json
