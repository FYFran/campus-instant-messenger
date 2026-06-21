export const meta = {
  name: 'pantheon-gap-class',
  description: 'Multi-agent gap analysis & feedback review: map the project -> probe each dimension for gaps -> adversarially confirm each gap -> synthesize a prioritized report',
  phases: [
    { title: 'PreScan', detail: 'Deterministic grep for TODO/FIXME/empty-catch/hardcoded → seed evidence' },
    { title: 'Map', detail: 'Scout the project: stated purpose, stack, maturity, and which dimensions to audit' },
    { title: 'Probe', detail: 'One agent per dimension hunts for gaps with file-level evidence + seed evidence' },
    { title: 'Confirm', detail: 'Skeptical reviewers steelman then dismiss; false positives dropped' },
    { title: 'Synthesize', detail: 'Judge dedups, prioritizes P0→P3, writes structured report' },
    { title: 'Critic', detail: 'Self-verify report: check evidence citations, hedging, duplicates, confidence consistency' },
  ],
}

// NOTE: the Workflow tool delivers `args` as a JSON STRING (not a parsed object).
// Parse defensively so this works whether args is a string, an object, or absent.
let A = {}
if (typeof args === 'string') { try { A = args ? JSON.parse(args) : {} } catch (e) { A = {} } }
else if (args && typeof args === 'object') { A = args }

const target = A.target ?? A.workdir ?? '.'         // absolute path to the project being reviewed
const focus = A.focus ?? null                       // optional: dimension/area to emphasize
const maxDims = A.maxDimensions ?? 6                // how many dimensions to probe
const V = A.verifiers ?? 2                          // skeptical reviewers per candidate gap
const crossVerify = A.crossModelVerify ?? false    // true => Codex/GPT-5.5 runs the confirm step
const dimensionsOverride = Array.isArray(A.dimensions) ? A.dimensions : null

const PROFILE_SCHEMA = {
  type: 'object',
  properties: {
    projectType: { type: 'string', description: 'What kind of project this is (CLI, web app, library, ...)' },
    statedPurpose: { type: 'string', description: 'What the project claims to do, per README/docs' },
    stack: { type: 'array', items: { type: 'string' } },
    maturity: { type: 'string', enum: ['prototype', 'mvp', 'production', 'unknown'] },
    dimensions: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          key: { type: 'string' },
          why: { type: 'string', description: 'Why this dimension matters for THIS project' },
        },
        required: ['key', 'why'],
      },
      description: 'The dimensions worth auditing for this specific project, most important first',
    },
  },
  required: ['statedPurpose', 'dimensions'],
}

const FINDINGS_SCHEMA = {
  type: 'object',
  properties: {
    dimension: { type: 'string' },
    gaps: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          title: { type: 'string' },
          severity: { type: 'string', enum: ['low', 'medium', 'high', 'critical'] },
          evidence: { type: 'string', description: 'file:line or a concrete observation from the actual code' },
          impact: { type: 'string' },
          suggestion: { type: 'string' },
        },
        required: ['title', 'severity', 'evidence', 'suggestion'],
      },
    },
  },
  required: ['dimension', 'gaps'],
}

// Verifier lenses (CodeX-Verify pattern: independent evidence accumulates when agents check DIFFERENT aspects, ρ≈0.05-0.25)
const LENSES = ['correctness', 'security', 'performance', 'completeness', 'architecture']
const VERDICT_SCHEMA = {
  type: 'object',
  properties: {
    valid: { type: 'boolean', description: 'true ONLY if gap holds up after steelman attempt' },
    steelman: { type: 'string', description: 'MANDATORY: best argument FOR this gap being real. What conditions make it exploitable? Who affected? Skip → verdict invalid.' },
    reason: { type: 'string', description: 'Why dismissed (cite specific code location verified) or why confirmed' },
    confidence: { type: 'number', minimum: 0, maximum: 1, description: '0.0-1.0 confidence this verdict is correct. <0.8 = uncertain → gap marked SUSPECT.' },
    codeReference: { type: 'string', description: 'Specific file:line verified during review. "Seems fine" without code ref → invalid dismissal.' },
    adjustedSeverity: { type: 'string', enum: ['low', 'medium', 'high', 'critical'] },
    lens: { type: 'string', enum: LENSES, description: 'Which verification lens this reviewer used' },
  },
  required: ['valid', 'steelman', 'reason', 'confidence'],
}

