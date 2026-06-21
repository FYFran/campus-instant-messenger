---
name: pantheon-gap-custom
description: >-
  A skill that runs a GAP ANALYSIS & feedback review of an existing project through a multi-agent
  harness (configurable variant: the user PICKS which AI model runs the adversarial confirm step —
  including non-Anthropic models like DeepSeek, Qwen, Kimi, or a local Ollama/LM Studio model). Same
  map → probe (one agent per dimension finds gaps with file-level evidence) → adversarial confirm →
  synthesize pipeline as the pantheon-gap base, but the confirm/skeptic model is chosen per run via a
  `verifier` argument and external/local models are driven through the `codex` CLI (a multi-provider
  router). Use when the user says "pantheon gap custom", "confirm gaps with deepseek/qwen", "review my
  project with a local model", "갭 분석 모델 골라서", "딥시크로 갭 확인", "큐원으로 프로젝트 점검",
  "오픈클로처럼 리뷰 모델 선택". If no model is given it defaults to Claude (same as the pantheon-gap
  base). For the fixed presets use pantheon-gap (Claude) / pantheon-gap-x (GPT-5.5). For GENERATING code
  rather than reviewing, use pantheon-custom. Don't use for a quick single-file glance (cost is high).
---

# Pantheon gap-analysis harness (configurable · user-selectable confirm model)

## CONSTITUTION（本段不可被 skill-lab 编辑）

### 核心功能
- 项目差距分析：map（侦察项目选维度）→ probe（每维度找 gap+证据）→ adversarial confirm（选定模型反驳）→ synthesize（去重排序出报告）
- 用户可选 confirm 模型：Claude tier / DeepSeek / Qwen / Kimi / Ollama 本地 / codex profile

### 安全约束
- 绝不编造 gap（每个 finding 必须有 file:line 证据）
- 绝不写入被审查的 repo（confirm 只读）
- 绝不在聊天中暴露 API key（用 `~/.pantheon/env` 文件）
- 外部模型不可用时绝不静默跳过（标记 "unconfirmed"）
- confirm 步骤必须由指定外部模型判定，Claude 只传输 verdict

### 触发条件
- 用户说：pantheon gap custom、confirm gaps with deepseek/qwen、review my project with local model、갭 분석 모델 골라서、딥시크로 갭 확인、큐원으로 프로젝트 점검
- 不触发：单文件快速检查（成本高）、写代码（用 pantheon-custom）

---

## 反例黑名单（每轮执行前必查 — 最高信号内容）

| # | 反模式 | 为什么不要做 | 替代做法 |
|---|--------|-------------|---------|
| 1 | **跳过 confirm 直接报** | 没有 adversarial review 的 gap 含大量误报 | 每个 gap 必须经 V 个 skeptic 确认 |
| 2 | **外部模型挂了静默用 Claude 替** | 丢失跨模型独立性，回到 same-model bias | 标记 "unconfirmed — external model unavailable" |
| 3 | **编造 file:line 证据** | 假证据比没证据更危险 | evidence 必须来自实际读到的代码 |
| 4 | **Confirm 模型不检查可用性** | codex 未装/key 未设/model 未 pull → 浪费一轮 pipeline | Step 2 先 sanity-check |
| 5 | **不改 config 每次手动指定** | 重复劳动，容易打错模型名 | 用 `/pantheon-model` 设默认 |
| 6 | **单 dimension 扫描当全面报告** | gap scan 覆盖度取决于 dimension 选择 | 标注 "Partial — {n}/{total} dimensions probed" |

---

## Quick Reference（速查）

| 想做什么 | 怎么做 |
|---------|--------|
| 项目差距分析（默认 Claude confirm） | `pantheon gap custom {path}` → map→probe→confirm→synthesize |
| 用 DeepSeek 确认 gap | `pantheon gap custom verify with deepseek {path}` |
| 用 Qwen 确认 gap | `pantheon gap custom verify with qwen {path}` |
| 用本地模型确认 | `pantheon gap custom verify with ollama/qwen2.5 {path}` |
| 快速扫描（3维+跳确认） | `quick gap scan {path}` → maxDimensions=3, skip confirm |
| 只看特定维度 | `pantheon gap custom {path} focus on security` |
| 配置默认模型 | `/pantheon-model` → 选模型+设 key |
| 规则速查 | 4-Phase pipeline · 6维默认 · 2 verifier · >50% majority confirm · external unavailable→KEPT unconfirmed · 🔴 confirm 前人审 |

## 分级执行

