export const meta = {
    name: '试剑石 T0',
    description: 'Tier 0 — 纯规则评分 ($0, <1s)。c1+c2+c6+c7 4维规则评分，无LLM。每次save/commit跑。',
    phases: [
        { title: 'Score', detail: 'Pure rule-based scoring (4 dimensions)' },
    ],
}

// T0 = rule-only quality gate. No LLM. Runs on T2-style report output.
// Usage: pipe T2 agent reports → T0 scores what it can without AI judge.

const BUGS = [
    {id:'B01',t:'T0'},{id:'B02',t:'T1'},{id:'B03',t:'T2'},{id:'B04',t:'T3'},{id:'B05',t:'T4'},
    {id:'B06',t:'T5'},{id:'B07',t:'T6'},{id:'B08',t:'T7'},{id:'B09',t:'T1'},{id:'B10',t:'T3'},
]

// Simulate: read reports from args or hard-coded test data
// In production, reports come from T2 agent output
const reports = args && args.reports ? args.reports : {}

function ruleScore(bug, report) {
    if (!report || !report.root_cause) {
        return {bug_id: bug.id, gt_type: bug.t, agent_type: '?', total: 0, c1: 0, c2: 0, c6: 0, c7: 0, status: 'NO_DATA'}
    }

    const at = (report.classification || '').trim().substring(0, 2)

    // c1: T-Type exact match (rule)
    const c1 = at === bug.t ? 1 : 0

    // c2: chain completeness — all 6 fields must be present and non-trivial
    const fields = ['evidence', 'trace', 'root_cause', 'cf_evidence', 'fix_description']
    const allPresent = fields.every(f => (report[f] || '').length > 10)
    const c2 = allPresent ? 1 : 0

    // c6: fix quality — fix_description must be substantive (>15 chars, not template)
    const fixLen = (report.fix_description || '').length
    const isTemplate = /^(修复|fix|修改|change|update|已修复)$/i.test((report.fix_description || '').trim())
    const c6 = (fixLen > 15 && !isTemplate) ? 1 : 0

    // c7: trajectory quality (= c2, proxy for whether agent followed the chain)
    const c7 = c2

    const total = c1 + c2 + c6 + c7
    let status = 'PASS'
    if (total <= 1) status = 'FAIL'
    else if (total <= 2) status = 'WARN'

    return {bug_id: bug.id, gt_type: bug.t, agent_type: at, total, c1, c2, c6, c7, status}
}

phase('Score')
log('T0 Rule-Based Quality Gate (no LLM, $0)')
log('Dimensions: c1(T-Type) + c2(Chain) + c6(Fix) + c7(Trajectory) = 4pt max')
log('')

// If no reports provided, run a diagnostic
if (Object.keys(reports).length === 0) {
    log('No reports provided. T0 needs agent report data to score.')
    log('Usage: pipe T2 agent output → T0 for rule-based dimensions.')
    log('')
    log('T0 diagnostic — checking bugset integrity...')

    // Check bugset files exist
    const fs = require('fs')
    const path = require('path')
    const bugsetDir = 'f:/ClaudeFiles/.claude/benchmarks/bughunt/bugset'

    let complete = 0, incomplete = 0
    for (const b of BUGS) {
        const dp = path.join(bugsetDir, b.id, 'desc.md')
        const tp = path.join(bugsetDir, b.id, 'truth.md')
        const hasBoth = fs.existsSync(dp) && fs.existsSync(tp)
        if (hasBoth) complete++
        else incomplete++
    }

    log(`Bugset integrity: ${complete}/${BUGS.length} complete, ${incomplete} missing`)
    log('T0 ready for report input.')
    log(`Cost: $0 (no LLM)`)

    return {
        mode: 'diagnostic',
        bugsetIntegrity: {complete, incomplete, total: BUGS.length},
        cost: '$0.00',
    }
}

const scores = BUGS.map(b => ruleScore(b, reports[b.id] || null))
const validScores = scores.filter(s => s.status !== 'NO_DATA')
const totalScore = validScores.reduce((a, s) => a + s.total, 0)
const maxScore = validScores.length * 4
const pct = maxScore > 0 ? (totalScore / maxScore * 100).toFixed(0) : 'N/A'

log('Bug | GT | Agent | c1 | c2 | c6 | c7 | Total | Status')
log('----|----|-------|----|----|----|----|-------|------')
for (const s of scores) {
    log(` ${s.bug_id} | ${s.gt_type} | ${s.agent_type} | ${s.c1} | ${s.c2} | ${s.c6} | ${s.c7} | ${s.total}/4 | ${s.status}`)
}
log('')
log(`Rule Score: ${totalScore}/${maxScore} (${pct}%)`)
log('Note: c3(evidence)+c4(root_cause)+c5(CF) require LLM judge → Tier 1+')
log(`Cost: $0 (pure rules, <1ms)`)

return {
    total: totalScore,
    max: maxScore,
    pct: maxScore > 0 ? parseFloat(pct) : 0,
    scores,
    cost: '$0.00',
}
