---
name: 火眼
description: 火眼（Fire Eye）— 项目差距分析引擎。PreScan→Map→Probe→Confirm→Synthesize→Critic→Write。跨模型对抗验证。零依赖降级：无Workflow则单agent模式仍可用。触发：火眼/gap analysis/差距分析/find gaps/confirm gaps/项目审查。
---

# 火眼 — 项目差距分析引擎

## CONSTITUTION（不可被 skill-lab 编辑）

**核心功能：** 代码库差距分析 → P0-P3优先级报告。7-Phase pipeline：PreScan（静态grep）→ Map（侦察选维度）→ Probe（找gap+证据）→ Confirm（跨模型steelman验证）→ Synthesize（去重排序）→ Critic（自检报告）→ Write（产物持久化）。
**安全约束：** 绝不编造gap（每finding需file:line证据）。绝不写入被审查repo。绝不在聊天中暴露API key。外部模型不可用→标记unconfirmed，不静默跳过。
**触发：** 火眼 / gap analysis / find gaps / 差距分析 / confirm gaps / project review / 项目审查

---

## PREFLIGHT（每次必跑）

```
1. 检查 ~/.pantheon/ 目录是否存在 → 不存在则 "New-Item -ItemType Directory -Force ~/.pantheon/"
2. 检查 ~/.pantheon/config.json → 不存在则创建 {"verifier":"claude"}
3. 检查 Workflow 工具是否可用 → 可用则 MODE=engine(7-phase)。不可用则 MODE=single(agent模式)
```

MODE=single 时：agent 直接执行 PreScan+Map+Probe 三步（无并行验证、无 Critic、无 Write），仍产出结构化报告。

---

## Procedure

**1.** 🔴 解析确认模型。内联模型名 → 直接使用。读 `~/.pantheon/config.json` → 取 `verifier ?? defaultVerifier`。无配置 → BLOCK，引导用户运行 `/pantheon-model` 或同意 Claude default。
格式：`provider/model-id` 或别名（deepseek/qwen/kimi/ollama:model/profile:name）。
Claude-tier（opus/sonnet/haiku）通过 `agent({model})` 切换。

**2.** 🔴 检查确认模型可用性。不可用 → 标记 unconfirmed 但继续。绝不静默替换为 Claude。

**3.** 🔴 确定目标路径。无路径 → BLOCK，追问。路径不存在 → BLOCK。必须是绝对路径。

**4.** 决定参数：target（绝对路径）、focus（可选重点维度）、maxDimensions（默认 6）、verifiers（默认 2）、verifier（确认模型）。

**5.** 🔴 Pre-Workflow Gate：确认 target/maxDimensions/verifier/预期成本后启动。

**6.** MODE=engine：读 `pantheon-gap-class.js` → `Workflow({script, args})` → 等完成 → 按 Output Spec 格式输出。
MODE=single：agent 直接执行 PreScan（Select-String grep）+ Map（读 README/结构）+ Probe（每维度手动检查）→ 按 Output Spec 格式输出。

**7.** 报告含：确认模型、Passes、Lenses覆盖、Confirmed Gaps（P0-P3+Evidence+Confidence+Fix）、SUSPECT Gaps（conf<0.8）、Quick Wins、Highest-Leverage Fix。标注模式（engine/single）。

---

## Output Specification

```markdown
## Gap Analysis: {target} — {timestamp}
**Confirm model:** {model} | **Passes:** N | **Lenses:** [lenses] | **Mode:** {engine/single}

### Summary
{一段话项目状态评估}

### Confirmed Gaps ({n})
| # | P | Dimension | Gap | Evidence | Confidence | Fix |
|---|----|-----------|-----|----------|------------|-----|
| 1 | P0 | security | ... | file:line | 0.95 | ... |

### SUSPECT Gaps ({n}) — avg confidence <0.8, treat as suggestions
| # | Dimension | Gap | Confidence | Why SUSPECT |

### Quick Wins
- [ ] {低成本高价值修复}

### Highest-Leverage Fix
**{title}** — {为什么这是最该先修的}
```

---

## 分级执行

| 模式 | 触发 | 行为 |
|------|------|------|
| **full** | 默认 | 7-Phase 引擎（需Workflow），跨模型验证，convergence re-probe |
| **quick** | `quick gap scan` | 3维度 + 跳过确认（⚠ UNCONFIRMED，仅用于快速摸底） |
| **safe** | `safe gap scan` | 7-Phase 但强制 Claude-tier 确认（⚠ 同模型家族，非真实跨模型独立） |

---

## Pipeline（MODE=engine 时 JS 执行）

- **PreScan:** 静态 grep（Select-String/rg）：TODO/FIXME/空catch/硬编码密钥 → 种子证据
- **Map:** 侦察项目结构选最相关维度（默认 6 维）
- **Probe:** 每维度一个 agent 找 gap（3-8个高信号 gap，维度扎实则返回空）
- **Confirm:** V 个 skeptic（各不同 lens: correctness/security/performance/completeness/architecture）先 steelman 再反驳，多数确认则保留。弱理由（空 steelman 或无 code reference）→ 降权 0.5。avg confidence <0.8 → SUSPECT
- **Synthesize:** 去重 + P0-P3 优先级排序
- **Critic:** 自检报告（证据/hedging/重复/置信度/修复方案），blocking issues → auto-fix ≤2次
- **Write:** Python3 跨平台写入 `.gaps/{scope}-{timestamp}.json`

**收敛：** CRITICAL gap 触发互补维度 re-probe（security↔correctness, performance↔architecture, testing↔completeness），最多 3 轮。

**上报：** 外部模型不可用 → 标记 unconfirmed。JSON 解析失败 → valid:true, reason:"parse error — gap kept"。

---

## Gotchas（真实踩坑）

| # | 坑 | 正确做法 |
|---|-----|---------|
| 1 | codex exec exit 0 但 output 为空 JSON | 检查 output 非空 + 含 `valid` 字段。空 → unconfirmed |
| 2 | pipeline 并行竞态 | confirm 阶段 `--sandbox read-only`，绝不加 `--sandbox none` |
| 3 | DeepSeek 返回中文 JSON key | VERDICT_SCHEMA 强制验证，解析失败 → gap kept |
| 4 | 大项目 probe 超时 | maxDimensions 默认 6，大项目降到 4 |
| 5 | verifier 全票否决但全是弱理由 | steelman 空或 reason 无 codeReference → 降权 0.5 |
| 6 | config.json schema 变更 | 读取时兼容 `verifier ?? defaultVerifier ?? 'claude'` |
| 7 | 单 dimension 扫描当全面报告 | 标注 "Partial — {n}/{total} dimensions probed" |

## Report Artifacts

产物写入 `{target}/.gaps/{scope}-{timestamp}.json`。同 gap 连续 2 次出现 → severity +1 升级。保留 20 个文件，删 >90 天。