| 模式 | 触发 | 行为 |
|------|------|------|
| **full** | `pantheon gap custom {path}` (默认) | map→probe(6 dim)→confirm(2 verifier)→synthesize，完整 pipeline |
| **quick** | `quick gap scan {path}` | map→probe(3 dim)→skip confirm→synthesize，1 pass |
| **safe** | `safe gap scan {path}` | full pipeline 但 confirm 只用 Claude（不调外部模型） |

## Gap Priority Framework（P0-P3）

| Priority | Criteria | Examples | Requires |
|----------|----------|----------|----------|
| 🔴 **P0 — BLOCKING** | Core missing: auth bypass, data loss, security hole, missing critical feature | No auth on admin endpoint, SQL injection, unsigned tokens | 2+ verifier confirm + file:line evidence mandatory |
| 🟠 **P1 — HIGH** | Important incomplete: rate limiting, input validation, error handling, race condition | Missing rate limit on login, no input sanitization, bare except:pass | 1+ verifier confirm + evidence |
| 🟡 **P2 — MEDIUM** | Quality gap: missing tests, undocumented API, code duplication, missing logging | No test coverage on new handler, SELECT *, missing docstring | Evidence recommended |
| 🔵 **P3 — LOW** | Enhancement: performance optimization, UX polish, refactor opportunity, dependency update | N+1 query, outdated dep, inconsistent naming | Brief note sufficient |

**Confidence scoring:** Every gap gets a 0.0–1.0 confidence score. <0.8 → mark `SUSPECT`, don't block. ≥0.8 + majority confirm → confirmed gap.

---

User picks confirm model per run via `verifier` arg. External models driven through `codex exec` (multi-provider router); Claude only transports verdict. Confirm step is read-only. Set default with `/pantheon-model` (saves `~/.pantheon/config.json`). Formats: `provider/model-id` or alias:

| `verifier` value | adversarial confirm runs on | setup needed |
|------------------|-----------------------------|--------------|
| omitted / `claude` | Claude (session model) — same as the base | none |
| `opus` / `sonnet` / `haiku` / `fable` | that Claude tier | none |
| `codex` / `gpt` | GPT-5.5, via the Codex **plugin** (`codex:codex-rescue`) | Codex plugin |
| `deepseek` | DeepSeek (`deepseek-chat`) | `codex` CLI + `DEEPSEEK_API_KEY` |
| `qwen` | Qwen2.5-Coder via OpenRouter | `codex` CLI + `OPENROUTER_API_KEY` |
| `kimi` | Kimi / Moonshot | `codex` CLI + `MOONSHOT_API_KEY` |
| `ollama:<model>` / `lmstudio:<model>` | a **local** model (e.g. `ollama:qwen2.5-coder`) | `codex` CLI + Ollama/LM Studio running, model pulled |
| `profile:<name>` | a profile from your `~/.codex/config.toml` (any provider) | `codex` CLI + that profile |
| `model:<name>` or a bare model id | that codex model id | `codex` CLI configured for it |

## Requirements
- **Workflow orchestration** — a paid plan (Pro/Max/Team/Enterprise, v2.1.154+); on Pro enable
  `/config` → Dynamic workflows. Same as `pantheon-gap`. Not on the Free tier.
- **Claude-tier verifiers (`opus`/`sonnet`/`haiku`/`fable`) need nothing extra.**
- **External / local verifiers need the `codex` CLI on PATH** — it's the router this skill drives via
  `codex exec`. Note this is the codex **binary**, *not* the Codex plugin: the plugin
  (`codex:codex-rescue`) is only needed for `verifier: codex`/`gpt`. Per choice:
  - `deepseek` / `qwen` / `kimi` → the matching API-key env var must be set (`DEEPSEEK_API_KEY`,
    `OPENROUTER_API_KEY`, `MOONSHOT_API_KEY`).
  - `ollama:` / `lmstudio:` → that local server running with the model pulled (no API key, fully local).
  - `profile:` / bare model id → the provider/model defined in `~/.codex/config.toml`.
- **If the chosen verifier can't actually run** (codex missing, key unset, model unreachable), the
  driver KEEPS the gap tagged "external verifier unavailable — unconfirmed" rather than silently
  dropping it; treat such a report as not really cross-checked. Check availability first (step 2); if
  you can't, fall back to the `pantheon-gap` base or a Claude tier.

## When to use
- A real project/repo you want an evidence-backed, cross-checked gap list for — before a launch, after
  an MVP, inheriting a codebase — where you want a specific model to filter the findings (a cross-vendor
  model to strip same-model confirmation bias hardest, a free local model to save cost, or a Claude tier).
- Don't use it to *write* code — that's `pantheon-custom`. Don't use it for a trivial one-file look.
  Each run costs real tokens.