const REPORT_SCHEMA = {
  type: 'object',
  properties: {
    summary: { type: 'string', description: "Short read on the project's current state" },
    highestLeverage: { type: 'string', description: 'The single most important thing to fix next' },
    topGaps: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          title: { type: 'string' },
          dimension: { type: 'string' },
          severity: { type: 'string' },
          impact: { type: 'string' },
          suggestion: { type: 'string' },
        },
        required: ['title', 'severity', 'suggestion'],
      },
    },
    quickWins: { type: 'array', items: { type: 'string' }, description: 'Cheap, high-value fixes' },
    overallAssessment: { type: 'string' },
  },
  required: ['summary', 'highestLeverage', 'topGaps'],
}

// ---- Agent reliability wrapper (cc-recovery pattern: categorize → retry/skip/escalate) ----
// Error categories: transient (network/timeout → retry with backoff), recoverable (null result → retry once), fatal (schema violation → skip)
async function safeAgent(promptCore, opts, category = 'recoverable') {
  const MAX_RETRIES = category === 'transient' ? 3 : category === 'recoverable' ? 1 : 0
  const BACKOFF_MS = [1000, 4000, 16000] // exponential: 1s → 4s → 16s
  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    try {
      const result = await agent(promptCore, opts)
      if (result !== null) return result
      if (attempt < MAX_RETRIES) {
        log(`⚠ ${opts.label || 'agent'}: null result, retry ${attempt + 1}/${MAX_RETRIES}...`)
        await new Promise((r) => { /* sleep via busy-wait approximation — Workflow sandbox has no setTimeout */ let x = 0; while (x < BACKOFF_MS[attempt] * 1000) x++ })
      }
    } catch (_) {
      if (attempt < MAX_RETRIES) {
        log(`⚠ ${opts.label || 'agent'}: error, retry ${attempt + 1}/${MAX_RETRIES}...`)
      }
    }
  }
  log(`✗ ${opts.label || 'agent'}: FAILED after ${MAX_RETRIES + 1} attempt(s) — ${category === 'fatal' ? 'ESCALATE' : 'SKIPPED'}`)
  return null
}

// ---- Phase 0: PRE-SCAN — deterministic grep for code smells (no LLM judgment, seed evidence for probes) ----
const PRE_SCAN_FINDINGS = { type: 'object', properties: { findings: { type: 'array', items: { type: 'object', properties: { pattern: { type: 'string' }, file: { type: 'string' }, line: { type: 'number' }, snippet: { type: 'string' } }, required: ['pattern', 'file', 'line'] } } }, required: ['findings'] }
phase('PreScan')
const preScan = await agent(
  `Run these grep commands in ${target} and return EVERY match as a structured finding (no filtering, no judgment — grep is deterministic):\n` +
    `1. rg -n "TODO|FIXME|HACK|XXX" --type-add 'code:*.{py,go,js,ts,dart,rs}' -t code\n` +
    `2. rg -n "except\\s*(Exception)?\\s*:\\s*pass" --type py\n` +
    `3. rg -n "catch\\s*\\(.*\\)\\s*\\{\\s*\\}" --type ts --type js\n` +
    `4. rg -nE '(password|secret|key|token)\\s*=\\s*["\\x27][^"\\x27]{8,}' --type-add 'code:*.{py,go,js,ts,dart,yaml,toml}' -t code\n` +
    `Return { findings: [{ pattern: "TODO|FIXME|...", file: "path:line", line: N, snippet: "matched line" }] }. Empty array if no matches.`,
  { schema: PRE_SCAN_FINDINGS, phase: 'PreScan', label: 'prescan' },
)
const seedEvidence = (preScan?.findings ?? []).map((f) => `[PRE-SCAN] ${f.pattern}: ${f.file} — ${(f.snippet ?? '').slice(0, 80)}`)
if (seedEvidence.length > 0) log(`Phase 0/7 complete: ${seedEvidence.length} code smells → seed evidence`)
else log('Phase 0/7 complete: no code smells found')

