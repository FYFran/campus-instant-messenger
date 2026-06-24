export const meta = {
    name: '试剑石 Mine',
    description: 'Git 挖矿 — 从 git log 真实 fix commits 提取→脱敏→泛化→生成新 benchmark bug。',
    phases: [
        { title: 'Scan', detail: 'Scan git log for fix commits' },
        { title: 'Extract', detail: 'LLM reads diffs, extracts bug patterns' },
        { title: 'Generate', detail: 'Generate desc.md + truth.md for each candidate' },
    ],
}

// Commits to mine (from earlier git log scan)
const CANDIDATES = [
    {hash:'d74c7a8',msg:'fix: 3 api-tester bugs — stats JOIN, empty login 400, emoji rejection'},
    {hash:'aabea3c',msg:'fix: registration TOCTOU race + JWT rotation + gitleaks + dead code'},
    {hash:'b0a13bb',msg:'v2.10.1: OTP防爆修复 — checkCooldown key错误导致保护未触发'},
    {hash:'4acbf62',msg:'fix: login timing leak + rate limiters on unprotected endpoints'},
    {hash:'fe647e9',msg:'fix: chat broken — currentLang undefined caused send() to fail every request'},
    {hash:'61ffff3',msg:'fix: extractContent now captures reasoning_content — prevents empty AI responses'},
    {hash:'6b1e814',msg:'v2.5: 支付竞态修复+基础设施加固'},
    {hash:'959db60',msg:'fix: file upload 415 — requireJSON blocked multipart form-data'},
]

phase('Scan')
log(`Scanning ${CANDIDATES.length} candidate fix commits for bug extraction...`)

// Build git diff extraction prompt
function buildExtractPrompt(c) {
    return `Analyze this git commit from a production codebase. Extract the underlying bug pattern that can become a benchmark test case.

Commit: ${c.hash} — ${c.msg}

Task:
1. Run: git show ${c.hash} --stat → understand what files changed
2. Run: git show ${c.hash} -- "*.go" "*.py" → read the actual diff
3. Understand the ROOT CAUSE of the bug being fixed
4. Generalize it into a benchmark bug: remove project-specific details, keep the pattern

Then output a JSON bug definition:
{
  "bug_id": "M01",
  "title": "short descriptive title",
  "description": "Generalized bug description (2-3 sentences, no specific file names unless essential). Should be what a USER would report or a QA would find. Remove project names.",
  "t_type": "T0|T1|T2|T3|T4|T5|T6|T7",
  "language": "Go|Python|Mixed|Flutter",
  "root_cause_summary": "what the real fix was (for truth.md)",
  "difficulty": "easy|medium|hard",
  "extractable": true/false  // false if too project-specific
}

T-Type guide:
- T0: every time crash/500 with error
- T1: intermittent/race/timing
- T2: depends on specific input values
- T3: silent data error, no crash
- T4: worked before, broke after env change
- T5: state machine stuck
- T6: environment-specific (OS/version)
- T7: NOT_A_BUG / by design

Only output extractable=true bugs. If the fix is too trivial or too project-specific, set extractable=false.`
}

// ============================================================
phase('Extract')
log(`Extracting bug patterns from ${CANDIDATES.length} commits...`)

const extracted = await parallel(
    CANDIDATES.map(c => () => agent(buildExtractPrompt(c), {
        label: 'mine-'+c.hash.substring(0,7),
        phase: 'Extract',
    }))
)

// ============================================================
phase('Generate')
log('Generating desc.md + truth.md for extractable bugs...')

let bugCount = 0
const generated = []

for (let i = 0; i < CANDIDATES.length; i++) {
    const c = CANDIDATES[i]
    const raw = extracted[i]
    if (!raw) { log(`  ${c.hash.substring(0,7)}: FAIL (no output)`); continue }

    try {
        const text = typeof raw === 'string' ? raw : JSON.stringify(raw)
        // Try to parse JSON from output
        let bug = null
        const m = text.match(/\{[\s\S]*"bug_id"[\s\S]*\}/)
        if (m) { try { bug = JSON.parse(m[0]) } catch {} }
        if (!bug) {
            const arr = text.match(/\[[\s\S]*\]/)
            if (arr) { try { const a = JSON.parse(arr[0]); if (a.length) bug = a[0] } catch {} }
        }

        if (!bug || !bug.extractable) {
            log(`  ${c.hash.substring(0,7)}: SKIP (not extractable or parse fail)`)
            continue
        }

        bugCount++
        const bid = `M${String(bugCount).padStart(2,'0')}`
        log(`  ${bid}: ${bug.title} [${bug.t_type}] ${bug.difficulty}`)

        generated.push({
            bug_id: bid,
            source_commit: c.hash,
            title: bug.title,
            description: bug.description,
            t_type: bug.t_type,
            language: bug.language,
            root_cause: bug.root_cause_summary,
            difficulty: bug.difficulty,
        })
    } catch(e) {
        log(`  ${c.hash.substring(0,7)}: ERROR ${e}`)
    }
}

log('')
log(`============================================`)
log(`Mined: ${generated.length}/${CANDIDATES.length} extractable bugs`)
log('')
log('Next steps:')
log(`1. Review ${generated.length} candidates → pick best 5-10`)
log('2. Write desc.md + truth.md to bugset/M01-Mxx/')
log('3. Add to bughunt_t1_full.js BUGS array')
log('4. Run T1_full → verify new bugs classify correctly')
log('============================================')

return {
    scanned: CANDIDATES.length,
    extracted: generated.length,
    bugs: generated,
    cost: `~$0.${CANDIDATES.length * 3}`,
}
