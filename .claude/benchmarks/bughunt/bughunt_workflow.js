export const meta = {
    name: 'bughunt-benchmark',
    description: 'BugHuntBench v2.0 — automated skill quality benchmark. Fans out bug investigations in parallel worktree-isolated agents, auto-scores against ground truth.',
    phases: [
        { title: 'Setup', detail: 'Load bugs, prepare scoring harness' },
        { title: 'Investigate', detail: 'Parallel bug investigation in worktree isolation' },
        { title: 'Score', detail: 'Auto-score all reports (L1 rules + L2 LLM judge)' },
        { title: 'Verify', detail: 'L3 cross-model spot-check on scored reports' },
        { title: 'Report', detail: 'Generate summary + update results.tsv + gate check' },
    ],
}

// ============================================================
// BugHuntBench Workflow — Claude Code Dynamic Workflow
// ============================================================
// Architecture:
//   Setup → parallel(Investigate) → Score → Verify → Report
//
// Each bug gets:
//   - Isolated git worktree (clean environment)
//   - Blind investigation (no ground truth access)
//   - Structured output (validated by JSON Schema)
//
// Scoring is 3-layer:
//   L1: Rule-based (T-Type + chain + trace) — 0 token
//   L2: LLM Judge (evidence + root cause + CF) — per-dimension
//   L3: Cross-model spot-check (every 3rd run)
// ============================================================

// --- Constants ---

const BENCH_DIR = '.claude/benchmarks/bughunt'
const BUGS_DIR = `${BENCH_DIR}/bugs`
const SKILL_PATH = '.claude/skills/缉凶.md'

// Bug descriptions (user-facing only — NO ground truth)
// These are loaded at runtime from the bug files
const BUG_LIST = [
    'B01', 'B02', 'B03', 'B04', 'B05',
    'B06', 'B07', 'B08', 'B09', 'B10',
]

// T-Type taxonomy for classification
const T_TYPES = [
    'T0 — 稳定复现（每次必现）',
    'T1 — 竞态/时序（加print消失，Heisenbug）',
    'T2 — ≥2因素共同触发（修一个不收工）',
    'T3 — 无报错数据错/性能退化（silent failure）',
    'T4 — 昨天还好（git bisect + 配置变更）',
    'T5 — 状态机异常（正常输入→异常输出）',
    'T6 — 特定环境（CI/Docker/OS/版本）',
    'T7 — 代码对需求错（NOT_A_BUG，STOP）',
]

// ============================================================
// JSON Schema for agent output
// ============================================================

const BUG_REPORT_SCHEMA = {
    type: 'object',
    properties: {
        bug_id: { type: 'string', description: 'Bug ID being investigated' },
        classification: { type: 'string', description: 'T-Type: T0-T7 or NOT_A_BUG' },
        classification_reason: { type: 'string', description: 'Why this T-Type' },
        chain_steps: {
            type: 'object',
            description: '7-step contract chain outputs',
            properties: {
                classification: { type: 'string' },
                evidence: { type: 'string' },
                trace: { type: 'string' },
                analysis: { type: 'string' },
                fix: { type: 'string' },
                verify: { type: 'string' },
                record: { type: 'string' },
            },
            required: ['classification', 'evidence', 'trace', 'analysis', 'fix', 'verify', 'record'],
        },
        root_cause: { type: 'string', description: 'Root cause with file:line references' },
        root_cause_file_line: { type: 'string', description: 'Primary file:line of root cause' },
        cf_evidence: { type: 'string', description: 'Counterfactual evidence with pre/post comparison' },
        fix_description: { type: 'string', description: 'Proposed fix' },
        confidence: { type: 'number', description: 'Confidence 0.0-1.0', minimum: 0, maximum: 1 },
        latent_issues: { type: 'string', description: 'Additional issues discovered' },
    },
    required: [
        'bug_id', 'classification', 'classification_reason',
        'chain_steps', 'root_cause', 'root_cause_file_line',
        'cf_evidence', 'fix_description', 'confidence',
    ],
}

// ============================================================
// Prompts
// ============================================================

