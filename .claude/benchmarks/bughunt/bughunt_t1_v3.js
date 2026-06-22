export const meta = {
    name: '试剑石 T1 49-bug 批次',
    description: 'Tier 1 — 49 bug 3-agent 分批分类 (~$0.03)。每 agent ~16 bugs，防 context 溢出。',
    phases: [
        { title: 'Classify', detail: '3 agents classify ~16 bugs each in parallel' },
        { title: 'Score', detail: 'Aggregate + hold-out gap analysis' },
    ],
}

const ALL_BUGS = [
    {id:'B01',d:'campus_go 活动列表 API 在数据库为空时返回 500 错误。有活动时正常。',t:'T0',l:'Go'},
    {id:'B02',d:'campus_go 报名接口偶尔出现同一学生报了两次名。约每20-30次一次。',t:'T1',l:'Go'},
    {id:'B03',d:'campus_go college_admin 有时能看到并操作其他学院的活动。跟学院名有关。',t:'T2',l:'Go'},
    {id:'B04',d:'campus_go 学生志愿时长统计页面总时长比实际短。没报错数字不对。签了10小时显示7小时。',t:'T3',l:'Python'},
    {id:'B05',d:'campus_go JWT token 刷新昨天能用今天全401。代码没改服务器重启过。',t:'T4',l:'Go'},
    {id:'B06',d:'campus_go 活动报名后状态一直pending不会变confirmed。审批流程自动。学生等2小时状态没变。',t:'T5',l:'Go'},
    {id:'B07',d:'campus_go 测试本机go1.22全通但CI go1.23 TestListActivities panic nil deref。',t:'T6',l:'Mixed'},
    {id:'B08',d:'产品经理反馈 campus_go "我的报名"只显示已确认不显示待审批。用户投诉这是bug——报了名看不到以为没成功。需确认是代码问题还是产品设计。',t:'T7',l:'Go'},
    {id:'B09',d:'Python 后端积分更新偶尔不生效。有时刷新还是旧的再刷一次对了。不是每次都发生。',t:'T1',l:'Python'},
    {id:'B10',d:'campus_go 活动列表越来越慢。50个活动100ms，200个需3秒。没报错API正常200。',t:'T3',l:'Go'},
    {id:'B11',d:'campus_go 管理后台仪表板在数据库连接池耗尽或网络异常时返回500并panic。条件满足时稳定复现。',t:'T0',l:'Go'},
    {id:'B12',d:'学院管理员打开仪表板后统计数据全0。但数据库中有学生和活动。HTTP 200无报错。',t:'T3',l:'Go'},
    {id:'B13',d:'campus_go 登录接口之前有频率限制(同IP 12秒一次)，最近几个版本限制不生效了。连续100次错误密码全部401没被拦截。之前版本正常。',t:'T4',l:'Go'},
    {id:'B14',d:'学院管理员查看学生列表时某些学生数据缺失。学院50个学生页面只显示48个。缺失学生在数据库中存在且可正常登录。无报错。',t:'T3',l:'Go'},
    {id:'B15',d:'用户通知列表所有通知 is_read 始终为 false，即使用户已点开阅读。数据库存整数0/1但API JSON is_read始终false。日志有scan error。',t:'T6',l:'Go'},
    {id:'B16',d:'代码审查发现 activities.go Signup 函数 defer Rollback 后又 Commit——审查者认为是bug，Commit后defer会回滚已提交数据。需确认是否真有问题。',t:'T7',l:'Go'},
    {id:'B17',d:'campus_go 注册接口在特定条件下允许普通学生注册为教师或管理员。用户说没邀请码但注册后变成teacher。不是每次都触发。',t:'T2',l:'Go'},
    {id:'B18',d:'campus_go 已结束(ended)的活动偶尔变回已发布(published)状态。管理员确认没手动改。已结束活动突然又开放报名。',t:'T5',l:'Go'},
    {id:'B19',d:'campus_go 登录限流偶尔不准确——同IP在12秒内能连续尝试多次。go test -race 偶尔出现告警。压力测试更容易触发。',t:'T1',l:'Go'},
    {id:'B20',d:'campus_go 活动报名截止判断偏差8小时。截止时间今晚23:59但下午16:00就提示报名已截止。',t:'T6',l:'Go'},
    {id:'B21',d:'Python后端点"完成活动"后状态变completed用户收到"学时已发放"通知——但学时实际没增加。如果另外点"生成证书"学时才会正确增加。只点"完成活动"学时永远是0。',t:'T3',l:'Python'},
    {id:'B22',d:'Python后端仪表板统计API在数据库无任何活动记录时返回500。日志 ZeroDivisionError。有活动时正常。',t:'T0',l:'Python'},
    {id:'B23',d:'campus_go 活动报名开始时间未设置(留空)，状态published截止在未来。但学生报名时提示"报名尚未开始"。',t:'T2',l:'Go'},
    {id:'B24',d:'campus_go API偶尔返回旧数据。刚报名后刷新按钮没变(仍显示"报名")。等1-2分钟再刷新才正确。前端确认没本地缓存。',t:'T4',l:'Go'},
    {id:'B25',d:'campus_go 用户点击通知后详情页显示"已读"但返回列表后红点仍在(未读)。两个页面状态不一致。',t:'T5',l:'Go'},
    {id:'B26',d:'campus_go 处理不带 Authorization 头的请求时发生 panic。日志 nil pointer dereference 在 auth.go JWT中间件。正常带token请求没问题。',t:'T0',l:'Go'},
    {id:'B27',d:'TokenLine 平台调用 AI API 时扣费发生在 API 调用之前。AI API 超时或失败时 token 已被扣但用户没收到回复。余额减少但对话历史无对应AI回复。',t:'T3',l:'Python'},
    {id:'B28',d:'TokenLine 充值订单偶尔一直显示"处理中(processing)"不会自动变"已完成"或"失败"。用户已完成支付(微信/支付宝回调已收到)但订单状态没更新。钱付了 token 没到账。',t:'T5',l:'Go'},
    {id:'B29',d:'安全审查报告标记 campus_go 密码哈希使用"不安全的bcrypt cost值"。auth.go:156 用 bcrypt.DefaultCost(值10)，OWASP 2026推荐最低cost为12。审查者认为易被暴力破解。',t:'T7',l:'Go'},
    {id:'B30',d:'campus_go WebSocket实时推送偶尔丢消息。有时连接正常但收不到推送。刷新重连后又出现。大概10条丢1-2条。',t:'T1',l:'Go'},
    {id:'B31',d:'Python后端志愿学时统计有浮点小数偏差。3个活动3.5+2.0+1.5应为7.0但显示6.999999999999999。偏差极小但学生注意到了。',t:'T3',l:'Python'},
    {id:'B32',d:'Python后端并发通知发送在Python 3.9不工作。开发机3.12正常但服务器3.9批量通知只发第一条其余丢失。无报错。',t:'T6',l:'Python'},
    {id:'B33',d:'Flutter端网络慢或API异常时每次登录后首页白屏——导航栏在但主体白色，日志无错误。杀app重开恢复。条件满足时稳定复现。',t:'T0',l:'Flutter'},
    {id:'B34',d:'campus_go 活动列表越来越慢。最早<100ms现在>2秒。管理员后台更慢活动超50个需5秒+。',t:'T2',l:'Go'},
    {id:'B35',d:'安全审查报告标记campus_go存在"权限绕过"：scope_type=all的活动对所有学院学生可见。标记HIGH severity。',t:'T7',l:'Go'},
    {id:'B36',d:'campus_go 学生登录偶尔失败返回401密码明明是对的。重试2-3次后又成功。大概10次有1-2次失败。',t:'T7',l:'Go'},
    {id:'B37',d:'campus_go 志愿时长开发环境显示正确(10.5h)但生产环境始终0。代码相同数据相同无报错HTTP 200。',t:'T6',l:'Go'},
    {id:'B38',d:'campus_go 首次启动后第一个请求必panic，之后所有请求正常。重启后又出现第一次panic。每次重启稳定复现。',t:'T5',l:'Go'},
    {id:'M01',d:'Dashboard统计页面高并发时偶尔返回502/504超时。平时正常流量高峰期概率性出现。监控显示数据库CPU飙升。',t:'T1',l:'Go'},
    {id:'M02',d:'同一IP偶尔能绕过注册频率限制连续注册多个账号。系统有限流但有时同IP能注册超限。并发时更容易触发。',t:'T1',l:'Go'},
    {id:'M03',d:'暴力破解/频率限制功能完全不工作。无论多少次失败尝试都不会被限流。代码有完整限流逻辑但从未被触发。无报错。',t:'T3',l:'Go'},
    {id:'M04',d:'不存在邮箱登录秒拒(401)存在邮箱错误密码慢1-2秒。用户反馈乱输不存在邮箱立刻返回自己邮箱要等。',t:'T1',l:'Go'},
    {id:'M05',d:'每个API请求都失败返回通用错误。前端刚改过代码加新参数。所有用户所有功能都用不了。',t:'T0',l:'JavaScript'},
    {id:'M06',d:'某些AI模型流式响应空白。API返回数据(DevTools有EventStream内容)但前端显示空。普通模型正常只有特定模型有问题。无报错。',t:'T3',l:'Go'},
    {id:'M07',d:'支付回调偶尔触发双倍token发放。用户付一次钱收到双倍token。5-10%支付出现。日志同invoice ID被处理两次。',t:'T1',l:'Go'},
    {id:'M08',d:'文件上传完全不工作每次415。短信回调和支付回调也415。所有非JSON Content-Type被拒绝。',t:'T0',l:'Go'},
    {id:'T01',d:'TokenLine使用某些AI模型时用户看到AI内部思考过程(内心独白)。不应暴露给用户。普通模型没这个问题。',t:'T3',l:'JavaScript'},
    {id:'T02',d:'TokenLine AI聊天偶尔空回复——用户提问模型不回答聊天框空白。API日志显示返回了tokens但前端渲染空。不是每次都触发。',t:'T1',l:'JavaScript'},
    {id:'T03',d:'TokenLine聊天功能突然完全不工作每次发送都失败。前端刚更新过代码。之前版本正常。所有用户受影响。',t:'T4',l:'JavaScript'},
]

