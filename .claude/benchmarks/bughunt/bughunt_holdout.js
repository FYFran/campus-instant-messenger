export const meta = {
    name: '试剑石 Holdout',
    description: 'Hold-out 验证 — B26-B30 (从未参与优化)。检测过拟合。',
    phases: [
        { title: 'Classify', detail: '1 agent classifies 5 hold-out bugs' },
        { title: 'Score', detail: 'T-Type vs GT' },
    ],
}

const BUGS = [
    {id:'B26',d:'campus_go 在特定条件下处理不带Authorization头的请求时发生panic。日志显示 nil pointer dereference 发生在JWT中间件。正常带token的请求没问题。',t:'T0',l:'Go'},
    {id:'B27',d:'TokenLine平台：调用AI API时扣费发生在API调用之前。当AI API超时或失败时，token已被扣除但用户没有收到任何回复。余额减少但没有AI回复。每次API失败都会触发。',t:'T3',l:'Python'},
    {id:'B28',d:'TokenLine平台充值订单偶尔一直显示处理中(processing)，不会自动变为已完成或失败。用户已完成支付(微信/支付宝回调已收到)但订单状态没更新。钱付了token没到账。',t:'T5',l:'Python'},
    {id:'B29',d:'安全审查报告标记 campus_go 密码哈希使用了不安全的bcrypt cost值。auth.go中 bcrypt.DefaultCost 值为10，而OWASP 2026推荐最低cost为12。审查者认为密码哈希易被暴力破解。',t:'T7',l:'Go'},
    {id:'B30',d:'campus_go WebSocket实时推送偶尔丢消息。用户收到新通知推送时，有时WebSocket连接正常但收不到消息。刷新页面(重新连接)后消息又出现了。大约10条消息丢1-2条。',t:'T1',l:'Go'},
]

function buildClassifyPrompt() {
    let p = `你是缉凶 agent。仅做分类——不调查代码。5 个 hold-out bug，每个判 T-Type。

分类规则:
- STOP 先想 bug 的深层因果结构（什么变了？什么时候变？谁受影响？）
- T0: 每次必现 crash/panic/500。必须伴随报错
- T1: 同一操作有时正常有时异常、刷新后又正常 → 结果不一致
- T2: 换一个参数值就正常了 → 不同输入不同结果
- T3: T1/T2/T4/T5 全排除后才考虑。数据一致地错、没报错没crash
- T4: 代码没改、昨天能用、重启后 → 查环境/配置
- T5: 正常输入→卡在中间状态回不来 → 状态转移失败
- T6: 本机正常 CI/其他环境异常
- T7: 读代码发现行为符合产品设计 → NOT_A_BUG

致命误判: F1"偶尔+刷新好了"=T1非T3 F2"某些输入触发"=T2非T3 F3"一直pending"=T5非T3

每个 bug 返回: {bug_id, classification (T0-T7), classification_reason, confidence (0-100)}
全部 5 bug 的 JSON 数组。
`
    for (const b of BUGS) {
        p += `\nBug ${b.id} (${b.l}): ${b.d}`
    }
    p += `\n\n返回: [{"bug_id":"Bxx","classification":"Tx","classification_reason":"...","confidence":xx}, ...]`
    return p
}

phase('Classify')
log('1 agent classifies 5 hold-out bugs...')

const output = await agent(buildClassifyPrompt(), {label:'classify-holdout', phase:'Classify', agentType:'debugger'})

let classifications = {}
try {
    const text = typeof output === 'string' ? output : JSON.stringify(output)
    let arr = null
    const match = text.match(/\[[\s\S]*\]/)
    if (match) { try { arr = JSON.parse(match[0]) } catch {} }
    if (!arr) {
        const cm = text.match(/```(?:json)?\s*([\s\S]*?)```/)
        if (cm) { const cm2 = cm[1].match(/\[[\s\S]*\]/); if (cm2) try { arr = JSON.parse(cm2[0]) } catch {} }
    }
    if (!arr) {
        arr = []
        const entries = text.match(/\{[^}]+\}/g)
        if (entries) { for (const e of entries) { try { arr.push(JSON.parse(e)) } catch {} } }
    }
    if (arr) {
        for (const c of arr) {
            if (!c.bug_id) continue
            classifications[c.bug_id] = { classification: (c.classification||'').trim().substring(0,2), reason: (c.classification_reason||'').substring(0,80) }
        }
    }
    if (Object.keys(classifications).length===0) log(`Parse failed. Raw: ${text.substring(0,300)}`)
} catch(e) { log(`Parse error: ${e}`) }

phase('Score')
log('Bug | Agent | GT | OK? | Reason')
log('----|-------|-----|-----|------')
let correct = 0
for (const b of BUGS) {
    const c = classifications[b.id]
    const at = c ? c.classification : '?'
    const ok = at === b.t
    if (ok) correct++
    log(` ${b.id} | ${at} | ${b.t} | ${ok?'OK':'FAIL'} | ${c?c.reason:'no output'}`)
}
const pct = (correct/BUGS.length*100).toFixed(0)
log('')
log(`Hold-out T-Type: ${correct}/${BUGS.length} (${pct}%)`)
log(`In-sample T-Type: 10/10 (100%)`)
log(`Overfit gap: ${100-parseInt(pct)}pp`)

return { total:BUGS.length, correct, pct:parseInt(pct), classifications, overfit_gap: 100-parseInt(pct) }