function buildInvestigationPrompt(bugDescription, bugId) {
    return `你是缉凶 agent — Bug 排查合同框架 v2.0。严格按合同链输出。

## Bug 描述

${bugDescription}

## 合同链（每步产出=下步门票，必须全填）

**分类** — 判定 T-Type + 依据。T-Type定义:
${T_TYPES.join('\n')}

**证据** — 复现步骤 + baseline 输出（必须可验证，含具体命令/响应）
**追踪** — 代码调用链 + Expected vs Actual 第一点（必须含 file:line）
**分析** — 根因（含 file:line）+ Counterfactual。conf < 0.8 → 标记 SUSPECT
**修复** — 修复方案。T7(NOT_A_BUG) → 不修代码，出产品建议
**验证** — pre/post diff 对比
**记录** — 完整报告 + 发现的潜在问题

## 红线（违反任一条=无效）
1. 不复现不修
2. 不 Counterfactual 不提交
3. 不测试不修
4. 3次修不好→STOP，回分类步重判
5. 修前确认部署文件

## 资源
- campus_go: f:/ClaudeFiles/campus_go/
- campus_app: f:/ClaudeFiles/campus_app/
- 生产服务器: 139.196.50.134
- Bug 模式库: f:/ClaudeFiles/bug-patterns.md

## 输出格式
必须返回结构化 JSON（按 schema），包含完整 bug report。`;
}

function buildScoringPrompt(report, groundTruth, dimension) {
    const prompts = {
        evidence: `你是独立评分 agent。评估 bug report 的【证据充分性】。

Bug: ${groundTruth.description?.substring(0, 200)}
Agent 证据: ${report.chain_steps?.evidence || 'N/A'}
Ground Truth 期望: ${groundTruth.evidence_required || '具体复现步骤 + baseline'}

评分:
- 1: 包含具体复现步骤 + 可验证的 baseline 输出
- 0: 笼统描述或无 baseline

返回 JSON: {"score": 0|1, "confidence": 0-100, "reasoning": "引用具体证据或缺失点"}`,

        root_cause: `你是独立评分 agent。评估 bug report 的【根因正确性】。

Ground Truth 根因: ${groundTruth.root_cause?.substring(0, 300) || 'N/A'}
Agent 根因: ${report.root_cause || 'N/A'}
Agent 文件引用: ${report.root_cause_file_line || 'N/A'}

评分:
- 2: 根因与 ground truth 方向一致，file:line 引用正确
- 1: 方向对但细节偏差
- 0: 根因错误

返回 JSON: {"score": 0|1|2, "confidence": 0-100, "reasoning": "一句话", "matches_gt": true|false}`,

        cf: `你是独立评分 agent。评估 bug report 的【Counterfactual 真实性】。

Agent CF: ${report.cf_evidence || 'N/A'}

评分:
- 1: CF 包含可验证的 pre/post 对比数据
- 0: 只有声明性语句（"修后OK"）

返回 JSON: {"score": 0|1, "confidence": 0-100, "reasoning": "引用具体证据或缺失点"}`,
    }
    return prompts[dimension] || ''
}

// ============================================================
// Main Workflow
// ============================================================

phase('Setup')

log(`BugHuntBench v2.0 — ${BUG_LIST.length} bugs`)

// Step 1: Load bug descriptions from filesystem
log('Loading bug descriptions...')
const bugFiles = await Bash(
    `ls ${BUGS_DIR}/B*.md | sort`,
    { description: 'List bug files' }
)
log(`Found bug files:\n${bugFiles.substring(0, 500)}`)

// Load each bug's description section (exclude ground truth)
const bugDescriptions = {}
for (const bugId of BUG_LIST) {
    const content = await Bash(
        `python -c "
import re
with open('${BUGS_DIR}/${bugId}_*.md'.replace('*', ''), 'r', encoding='utf-8') as f:
    content = f.read()
# Try glob pattern
" 2>/dev/null || echo 'FALLBACK'`,
        { description: `Read bug ${bugId}` }
    )
    // We'll parse in the Investigate phase
}

// Step 2: Discover exact bug file paths
const bugPaths = {}
for (const bugId of BUG_LIST) {
    const findResult = await Bash(
        `ls ${BUGS_DIR}/${bugId}_*.md`,
        { description: `Find bug file for ${bugId}` }
    )
    if (findResult && findResult.trim()) {
        bugPaths[bugId] = findResult.trim()
        log(`  ${bugId}: ${bugPaths[bugId]}`)
    }
}

const foundBugs = Object.keys(bugPaths)
log(`Loaded ${foundBugs.length}/${BUG_LIST.length} bugs`)

if (foundBugs.length === 0) {
    log('ERROR: No bugs found. Check BUGS_DIR path.')
    return { error: 'No bugs found' }
}