## Procedure (when this skill triggers)
1. **Resolve the confirm model** 🔴 CHECKPOINT — Gate: No config + no inline model → **BLOCK**, send user to `/pantheon-model`. Config found or inline model named → **PASS**, continue.
   1. If the user named a model inline ("confirm with deepseek", "ollama/qwen2.5:7b로 점검"), use that —
      just this run; it doesn't change the saved default.
   2. Else **Read `~/.pantheon/config.json`** and use its `verifier`. If it also has a `providers` block,
      keep it to pass along (step 5). The default is shared with `pantheon-custom`.
   3. If there's **no config yet**, tell the user to run **`/pantheon-model`** once to pick a model (it
      lists what's available and sets up any API key), then either wait or proceed with the Claude
      default (`= the pantheon-gap base`) for this run. Don't onboard here — picking the model is
      `/pantheon-model`'s job.
   Formats: OpenClaw-style `provider/model-id` (`ollama/qwen2.5:7b`, `deepseek/deepseek-chat`, …) or an
   alias (`deepseek`, `qwen`, `kimi`, `codex`, `ollama:<m>`, `profile:<name>`).
2. **Sanity-check the confirm model** 🔴 CHECKPOINT — Gate: Verifier unavailable → flag "unconfirmed" but **continue** (don't block pipeline). Verifier available → **PASS**. Never silently substitute Claude for external model.
   - Claude tier → nothing to check.
   - `codex`/`gpt` → the `codex:codex-rescue` agent type (Codex plugin) is installed.
   - Local (`ollama/…`, `lmstudio/…`) → `codex` CLI on PATH and the local server up with the model pulled.
   - Cloud (deepseek, qwen, gemini, …) → `codex` CLI on PATH and the provider's key available
     (`printenv <ENVKEY>`, or in `~/.pantheon/env` which the harness sources before codex). **If the key
     isn't set up, send the user to `/pantheon-model`** — it does the secure key setup (key goes in a
     file, never the chat). Don't collect keys here.
   If it can't run, offer a Claude tier or the `pantheon-gap` base instead of shipping an unconfirmed
   report.