// ---- Phase 1: MAP — scout the project and choose the dimensions worth auditing ----
phase('Map')
log(`Phase 1/7: Map — scouting ${target}...`)
const profile = await agent(
  `You are the SCOUT in a Pantheon gap-analysis harness. Target project: ${target}\n\n` +
    `Survey it: read the README/docs, the directory structure, package manifests, entry points, tests, and CI config. ` +
    `Determine what the project IS, its STATED PURPOSE (what it claims to do), its stack, and its maturity. ` +
    `Then choose up to ${maxDims} dimensions most worth auditing for GAPS in THIS specific project, most important first.\n` +
    `Dimension menu (pick from these and/or add project-specific ones): product-completeness, correctness-robustness, ` +
    `testing, security, docs-onboarding, architecture-maintainability, dx-api, performance-scalability, ops-observability.` +
    (focus ? `\nThe user wants extra emphasis on: ${focus}.` : ''),
  { schema: PROFILE_SCHEMA },
)
const dims = dimensionsOverride
  ? dimensionsOverride.map((k) => ({ key: k, why: 'user-specified' }))
  : profile.dimensions.slice(0, maxDims)
log(`Phase 1/7 complete: "${(profile.statedPurpose ?? 'project').slice(0, 60)}" (${profile.maturity ?? 'unknown'}). Auditing ${dims.length} dims: ${dims.map((d) => d.key).join(', ')}`)