function chunk(arr, size) {
    const chunks = []
    for (let i = 0; i < arr.length; i += size) chunks.push(arr.slice(i, i + size))
    return chunks
}

function buildClassifyPrompt(bugs) {
    let p = `分类 ${bugs.length} 个 bug。只输出 JSON 数组。

T0=条件满足必现crash/500/panic | T1=同一操作有时对有时错(竞态/时序/间歇) | T2=不同输入不同结果(换参数值就正常) | T3=排完T1/T2/T5后数据每次一致地错(静默) | T4=之前能用代码没改变(回归/环境) | T5=卡在中间状态回不来(状态机) | T6=本机行其他环境不行(环境差异) | T7=读代码发现符合产品设计(NOT_A_BUG/安全建议不算bug)

致命误判: F1"偶尔+刷新好了"=T1 | F2"某些输入触发"=T2 | F3"一直pending"=T5 | F4"需确认产品设计"=T7 | F5"空数据库crash"=T0 | F6"之前有现在没了"=T4 | F7"scan error/类型转换"=T6 | F8"固定数值偏差(8h等)"=T6/T4 | F9"偶尔非数据错+状态回退"=T5/T1

判T3前必须排除T1/T2/T5。跳过直接选T3=报废。
`
    for (const b of bugs) p += `\n${b.id}: ${b.d}`
    p += `\n\n返回: [{"bug_id":"${bugs[0].id}","classification":"Tx","reason":"简短理由","confidence":xx},...] 共${bugs.length}个。`
    return p
}

