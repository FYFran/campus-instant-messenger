export const meta = {
    name: '试剑石 T1',
    description: 'Tier 1 — 分类-only ($0.01, <30s)。1 agent 分类 10 bugs，验证 T-Type。',
    phases: [
        { title: 'Classify', detail: '1 agent classifies all 10 bugs' },
        { title: 'Score', detail: 'Rule-based T-Type matching' },
    ],
}

const T = 'T0=稳定复现(每次都) T1=竞态时序(偶尔,同一操作结果不一致) T2=多因素(需≥2条件,换输入结果不同) T3=静默数据(T1/T2/T5已排除) T4=昨天还好(代码没改环境变了) T5=状态机卡住 T6=特定环境(本机vsCI/Docker/OS) T7=NOT_A_BUG(符合设计)'

const BUGS = [
    {id:'B01',d:'campus_go 活动列表 API /api/activities 在数据库为空时返回 500 错误。有活动时正常。',t:'T0',l:'Go'},
    {id:'B02',d:'campus_go 报名接口偶尔出现同一学生报了两次名。约每20-30次一次。',t:'T1',l:'Go'},
    {id:'B03',d:'campus_go college_admin 有时能看到并操作其他学院的活动。跟学院名有关。',t:'T2',l:'Go'},
    {id:'B04',d:'campus_go 学生志愿时长统计页面总时长偶尔比实际短。没报错没crash，数字不对。',t:'T3',l:'Python'},
    {id:'B05',d:'campus_go JWT token 刷新昨天能用今天全401。代码没改，服务器重启过。',t:'T4',l:'Go'},
    {id:'B06',d:'campus_go 活动报名后状态一直pending不会变confirmed。审批流程是自动的。学生等2小时状态没变。',t:'T5',l:'Go'},
    {id:'B07',d:'campus_go 测试本机go1.22全通但CI go1.23 TestListActivities panic nil deref。',t:'T6',l:'Mixed'},
    {id:'B08',d:'用户反馈 campus_go 我的报名列表只显示已确认活动不显示待审批。用户认为这是bug。',t:'T7',l:'Go'},
    {id:'B09',d:'Python 后端积分更新偶尔不生效。有时刷新还是旧的。再刷一次对了。不是每次都发生。',t:'T1',l:'Python'},
    {id:'B10',d:'campus_go 活动列表越来越慢。50个活动100ms，200个需3秒。没报错API正常200。',t:'T3',l:'Go'},
]

function buildClassifyPrompt() {
    let p = `你是缉凶 agent。仅做分类——不调查代码。10 个 bug，每个判 T-Type。

分类规则:
- STOP 先想 bug 的深层因果结构（什么变了？什么时候变？谁受影响？），不要匹配关键词
- T0: 每次必现、稳定复现
- T1: 同一操作有时正常有时异常、刷新后又正常 → 结果不一致
- T2: 换一个参数值就正常了 → 不同输入不同结果
- T3: T1/T2/T4/T5 全排除后才考虑。数据一致地错、没报错没crash
- T4: 代码没改、昨天能用、重启后 → 查环境/配置
- T5: 正常输入→卡在中间状态回不来 → 状态转移失败
- T6: 本机正常 CI/其他环境异常 → 环境差异
- T7: 读代码发现行为符合产品设计 → NOT_A_BUG

致命误判（从真实失败提取）:
- F1: "偶尔不生效"+"刷新又好了" → T1 不是 T3（T3要求每次一致地错）
- F2: "某些学院名能看到某些不能" → T2 不是 T3（T3要求与输入无关）
- F3: "一直pending不变" → T5 不是 T3（T3是数据错，T5是状态卡住）

结构排除: 判 T3 前写出 ≥2 个证据证明 T1/T2/T5 不成立。缺 = 不能选 T3。

每个 bug 返回:
{bug_id, classification (T0-T7), classification_reason ("为什么T_X不是T_Y? 致命误判检查?"), confidence (0-100)}

全部 10 bug 的 JSON 数组。
`
    for (const b of BUGS) {
        p += `\nBug ${b.id} (${b.l}): ${b.d}`
    }
    p += `\n\n返回: [{"bug_id":"Bxx","classification":"Tx","classification_reason":"...","confidence":xx}, ...]`
    return p
}

// ============================================================
phase('Classify')
log('1 agent classifies all 10 bugs (T-Type only, ~$0.01)...')

const classifyOutput = await agent(buildClassifyPrompt(), {
    label: 'classify-all',
    phase: 'Classify',
})

// Parse batch results
let classifications = {}
try {
    const text = typeof classifyOutput === 'string' ? classifyOutput : JSON.stringify(classifyOutput)
    const match = text.match(/\[[\s\S]*\]/)
    if (match) {
        const arr = JSON.parse(match[0])
        for (const c of arr) {
            classifications[c.bug_id] = {
                classification: (c.classification || '').trim().substring(0, 2),
                reason: (c.classification_reason || '').substring(0, 80),
                confidence: c.confidence || 0,
            }
        }
    }
} catch (e) {
    log(`Parse error: ${e}`)
}

// ============================================================
phase('Score')
log('Bug | Agent | GT | OK? | Reason')
log('----|-------|-----|-----|------')
let correct = 0
let total = 0
for (const b of BUGS) {
    const c = classifications[b.id]
    const agentType = c ? c.classification : '?'
    const ok = agentType === b.t
    if (ok) correct++
    total++
    log(` ${b.id} | ${agentType} | ${b.t} | ${ok ? 'OK' : 'FAIL'} | ${c ? c.reason : 'no output'}`)
}
log('')
log(`T-Type: ${correct}/${total} (${(correct/total*100).toFixed(0)}%)`)
log(`Cost: 1 agent (~$0.01) vs Tier 3 full workflow (46 agents, ~$5) = 99.8% savings`)

return {
    total, correct,
    pct: parseFloat((correct/total*100).toFixed(0)),
    classifications,
    cost: '~$0.01',
}