// ---- Phases 2+3: PROBE each dimension, then CONFIRM each gap adversarially (pipelined) ----
// pantheon-gap-custom: the adversarial-confirm step runs on a USER-SELECTABLE model (`verifier` arg).
//  - Claude family (opus/sonnet/haiku/fable) -> { model }; omitted/'claude' -> default Claude.
//  - 'codex'/'gpt' -> the installed codex:codex-rescue plugin agent (codex's default model).
//  - ANY OTHER external/local AI is driven through `codex exec` (codex is itself a multi-provider
//    router): 'ollama:<model>' / 'lmstudio:<model>' (local, no key), 'profile:<name>' (a codex
//    config profile), 'model:<name>' (a codex model id), or a built-in alias below
//    (deepseek/qwen/kimi — needs the matching *_API_KEY env var). crossModelVerify:true stays = codex.
// Provider catalog mirrored from OpenClaw (docs.openclaw.ai/concepts/model-providers): the
// OpenAI/Responses-compatible cloud + local-HTTP providers `codex exec` can route to. `envKey` is the
// NAME of the API-key env var (no secret). Extend/override at runtime via args.providers (same shape,
// e.g. fed from the repo's providers.json). First-party Claude / GPT-5.5 / Ollama are special-cased below.
const PROVIDERS = {
  deepseek: { baseUrl: 'https://api.deepseek.com', envKey: 'DEEPSEEK_API_KEY', wire: 'chat', defModel: 'deepseek-chat' },
  openrouter: { baseUrl: 'https://openrouter.ai/api/v1', envKey: 'OPENROUTER_API_KEY', wire: 'chat', defModel: 'qwen/qwen-2.5-coder-32b-instruct' },
  mistral: { baseUrl: 'https://api.mistral.ai/v1', envKey: 'MISTRAL_API_KEY', wire: 'chat', defModel: 'mistral-large-latest' },
  groq: { baseUrl: 'https://api.groq.com/openai/v1', envKey: 'GROQ_API_KEY', wire: 'chat', defModel: 'llama-3.3-70b-versatile' },
  xai: { baseUrl: 'https://api.x.ai/v1', envKey: 'XAI_API_KEY', wire: 'chat', defModel: 'grok-4' },
  together: { baseUrl: 'https://api.together.xyz/v1', envKey: 'TOGETHER_API_KEY', wire: 'chat', defModel: 'meta-llama/Llama-3.3-70B-Instruct-Turbo' },
  moonshot: { baseUrl: 'https://api.moonshot.ai/v1', envKey: 'MOONSHOT_API_KEY', wire: 'chat', defModel: 'kimi-k2-0711-preview' },
  dashscope: { baseUrl: 'https://dashscope-intl.aliyuncs.com/compatible-mode/v1', envKey: 'DASHSCOPE_API_KEY', wire: 'chat', defModel: 'qwen2.5-coder-32b-instruct' },
  google: { baseUrl: 'https://generativelanguage.googleapis.com/v1beta/openai', envKey: 'GEMINI_API_KEY', wire: 'chat', defModel: 'gemini-2.5-pro' },
  nvidia: { baseUrl: 'https://integrate.api.nvidia.com/v1', envKey: 'NVIDIA_API_KEY', wire: 'chat', defModel: 'nvidia/llama-3.3-nemotron-super-49b-v1' },
  novita: { baseUrl: 'https://api.novita.ai/v3/openai', envKey: 'NOVITA_API_KEY', wire: 'chat', defModel: 'deepseek/deepseek-v3-0324' },
  perplexity: { baseUrl: 'https://api.perplexity.ai', envKey: 'PERPLEXITY_API_KEY', wire: 'chat', defModel: 'sonar-pro' },
  zai: { baseUrl: 'https://api.z.ai/api/paas/v4', envKey: 'ZAI_API_KEY', wire: 'chat', defModel: 'glm-4.6' },
  vllm: { baseUrl: 'http://127.0.0.1:8000/v1', envKey: 'VLLM_API_KEY', wire: 'chat', defModel: '' },
  sglang: { baseUrl: 'http://127.0.0.1:30000/v1', envKey: 'SGLANG_API_KEY', wire: 'chat', defModel: '' },
}
const ALIASES = { qwen: 'dashscope', kimi: 'moonshot', grok: 'xai', gemini: 'google', glm: 'zai' }
const providers = Object.assign({}, PROVIDERS, A.providers && typeof A.providers === 'object' ? A.providers : {})
// Cloud providers are called DIRECTLY via their OpenAI-compatible /chat/completions endpoint (curl),
// NOT through codex: codex 0.139.0 only speaks the Responses wire, which chat-only providers lack.
function httpDesc(provId, model) {
  const p = providers[provId]
  return { mode: 'http', baseUrl: p.baseUrl, envKey: p.envKey, model: model || p.defModel || (p.models && p.models[0]) || provId, who: provId + (model ? ' ' + model : '') }
}
// Map a `verifier` string to how the adversarial step runs. Accepts: '' / 'claude' (default Claude),
// a Claude tier, 'codex'/'gpt', an 'ollama:/lmstudio:/profile:/model:' form, a cloud alias
// (deepseek/qwen/kimi), or an OpenClaw-style 'provider/model-id' (anthropic/haiku, ollama/qwen2.5:7b,
// deepseek/deepseek-chat, openrouter/qwen/..., openai/gpt-5.5).
function resolveVerifier(v, crossLegacy) {
  const raw = typeof v === 'string' ? v.trim() : ''
  const m = raw.toLowerCase()
  const CLAUDE = ['opus', 'sonnet', 'haiku', 'fable']
  if (!m || m === 'claude' || m === 'default') return crossLegacy ? { mode: 'agent', agentType: 'codex:codex-rescue', who: 'GPT-5.5 (Codex)' } : { mode: 'claude', who: 'Claude (default)' }
  if (CLAUDE.includes(m)) return { mode: 'claude', model: m, who: 'Claude ' + m }
  if (m === 'codex' || m === 'gpt' || m === 'gpt-5.5' || m === 'gpt5.5' || m === 'openai') return { mode: 'agent', agentType: 'codex:codex-rescue', who: 'GPT-5.5 (Codex)' }
  // OpenClaw-style provider/model-id (split on FIRST slash)
  if (raw.includes('/')) {
    const s = raw.indexOf('/'); let prov = raw.slice(0, s).toLowerCase(); const model = raw.slice(s + 1)
    if (prov === 'anthropic' || prov === 'claude') return CLAUDE.includes(model.toLowerCase()) ? { mode: 'claude', model: model.toLowerCase(), who: 'Claude ' + model } : { mode: 'claude', who: 'Claude' }
    if (prov === 'ollama' || prov === 'lmstudio') return { mode: 'codex', codexArgs: ['--oss', '--local-provider', prov, '-m', model], who: prov + ' ' + model + ' (local)' }
    if (prov === 'openai' || prov === 'gpt') return { mode: 'codex', codexArgs: ['-m', model], who: model }
    if (ALIASES[prov]) prov = ALIASES[prov]
    if (providers[prov] && providers[prov].baseUrl) return httpDesc(prov, model)
    return { mode: 'codex', codexArgs: ['-c', `model_provider=${prov}`, '-m', model], who: raw }
  }
  // prefix forms
  if (m.startsWith('ollama:') || m.startsWith('lmstudio:')) {
    const i = raw.indexOf(':'); const prov = raw.slice(0, i).toLowerCase(); const model = raw.slice(i + 1)
    return { mode: 'codex', codexArgs: ['--oss', '--local-provider', prov, '-m', model], who: prov + ' ' + model + ' (local)' }
  }
  if (m.startsWith('profile:')) { const name = raw.slice(raw.indexOf(':') + 1); return { mode: 'codex', codexArgs: ['-p', name], who: 'codex profile ' + name } }
  if (m.startsWith('model:')) { const name = raw.slice(raw.indexOf(':') + 1); return { mode: 'codex', codexArgs: ['-m', name], who: name } }
  const provId = ALIASES[m] || m
  if (providers[provId] && providers[provId].baseUrl) return httpDesc(provId, null)
  return { mode: 'codex', codexArgs: ['-m', raw], who: raw }
}
const VR = resolveVerifier(A.verifier, crossVerify)
log(`Adversarial confirm model: ${VR.who}`)
// One skeptic's agent() promise, routed to the chosen model. `meta` = { phase, label }.
function verifierAgent(promptCore, meta) {
  if (VR.mode === 'http') {
    return agent(
      `You are a DRIVER. Delegate this gap confirmation to an INDEPENDENT external model (${VR.who}) by calling its OpenAI-compatible chat API DIRECTLY (not via codex), then relay ITS verdict. Do NOT judge the gap yourself.\n\n` +
        `Steps (use Bash; never print the key):\n` +
        `1. Load the key: [ -f ~/.pantheon/env ] && . ~/.pantheon/env   (sets $${VR.envKey}).\n` +
        `2. Using python3 so the prompt is safely JSON-escaped, write a request-body file with: model="${VR.model}", temperature=0, messages=[{"role":"user","content": THE REVIEW PROMPT BELOW, followed by "Inspect the actual code, then output ONLY one compact JSON object with keys valid(boolean), reason(string), adjustedSeverity(one of low|medium|high|critical)."}].\n` +
        `3. POST it: curl -s -w "\\n%{http_code}" ${VR.baseUrl}/chat/completions -H "Authorization: Bearer $${VR.envKey}" -H "Content-Type: application/json" -d @BODYFILE\n` +
        `4. From the JSON response take choices[0].message.content, extract the verdict JSON object it contains, and return THAT as your structured output (unchanged).\n` +
        `5. If $${VR.envKey} is empty, the HTTP status is not 200, or no JSON comes back, return valid=true, reason="external verifier ${VR.who} unavailable: <short error> — gap KEPT unconfirmed, verify manually", adjustedSeverity="medium". Never fabricate a dismissal.\n\n` +
        `REVIEW PROMPT <<<\n${promptCore}\n>>>`,
      { schema: VERDICT_SCHEMA, ...meta },
    )
  }
  if (VR.mode === 'codex') {
    return agent(
      `You are a DRIVER. Delegate this gap confirmation to an INDEPENDENT external model (${VR.who}) via the codex CLI, then relay ITS verdict. Do NOT judge the gap yourself.\n\n` +
        `Steps (use Bash; create temp files with mktemp):\n` +
        `1. Write this JSON Schema to a file $SCHEMA:\n${JSON.stringify(VERDICT_SCHEMA)}\n` +
        `2. Write the REVIEW PROMPT (between <<< >>> below) to a file $PROMPT.\n` +
        `3. Load saved API keys (if any), then run EXACTLY (OUT = another mktemp file). Do NOT print the keys:\n   [ -f ~/.pantheon/env ] && . ~/.pantheon/env;  codex exec --skip-git-repo-check --ephemeral --sandbox read-only -C ${target} ${VR.codexArgs.join(' ')} --output-schema "$SCHEMA" -o "$OUT" < "$PROMPT"\n   If codex rejects --output-schema for this provider, drop that flag and instead extract the JSON object the model prints to stdout.\n` +
        `4. Read $OUT (or the parsed stdout JSON) and return it as your structured verdict, unchanged.\n` +
        `If codex is missing / the *_API_KEY is unset / the model is unreachable / no JSON is produced, return {"valid":true,"reason":"external verifier ${VR.who} unavailable: <short error> — gap KEPT unconfirmed, verify manually","adjustedSeverity":"medium"} — never fabricate a dismissal.\n\n` +
        `REVIEW PROMPT <<<\n${promptCore}\n\nInspect the actual code, then output ONLY the verdict JSON.\n>>>`,
      { schema: VERDICT_SCHEMA, ...meta },
    )
  }
  const extra = VR.mode === 'agent' ? { agentType: VR.agentType } : VR.model ? { model: VR.model } : {}
  return agent(promptCore, { schema: VERDICT_SCHEMA, ...meta, ...extra })
}