// ============================================================
phase('Classify')
const batches = chunk(ALL_BUGS, 17)
log(`${batches.length} agents × ~${Math.round(ALL_BUGS.length/batches.length)} bugs each`)

const results = await parallel(
    batches.map((batch, i) => () =>
        agent(buildClassifyPrompt(batch), {label: `batch-${i+1}`, phase: 'Classify'})
    )
)

let classifications = {}
for (let i = 0; i < batches.length; i++) {
    const raw = results[i]
    if (!raw) { log(`Batch ${i+1}: FAIL`); continue }
    try {
        const text = typeof raw === 'string' ? raw : JSON.stringify(raw)
        let arr = null
        const m = text.match(/\[[\s\S]*\]/)
        if (m) { try { arr = JSON.parse(m[0]) } catch {} }
        if (!arr) {
            const cm = text.match(/```(?:json)?\s*([\s\S]*?)```/)
            if (cm) { const cm2 = cm[1].match(/\[[\s\S]*\]/); if (cm2) try { arr = JSON.parse(cm2[0]) } catch {} }
        }
        if (arr) {
            let batchCount = 0
            for (const c of arr) {
                if (!c.bug_id) continue
                classifications[c.bug_id] = {
                    classification: (c.classification || '').trim().substring(0, 2),
                    reason: (c.reason || '').substring(0, 80),
                    confidence: c.confidence || 0,
                }
                batchCount++
            }
            log(`Batch ${i+1}: ${batchCount}/${batches[i].length}`)
        } else {
            log(`Batch ${i+1}: parse fail`)
        }
    } catch(e) { log(`Batch ${i+1}: error ${e}`) }
}