// ============================================================
// Phase: Investigate — Parallel bug investigation
// ============================================================

phase('Investigate')

log(`Spawning ${foundBugs.length} investigation agents in parallel (worktree isolation)...`)

// Build agent prompts with bug descriptions
// We use Bash to extract just the description section from each bug file
async function getBugDescription(bugId) {
    const filePath = bugPaths[bugId]
    if (!filePath) return null

    const desc = await Bash(
        `python -c "
import re
with open('${filePath}', 'r', encoding='utf-8') as f:
    content = f.read()
match = re.search(r'## Bug 描述\s*\\n(.*?)(?=## Ground Truth)', content, re.DOTALL)
if match:
    print(match.group(1).strip())
"`,
        { description: `Extract description for ${bugId}` }
    )
    return desc?.trim() || null
}

// Load all descriptions
const descriptions = {}
for (const bugId of foundBugs) {
    descriptions[bugId] = await getBugDescription(bugId)
    if (descriptions[bugId]) {
        log(`  ${bugId}: description loaded (${descriptions[bugId].length} chars)`)
    }
}

// Fan out investigations in PARALLEL
// Each agent gets: bug description + 缉凶 contract chain + worktree isolation
// Uses schema for structured output validation
const validBugs = foundBugs.filter(id => descriptions[id])
log(`Launching ${validBugs.length} parallel investigation agents...`)

const investigationResults = await parallel(
    validBugs.map(bugId => () =>
        agent(
            buildInvestigationPrompt(descriptions[bugId], bugId),
            {
                label: `investigate-${bugId}`,
                phase: 'Investigate',
                schema: BUG_REPORT_SCHEMA,
                isolation: 'worktree',
                agentType: 'debugger',
            }
        )
    )
)

// Filter out null results (skipped/failed agents)
const successfulReports = investigationResults.filter(Boolean)
log(`Investigation complete: ${successfulReports.length}/${validBugs.length} agents returned results`)

// ============================================================
// Phase: Score — Auto-score all reports
// ============================================================

phase('Score')

log('Scoring reports (L1 rules + L2 LLM judge)...')

// Step 1: Rule-based scoring (L1) via Python harness
// Write agent outputs to temp file, run Python scorer
const reportsJson = JSON.stringify(successfulReports)
const tempFile = '.claude/benchmarks/bughunt/.temp_reports.json'
await Bash(
    `python -c "
import json
with open('${tempFile}', 'w', encoding='utf-8') as f:
    f.write('''${reportsJson.replace(/'/g, "''")}''')
" 2>/dev/null || echo '{"error":"write failed"}' > ${tempFile}`,
    { description: 'Write reports to temp file' }
)

// Run Python rule-based scorer
const ruleScoresRaw = await Bash(
    `cd .claude/benchmarks/bughunt && python -c "
import json, sys
sys.path.insert(0, '.')
from bughunt_harness import parse_agent_report, load_bugs, score_by_rules
from auto_scorer import AutoScorer

# Load ground truth
bugs = {b.id: b for b in load_bugs()}

# Parse agent reports from temp file
with open('.temp_reports.json', 'r') as f:
    reports = json.load(f)

scorer = AutoScorer(mode='quick')
results = []
for r in reports:
    bug = bugs.get(r.get('bug_id', ''))
    if not bug:
        continue
    # Convert chain_steps dict
    report = AgentReport__make(bug.id, r)
    card = scorer.score(report, bug)
    results.append({
        'bug_id': bug.id,
        'gt_type': bug.type_gt,
        'classification': card.score_classification,
        'chain': card.score_chain,
        'evidence': card.score_evidence,
        'root_cause': card.score_root_cause,
        'cf': card.score_cf,
        'fix': card.score_fix,
        'trace': card.score_trace,
        'total': card.total,
        'l3': card.l3_verdict,
        'notes': card.notes,
    })

print(json.dumps(results, ensure_ascii=False))
" 2>&1`,
    { description: 'Run L1 rule-based scoring' }
)

let ruleScores = []
try {
    ruleScores = JSON.parse(ruleScoresRaw)
} catch (e) {
    log(`Rule scoring parse warning: ${e.message}`)
    ruleScores = []
}

log(`L1 rule scoring: ${ruleScores.length} bugs scored`)