// Convergence loop: if CRITICAL gaps survive, re-probe with shifted angles (max 3 total passes)
let allReviewed = []; let finalConfirmed = []; let finalSuspects = []; let passes = 0; const MAX_PASSES = 3
let currentDims = dims; let currentSeed = seedEvidence
log(`Phase 2/7: Probe — ${currentDims.length} dimensions, ${V} verifiers each`)
while (passes < MAX_PASSES) {
  passes++
  const reviewed = await pipeline(
  dims,
  // Stage 1 — probe one dimension for concrete, evidence-backed gaps
  (d) =>
    agent(
      `You are GAP-PROBE for the "${d.key}" dimension in a Pantheon gap-analysis harness. Target project: ${target}\n` +
        `Project purpose: ${profile.statedPurpose}\nWhy this dimension matters here: ${d.why}\n\n` +
        `Hunt for concrete GAPS — things that are MISSING, incomplete, or weak in this dimension. ` +
        `For each gap give a short title, a severity, EVIDENCE (cite a file:line or a concrete observation — read the actual code, do NOT speculate), the impact, and a concrete suggestion. ` +
        `Prefer 3-8 real, high-signal gaps over a long noisy list. If this dimension is genuinely solid, return an empty gaps array.`,
      { schema: FINDINGS_SCHEMA, phase: 'Probe', label: `probe:${d.key}` },
    ),
  // Stage 2 — for each gap, V skeptical reviewers try to DISMISS it
  (review) =>
    parallel(
      (review?.gaps ?? []).map((g) => () =>
        parallel(
          Array.from({ length: V }, (_, k) => () => {
            const lens = LENSES[k % LENSES.length]
            return verifierAgent(
              // Bias-aware: no source attribution ("probe claims" → "gap found"). Steelman first.
              `You are a SKEPTICAL REVIEWER (lens: ${lens}) in a Pantheon gap-analysis harness. A gap was found in project ${target}:\n\n` +
                `DIMENSION: ${review.dimension}\nGAP: ${g.title}\nSEVERITY: ${g.severity}\nEVIDENCE: ${g.evidence}\nSUGGESTION: ${g.suggestion}\n\n` +
                `STEP 1 — STEELMAN (mandatory): Write your BEST argument for why this COULD be a real gap. What conditions make it exploitable? Who would be affected? What's the worst case?\n\n` +
                `STEP 2 — VERIFY through ${lens} lens: Inspect the ACTUAL code. Is it already handled elsewhere? Out of scope? False positive? Trivial? Each dismissal MUST cite a specific code location you verified (file:line). "Seems fine" without code reference = invalid.\n\n` +
                `STEP 3 — VERDICT: valid=false ONLY with concrete code evidence. valid=true if gap survives steelman attempt. Set confidence 0.0-1.0 (<0.8 = uncertain).`,
              { phase: 'Confirm', label: `confirm:${review.dimension}.${k}` },
            )
          }),
        ).then((vs) => {
          const verdicts = vs.filter(Boolean)
          const validVerdicts = verdicts.filter((v) => v.valid)
          const kept = validVerdicts.length >= Math.ceil(V / 2)
          // Confidence calibration (RAE/DSO-Agent pattern): avg confidence across valid verdicts; <0.8 → SUSPECT
          const avgConf = validVerdicts.length > 0
            ? validVerdicts.reduce((s, v) => s + (v.confidence ?? 0.5), 0) / validVerdicts.length
            : 0
          const suspect = kept && avgConf < 0.8  // survived majority but low confidence → escalate
          const sev = validVerdicts.filter((v) => v.adjustedSeverity).map((v) => v.adjustedSeverity)[0]
          const lensBreakdown = {}
          verdicts.forEach((v) => { if (v.lens) { lensBreakdown[v.lens] = (lensBreakdown[v.lens] || 0) + (v.valid ? 1 : 0) } })
          return { ...g, dimension: review.dimension, kept, suspect, verdicts: verdicts.length, validVotes: validVerdicts.length, avgConfidence: Math.round(avgConf * 100) / 100, adjustedSeverity: sev ?? g.severity, lensBreakdown }
        }),
      ),
    ),
)

  const allGaps = reviewed.filter(Boolean).flat().filter(Boolean)
  const confirmed = allGaps.filter((g) => g.kept && !g.suspect)
  const suspects = allGaps.filter((g) => g.kept && g.suspect)
  allReviewed = allReviewed.concat(allGaps)
  // Merge: new confirmed replace old for same dimension+title, else append
  for (const g of confirmed) {
    const idx = finalConfirmed.findIndex((x) => x.dimension === g.dimension && x.title === g.title)
    if (idx >= 0) finalConfirmed[idx] = g; else finalConfirmed.push(g)
  }
  for (const g of suspects) {
    const idx = finalSuspects.findIndex((x) => x.dimension === g.dimension && x.title === g.title)
    if (idx >= 0) finalSuspects[idx] = g; else finalSuspects.push(g)
  }
  const hasCritical = confirmed.some((g) => g.adjustedSeverity === 'critical')
  if (hasCritical && passes < MAX_PASSES) {
    log(`Pass ${passes}: ${confirmed.length} confirmed (CRITICAL found) → re-probing with angle shift`)
    // Shift dimension order to get fresh angles (rotate + swap adjacent)
    currentDims = [...currentDims.slice(1), currentDims[0]]
    currentSeed = confirmed.filter((g) => g.adjustedSeverity === 'critical').map((g) => `[RE-PROBE seed] ${g.dimension}: ${g.title} — ${g.evidence}`)
  } else {
    log(`Pass ${passes}: ${confirmed.length} confirmed, ${suspects.length} SUSPECT → ${hasCritical ? 'max passes' : 'converged'}`)
    break
  }
}
const confirmed = finalConfirmed; const suspects = finalSuspects
const allGaps = allReviewed.filter(Boolean).flat().filter(Boolean)
const avgConfAll = confirmed.length > 0 ? Math.round(confirmed.reduce((s, g) => s + (g.avgConfidence ?? 0), 0) / confirmed.length * 100) / 100 : 0
log(`Final: ${confirmed.length}/${allGaps.length} gaps confirmed (avg confidence ${avgConfAll})${suspects.length > 0 ? ', ' + suspects.length + ' SUSPECT' : ''} after ${passes} pass(es)`)