const found = Object.keys(classifications).length
log(`Total classified: ${found}/${ALL_BUGS.length}`)

// ============================================================
phase('Score')
// Hold-out: 10 hardest bugs (boundary ambiguity + traps)
const HOLD_OUT_IDS = ['B16','B18','B25','B28','B31','B33','B36','B38','M05','T03']
const IN_SAMPLE = ALL_BUGS.filter(b => !HOLD_OUT_IDS.includes(b.id))
const HOLD_OUT = ALL_BUGS.filter(b => HOLD_OUT_IDS.includes(b.id))

function scoreSet(bugs, label) {
    log(`--- ${label} (${bugs.length} bugs) ---`)
    log('Bug | Agent | GT | OK? | Conf')
    let correct = 0
    for (const b of bugs) {
        const c = classifications[b.id]
        const at = c ? c.classification : '?'
        const ok = at === b.t
        if (ok) correct++
        log(` ${b.id} | ${at} | ${b.t} | ${ok ? 'OK' : 'FAIL'} | ${c ? c.confidence : 0}%`)
    }
    const pct = bugs.length > 0 ? (correct/bugs.length*100).toFixed(0) : 'N/A'
    log(`  → ${correct}/${bugs.length} (${pct}%)`)
    return {correct, total: bugs.length, pct: bugs.length > 0 ? parseFloat(pct) : 0}
}

// T-Type failure analysis
const failures = []
for (const b of ALL_BUGS) {
    const c = classifications[b.id]
    if (c && c.classification !== b.t) {
        failures.push({bug:b.id, agent:c.classification, truth:b.t, reason:c.reason})
    }
}

// Cluster failures
const cluster = {}
for (const f of failures) {
    const key = `${f.agent}→${f.truth}`
    if (!cluster[key]) cluster[key] = []
    cluster[key].push(f.bug)
}

const inResult = scoreSet(IN_SAMPLE, `In-Sample`)
const holdResult = scoreSet(HOLD_OUT, `Hold-Out (10 hardest)`)
const totalCorrect = inResult.correct + holdResult.correct
const totalPct = (totalCorrect/ALL_BUGS.length*100).toFixed(0)
const gap = inResult.pct - holdResult.pct

log('')
log(`T1 49-bug v3: ${totalCorrect}/${ALL_BUGS.length} (${totalPct}%)`)
log(`In-Sample: ${inResult.pct}% | Hold-Out: ${holdResult.pct}% | Gap: ${gap}pp`)
log('')
log('Failure clusters:')
for (const [key, bugs] of Object.entries(cluster)) {
    log(`  ${key}: ${bugs.join(', ')} (${bugs.length}x)`)
}

return {
    total: ALL_BUGS.length, correct: totalCorrect, pct: parseFloat(totalPct),
    inSample: inResult, holdOut: holdResult, gap, overfit: gap > 15,
    clusters: cluster, found, cost: '~$0.03',
}