// Step 2: LLM Judge scoring (L2) for subjective dimensions
log('L2 LLM judge scoring (evidence, root_cause, cf)...')

// For each report, spawn 3 judge agents per dimension (cross-model)
const judgeResults = []
for (const report of successfulReports.slice(0, 3)) {  // Limit for cost; expand in full mode
    const bugId = report.bug_id

    // Load ground truth for this bug
    const gtRaw = await Bash(
        `python -c "
import re
with open('${BUGS_DIR}/${bugId}_*.md', 'r') as f:
    content = f.read()
match = re.search(r'## Ground Truth\\s*\\n(.*)', content, re.DOTALL)
if match:
    print(match.group(1).strip()[:500])
" 2>/dev/null`,
        { description: `Load GT for ${bugId}` }
    )

    const groundTruth = {
        root_cause: gtRaw || '',
        evidence_required: '',
    }

    // Judge dimension: evidence
    const evidenceVerdicts = await parallel(
        [1, 2, 3].map(n => () =>
            agent(
                buildScoringPrompt(report, groundTruth, 'evidence'),
                {
                    label: `judge-${bugId}-evidence-${n}`,
                    phase: 'Score',
                    model: 'sonnet',  // Cross-model: use Sonnet to judge DeepSeek
                }
            )
        )
    )

    // Judge dimension: root_cause
    const rootCauseVerdicts = await parallel(
        [1, 2, 3].map(n => () =>
            agent(
                buildScoringPrompt(report, groundTruth, 'root_cause'),
                {
                    label: `judge-${bugId}-root-${n}`,
                    phase: 'Score',
                    model: 'sonnet',
                }
            )
        )
    )

    judgeResults.push({
        bug_id: bugId,
        evidence_votes: evidenceVerdicts.filter(Boolean),
        root_cause_votes: rootCauseVerdicts.filter(Boolean),
    })
}

log(`L2 judge scoring: ${judgeResults.length} bugs judged`)

// ============================================================
// Phase: Verify — L3 cross-model spot-check
// ============================================================

phase('Verify')

log('L3 spot-check verification...')

// Spawn independent verification agent (no context of original investigation)
// Checks 2 key dimensions: Counterfactual truth + Classification correctness
const l3Results = []
for (const report of successfulReports.slice(0, 2)) {  // Spot-check 2 reports
    const bugId = report.bug_id

    const l3Verdict = await agent(
        `你是独立验证 agent。检查以下 bug report 的 Phase 4(分析) 和 Phase 1(分类) 输出。

原始 bug: ${descriptions[bugId]?.substring(0, 300) || 'N/A'}

Agent 分类: ${report.classification} — ${report.classification_reason || 'N/A'}
Agent 分析: ${report.root_cause || 'N/A'}
Agent CF: ${report.cf_evidence || 'N/A'}

判定标准:
- REAL: 分析包含具体代码引用/数据/逻辑推理，有 pre/post 对比
- TEMPLATE: 格式正确但内容空洞
- WRONG: 分析有事实错误

返回 JSON: {"verdict": "REAL|TEMPLATE|WRONG", "evidence": "引用具体证据或错误点"}`,
        {
            label: `l3-verify-${bugId}`,
            phase: 'Verify',
            model: 'sonnet',
        }
    )
    l3Results.push({ bug_id: bugId, l3: l3Verdict || 'NOT_RUN' })
}

log(`L3 verification: ${l3Results.length} reports spot-checked`)

// ============================================================
// Phase: Report — Generate summary + update results
// ============================================================

phase('Report')

log('Generating benchmark report...')

// Compile all scores
const finalScores = ruleScores.map(rs => {
    const judgeResult = judgeResults.find(j => j.bug_id === rs.bug_id)
    const l3Result = l3Results.find(l => l.bug_id === rs.bug_id)

    // Merge L2 judge scores if available
    if (judgeResult) {
        // Parse judge votes for evidence
        const evidenceVotes = (judgeResult.evidence_votes || [])
            .map(v => {
                try { return JSON.parse(v)?.score || 0 } catch { return 0 }
            })
        if (evidenceVotes.length >= 2) {
            rs.evidence = Math.round(
                evidenceVotes.reduce((a, b) => a + b, 0) / evidenceVotes.length
            )
        }

        // Parse judge votes for root_cause
        const rootVotes = (judgeResult.root_cause_votes || [])
            .map(v => {
                try { return JSON.parse(v)?.score || 0 } catch { return 0 }
            })
        if (rootVotes.length >= 2) {
            rs.root_cause = Math.round(
                rootVotes.reduce((a, b) => a + b, 0) / rootVotes.length
            )
        }
    }

    // Apply L3 verdict
    if (l3Result?.l3) {
        try {
            const l3v = JSON.parse(l3Result.l3)
            rs.l3 = l3v.verdict || 'NOT_RUN'
        } catch {
            rs.l3 = String(l3Result.l3).substring(0, 20)
        }
    }

    // Recalculate total
    rs.total = (rs.classification || 0) + (rs.chain || 0) + (rs.evidence || 0) +
               (rs.root_cause || 0) + (rs.cf || 0) + (rs.fix || 0) + (rs.trace || 0)

    return rs
})