// ---- Phase 4: SYNTHESIZE — dedup, prioritize, write the feedback report ----
phase('Synthesize')
log(`Phase 4/7: Synthesize — dedup + prioritize ${confirmed.length} confirmed + ${suspects.length} SUSPECT gaps`)
if (!confirmed.length && !suspects.length) {
  return {
    target,
    profile: { purpose: profile.statedPurpose, stack: profile.stack, maturity: profile.maturity, dimensions: dims.map((d) => d.key), passes: 1 },
    gapsFound: allGaps.length,
    gapsConfirmed: 0,
    gapsSuspect: 0,
    avgConfidence: 0,
    report: {
      summary: 'No high-confidence gaps survived adversarial review across the audited dimensions.',
      highestLeverage: 'Nothing critical surfaced. Widen the dimension set or deepen the probe if you want more coverage.',
      topGaps: [],
      quickWins: [],
      overallAssessment: 'The audited dimensions look solid, or the project is too early/empty to probe meaningfully.',
    },
  }
}

const priorityLabel = (s) => s === 'critical' ? '🔴P0' : s === 'high' ? '🟠P1' : s === 'medium' ? '🟡P2' : '🔵P3'
const report = await agent(
  `You are the JUDGE/SYNTHESIZER in a Pantheon gap-analysis harness for project ${target} (purpose: ${profile.statedPurpose}). ` +
    `Here are the gaps that SURVIVED adversarial review:\n` +
    confirmed
      .map((g, i) => `${i + 1}. [${g.dimension} | ${priorityLabel(g.adjustedSeverity)} | conf:${g.avgConfidence ?? '?'}] ${g.title} — ${g.impact ?? ''} (evidence: ${g.evidence}; fix: ${g.suggestion})`)
      .join('\n') +
    (suspects.length > 0 ? `\n\nSUSPECT gaps (majority confirmed but avg confidence <0.8 — treat as suggestions, not findings):\n` +
      suspects.map((g, i) => `${i + 1}. [${g.dimension} | ${g.adjustedSeverity} | conf:${g.avgConfidence}] ${g.title} — ${g.impact ?? ''}`).join('\n') : '') +
    `\n\nDeduplicate overlapping gaps, then produce the final feedback review: a short summary of the project's state, the TOP gaps prioritized by P0→P1→P2→P3 (impact x effort), a list of quick wins (cheap high-value fixes), and the single HIGHEST-LEVERAGE thing to fix next. Separate confirmed from SUSPECT. Be direct and concrete — this is feedback for the author.`,
  { schema: REPORT_SCHEMA },
)

