export const meta = {
    name: 'GEPA 反射优化',
    description: 'DSPy GEPA-style reflection: Teacher (Sonnet) analyzes T2 failures → suggests skill improvements.',
    phases: [
        { title: 'Analyze', detail: 'Teacher analyzes c4=0 failure patterns' },
        { title: 'Improve', detail: 'Teacher generates skill improvements' },
    ],
}

// Failures collected from 6 T2/T3 runs where c4=0 (root cause wrong)
const FAILURES = [
    {
        bug:'B03', runs:2,
        desc:'campus_go college_admin 有时能看到并操作其他学院的活动。跟学院名有关。',
        gt:'T2: strings.Contains() partial match. college="计算机" matches "计算机(师范)"—substring match bypasses college scope.',
        agentPattern:'Agent claimed SQL query has NO college filter at all. But GT says filter EXISTS but uses strings.Contains causing partial match.',
        judgeReason:'方向不一致。Agent说完全缺失college过滤，GT说过滤存在但有缺陷(strings.Contains部分匹配)。两者指向相反方向。',
    },
    {
        bug:'B05', runs:5,
        desc:'campus_go JWT token 刷新昨天能用今天全401。代码没改，服务器重启过。',
        gt:'T4: nginx proxy_pass port 9500 → 9501. After restart, nginx config reverted to old port. Not a code bug—an infra/config bug.',
        agentPattern:'Agent repeatedly looks at DB schema, JWT_SECRET, refresh_token_hash—all code/data issues. Never checks nginx config or proxy_pass port.',
        judgeReason:'方向完全错误。GT指向nginx端口配置问题，Agent指向数据库/密钥问题。每次agent都去查代码而不是查配置。',
    },
    {
        bug:'B09', runs:4,
        desc:'Python 后端积分更新偶尔不生效。有时刷新还是旧的。再刷一次对了。',
        gt:'T1: Missing await on async function call. update_user_points() is async but called without await → coroutine never executes.',
        agentPattern:'Agent sometimes finds wrong root cause: nginx port issue (confused with B05), DB transaction issue, or "denormalized column" theory.',
        judgeReason:'方向不一致。GT说async/await协程问题(Python)，Agent指向nginx端口或数据库事务。完全不同的技术栈。',
    },
]

phase('Analyze')
log(`GEPA Teacher analyzes ${FAILURES.length} failure patterns from ${FAILURES.reduce((a,f)=>a+f.runs,0)} runs...`)

const analysisPrompt = `你是 DSPy GEPA 反射优化器。分析缉凶 skill 在以下 bug 上的系统性失败模式。

每个失败 = agent 根因方向完全偏离 GT。你的任务: 找出缉凶 skill 的哪条指令/什么缺失导致了这些系统性误判。

${FAILURES.map(f => `
### ${f.bug} (${f.runs} 次失败)
Bug: ${f.desc}
GT根因: ${f.gt}
Agent反复犯的错误: ${f.agentPattern}
Judge评语: ${f.judgeReason}
`).join('')}

请分析:
1. 这些失败有什么共同模式？
2. 缉凶 skill 缺少什么指令导致了这些模式？
3. 应该增加/修改什么具体规则来防止这些失败？

输出JSON:
{
  "patterns": ["模式1", "模式2"],
  "root_causes": ["根因1", "根因2"],
  "improvements": [
    {"target": "致命误判表", "new_rule": "F10: ...", "reason": "..."},
    {"target": "分类决策流", "change": "...", "reason": "..."},
  ]
}`

const analysis = await agent(analysisPrompt, {label:'gepa-teacher', phase:'Analyze', model:'sonnet'})

let gepaResult = {patterns:[], improvements:[]}
try {
    const text = typeof analysis === 'string' ? analysis : JSON.stringify(analysis)
    const m = text.match(/\{[\s\S]*"improvements"[\s\S]*\}/)
    if (m) { try { gepaResult = JSON.parse(m[0]) } catch {} }
} catch(e) { log(`Parse error: ${e}`) }

phase('Improve')
log('')
log('GEPA 发现:')
log(`  Patterns: ${(gepaResult.patterns||[]).join(' | ')}`)
log(`  Root causes: ${(gepaResult.root_causes||[]).join(' | ')}`)
log('')
log('  Suggested improvements:')
for (const imp of (gepaResult.improvements||[])) {
    log(`  [${imp.target}] ${imp.new_rule||imp.change}`)
    log(`    Reason: ${imp.reason}`)
}

return gepaResult