// Generate summary
const totalScore = finalScores.reduce((sum, s) => sum + (s.total || 0), 0)
const maxScore = finalScores.length * 8
const pct = maxScore > 0 ? (totalScore / maxScore * 100).toFixed(1) : '0.0'

const classCorrect = finalScores.filter(s => s.classification === 1).length
const chainComplete = finalScores.filter(s => s.chain === 1).length
const rootHit = finalScores.filter(s => s.root_cause === 2).length
const l3Real = finalScores.filter(s => s.l3 && (s.l3.includes('REAL'))).length

// Build report
const reportLines = [
    '# BugHuntBench Run Report',
    '',
    `**Date:** ${new Date().toISOString().split('T')[0]}`,
    `**Bugs:** ${finalScores.length}/${BUG_LIST.length}`,
    `**Score:** ${totalScore}/${maxScore} = ${pct}%`,
    '',
    '## Metrics',
    '',
    `| Metric | Value |`,
    `|--------|-------|`,
    `| Total Score | ${totalScore}/${maxScore} (${pct}%) |`,
    `| T-Type Correct | ${classCorrect}/${finalScores.length} |`,
    `| Chain Complete | ${chainComplete}/${finalScores.length} |`,
    `| Root Cause Hit | ${rootHit}/${finalScores.length} |`,
    `| L3 REAL/REAL* | ${l3Real}/${finalScores.length} |`,
    '',
    '## Per-Bug Scores',
    '',
    '| Bug | GT | Class | Chain | Evid | Root | CF | Fix | Trace | Total | L3 |',
    '|-----|-----|-------|-------|------|------|----|-----|-------|-------|----|',
]

for (const s of finalScores) {
    reportLines.push(
        `| ${s.bug_id} | ${s.gt_type || '-'} | ${s.classification || 0} | ${s.chain || 0} | ` +
        `${s.evidence || 0} | ${s.root_cause || 0} | ${s.cf || 0} | ${s.fix || 0} | ` +
        `${s.trace || 0} | **${s.total || 0}** | ${s.l3 || 'NOT_RUN'} |`
    )
}

// Gate check
const gateChecks = [
    { name: 'T-Type >= 60%', pass: classCorrect / finalScores.length >= 0.6 },
    { name: 'Chain >= 90%', pass: chainComplete / finalScores.length >= 0.9 },
    { name: 'Avg >= 4.0', pass: (totalScore / finalScores.length) >= 4.0 },
    { name: 'Zero L3 WRONG', pass: !finalScores.some(s => s.l3 === 'WRONG') },
]
const gatePassed = gateChecks.every(c => c.pass)

reportLines.push(
    '',
    '## Gate Check',
    '',
    ...gateChecks.map(c => `- [${c.pass ? 'x' : ' '}] ${c.name}`),
    '',
    `**Gate: ${gatePassed ? 'PASS' : 'FAIL'}**`,
)

const report = reportLines.join('\n')

// Write report to file
const reportFile = `.claude/benchmarks/bughunt/REPORT_${new Date().toISOString().split('T')[0].replace(/-/g, '')}.md`
await Bash(
    `cat > ${reportFile} << 'REPORT_EOF'
${report}
REPORT_EOF`,
    { description: 'Write benchmark report' }
)

log(`Report written to: ${reportFile}`)
log(`\n${report}`)

// Return structured results
return {
    total_score: totalScore,
    max_score: maxScore,
    percentage: parseFloat(pct),
    bugs_run: finalScores.length,
    bugs_total: BUG_LIST.length,
    gate: gatePassed ? 'PASS' : 'FAIL',
    scores: finalScores,
    report_file: reportFile,
}