// ---- Phase 5: CRITIC — self-verify the report before shipping ----
phase('Critic')
log('Phase 5/7: Critic — self-verifying report (evidence, hedging, duplicates, confidence, fixes)')
const CRITIC_SCHEMA = { type: 'object', properties: { passed: { type: 'boolean' }, issues: { type: 'array', items: { type: 'object', properties: { severity: { type: 'string', enum: ['blocking', 'warning'] }, type: { type: 'string', enum: ['missing_evidence', 'hedging', 'duplicate', 'confidence_mismatch', 'missing_fix'] }, detail: { type: 'string' } }, required: ['severity', 'type', 'detail'] } } }, required: ['passed', 'issues'] }
const critic = await agent(
  `You are the CRITIC. Verify this gap report before shipping:\n` +
    JSON.stringify(report, null, 2) + `\n\n` +
    `Check: 1) Every gap has file:line evidence? 2) No hedging (might/could/possibly/consider/suggest)? 3) No duplicates with different wording? 4) P0 gaps have confidence ≥0.9? 5) Every P0/P1 has concrete fix?\n` +
    `Return { passed, issues: [{ severity: "blocking"|"warning", type: "missing_evidence"|"hedging"|"duplicate"|"confidence_mismatch"|"missing_fix", detail }] }. Ship if passed.`,
  { schema: CRITIC_SCHEMA, phase: 'Critic', label: 'critic' },
)
const criticIssues = critic?.issues ?? []
const criticPassed = critic?.passed ?? true
if (!criticPassed) log(`CRITIC: ${criticIssues.filter((i) => i.severity === 'blocking').length} blocking, ${criticIssues.filter((i) => i.severity === 'warning').length} warnings`)