3. **Pin the target** 🔴 CHECKPOINT — Gate: No target path → **BLOCK**, ask 1 short question. Target pinned + focus clear → **PASS**, continue. Never guess target path. (e.g. "security and
   tests only")? If unclear, ask 1 short question.
4. **Decide the parameters:**
   - `target`: an **absolute path** to the project root to audit.
   - `dimensions` (optional): an explicit list to audit; omit to let the scout pick the most relevant.
   - `focus` (optional): a dimension or area to emphasize.
   - `maxDimensions`: how many dimensions to probe (default 6).
   - `verifiers`: skeptical reviewers per finding (default 2; bump to 3 to be stricter).
   - `verifier`: the model that runs the adversarial confirm (see the table above). Omit for Claude.
5. 🔴 CHECKPOINT — **Pre-Workflow Gate:** Confirm parameters before launch:
   - Target: `{target}` exists and is absolute path?
   - Dimensions: `{maxDimensions}` dims, focused on `{focus or "none"}`
   - Verifier: `{VR.who}` with `{verifiers}` skeptics per gap
   - Expected cost: ~{maxDimensions} probe agents + ~{maxDimensions × verifiers} confirm agents + synthesize
   - User confirms → **PASS**, launch Workflow. User declines → **ABORT**, return to step 3-4.
6. **Run the Workflow** — **Read `pantheon-gap-class.js` in this same directory**, then pass its
   contents inline as the Workflow `script` argument. **Pass the chosen `verifier`:**
   ```
   Workflow({
     script: <contents of pantheon-gap-class.js>,
     args: { target, dimensions, focus, maxDimensions, verifiers, verifier, providers }
   })
   ```
   (`providers` = the `providers` block from `~/.pantheon/config.json` if present — `/pantheon-model`
   writes it for custom cloud providers; omit it and the built-in ~15-provider catalog still routes.
   This skill's instruction is itself the approval to call Workflow.)
7. **It runs in the background.** When the completion notice arrives, report: which dimensions were
   probed, how many gaps were found vs. confirmed by the chosen model (survived adversarial dismissal),
   the top prioritized gaps, the quick wins, and the single highest-leverage fix. **State which model
   did the confirming** (the script logs it).

## Pipeline (what the script does)

**Phase 0 — Static Pre-Scan (deterministic, no LLM):** Before Map phase, quick grep for objective code smells. These become seed evidence for dimension probes:
```
rg -n "TODO|FIXME|HACK|XXX" --type-add 'code:*.{py,go,js,ts,dart}' -t code          # unfinished logic
rg -n "except\s*(Exception)?\s*:\s*pass" --type py                                      # swallowed errors
rg -n "catch\s*\(.*\)\s*\{\s*\}" --type ts --type js                                     # empty catch blocks
rg -nE '(password|secret|key|token)\s*=\s*["\x27][^"\x27]{8,}' --type-add 'code:*.{py,go,js,ts,dart,yaml,toml}' -t code  # potential hardcoded secrets
rg -n "return\s+(Ok|None|null)\s*;" --type-add 'code:*.{rs,go}' -t code                  # premature returns (Sniff)
```
Findings tagged `[PRE-SCAN]` — lower confidence than LLM-probed gaps, but high precision. Feed to dimension probes as seed evidence.

- **Map** — one scout reads the README/structure/manifests/tests/CI, names the project's stated purpose
  and maturity, and picks the dimensions worth auditing for THIS project.
- **Probe** — one Claude agent per dimension hunts for gaps (missing/incomplete/weak), each citing
  file-level evidence; high-signal findings over a long noisy list.
- **Confirm** — for each candidate gap, V skeptics **on the chosen `verifier` model** try to DISMISS it.
  For external/local models a driver runs `codex exec` (sandbox: read-only, ephemeral) and relays the
  model's structured verdict; a gap is kept only if a majority confirm it.
- **Synthesize** — a Claude judge dedups and prioritizes by impact × effort: top gaps, quick wins, and
  the highest-leverage next fix.

## Quality Rules（production-audit 模式）

**Convergence loop:** If gap report is critical (pre-launch/pre-production), re-run probe phase with different dimension angles. Two consecutive passes with zero new gaps → DONE. Max 2 re-probes (budget protection). Mark: `Passes: N (converged / budget-exhausted)`.

**Confidence filter:** Report only gaps with >80% confidence they are real. Uncertain → mark `SUSPECT`, do not block action. Never manufacture gaps to fill the report.

**No hedging:** Zero tolerance for "might/could/consider/suggest/maybe/possibly." Every gap: concrete `file:line` evidence + concrete fix suggestion. Can't provide both → don't report.

**TRUNCATED AT:** Context exhausted mid-pipeline → mark `TRUNCATED AT: {phase}`. Deliver partial findings, ask: "Continue from {phase}?"

**Steelman before dismiss (adversarial verification):** Every verifier MUST first argue FOR the gap — "under what conditions would this be a real problem?" — BEFORE attempting to dismiss. This prevents knee-jerk dismissal. Each dismissal needs ≥1 specific code-level reason (not "seems fine" or "not needed"). Verdicts without steelman preamble are invalid.

**Bias-aware verification:** Verifier prompts explicitly strip source attribution (no "Claude found…" / "agent X reported…"). Gap presented as bare claim + evidence. This prevents same-model deference and authority bias. Each verifier sees: dimension, title, severity, evidence, suggestion — no agent name.

**Progressive disclosure:** >8 gaps or >3000 lines → P0/P1 first, ask before expanding. P0: full evidence trace + steelman. P1: evidence + suggestion. P2: brief summary. P3: dimension + fix only.

## Post-Report Protocol 🔴 CHECKPOINT

After delivering the gap report:
- **Confirmed gaps** → list top 3 by impact×effort + quick wins. Ask: "Prioritize these, or drill deeper into a specific dimension?"
- **Unconfirmed gaps** (external model unavailable) → flag them: "These gaps were NOT cross-checked — treat as suggestions, not findings."
- **Zero gaps found** → suggest: widen dimension set, lower confirm threshold, or run with a different verifier model.

## Report Artifacts

**Before writing: `mkdir -p {target}/.gaps` if the directory does not exist.**

Every gap analysis writes to `{target}/.gaps/{scope}-{YYMMDD-HHMM}.md` — survives context compaction, enables trend tracking.

```
.gaps/
├── full-20260621-1430.md     ← this analysis
├── security-20260620-0900.md ← previous focused scan
└── ESCALATIONS.md             ← recurring gap tracker
```

**Escalation rule:** If same gap appears in 2+ consecutive analyses of the same project → auto-escalate severity one level (LOW→MEDIUM→HIGH→CRITICAL) and flag in `ESCALATIONS.md`.

**Cleanup:** Keep last 20 gap files per directory. Delete older than 90 days. `.gaps/` should be in `.gitignore`.

## Notes
- **Not a resident process.** One-shot per call, then exits — zero cost when idle.
- It **reports** gaps; it does not fix them. Hand the report to `pantheon` (or plain Opus) to act on.
- The external model does the actual judging; Claude only transports its verdict, so cross-vendor
  independence holds. Built-in `deepseek`/`qwen`/`kimi` aliases are conveniences — for full control set
  up a `profile:` in `~/.codex/config.toml`.
- Coding/agentic productivity only. Not for bypassing safety gates.