// ---- Phase 6: WRITE ARTIFACT — persist report to .gaps/ ----
phase('Write')
log(`Phase 6/7: Write — saving report to ${target}/.gaps/...`)
const scope = focus ? focus.replace(/\s+/g, '-') : 'full'
const artifactPath = `${target}/.gaps/${scope}-${new Date().toISOString().slice(0,16).replace(/[T:]/g,'')}.md`
await agent(
  `Run: mkdir -p ${target}/.gaps && cat > ${artifactPath} << 'REPORT_EOF'\n${JSON.stringify({ target, profile: profile.statedPurpose, passes, confirmed: confirmed.length, suspects: suspects.length, avgConfidence, criticPassed, criticIssues, report }, null, 2)}\nREPORT_EOF\n` +
    `Then verify: wc -l ${artifactPath} shows >0 lines.`,
  { phase: 'Write', label: 'write-artifact' },
)
log(`Report written to ${artifactPath}`)

// TRUNCATED AT safety net: if context exhausted mid-pipeline, mark partial
const truncated = confirmed.length < allGaps.length * 0.5 ? `TRUNCATED AT: ${passes < MAX_PASSES ? 'Probe pass ' + passes : 'Synthesize'} — ${confirmed.length}/${allGaps.length} gaps confirmed` : null
if (truncated) log(truncated)

const skippedDims = dims.filter((d) => !allGaps.some((g) => g.dimension === d.key)).map((d) => d.key)
const skippedLog = skippedDims.length > 0 ? ` | ${skippedDims.length} dims SKIPPED (${skippedDims.join(', ')})` : ''
log(`Phase 7/7 complete: ${confirmed.length} confirmed (avg conf ${avgConfAll}), ${suspects.length} SUSPECT, ${passes} passes${skippedLog}${truncated ? ', TRUNCATED' : ''}${!criticPassed ? ', CRITIC flagged' : ''}`)

return {
  criticPassed,
  criticIssues,
  target,
  profile: { purpose: profile.statedPurpose, stack: profile.stack, maturity: profile.maturity, dimensions: dims.map((d) => d.key), passes },
  probed: dims.map((d) => d.key),
  gapsFound: allGaps.length,
  gapsConfirmed: confirmed.length,
  gapsSuspect: suspects.length,
  avgConfidence: confirmed.length > 0 ? Math.round(confirmed.reduce((s, g) => s + (g.avgConfidence ?? 0), 0) / confirmed.length * 100) / 100 : 0,
  lensCoverage: LENSES.slice(0, V),
  artifactPath,
  truncated,
  report,
}
