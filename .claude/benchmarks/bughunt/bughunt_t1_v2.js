export const meta = {
    name: '试剑石 T1 全量 v2',
    description: 'Tier 1 — 35 bug 分批分类 (~$0.03)。3 agent 并行各处理 ~12 bugs，防 context 溢出。',
    phases: [
        { title: 'Classify', detail: '3 agents classify ~12 bugs each in parallel' },
        { title: 'Score', detail: 'Aggregate + hold-out gap' },
    ],
}

const ALL_BUGS = [
    {id:'B01',d:'campus_go 活动列表 API /api/activities 在数据库为空时返回 500 错误。有活动时正常。',t:'T0',l:'Go'},
    {id:'B02',d:'campus_go 报名接口偶尔出现同一学生报了两次名。约每20-30次一次。',t:'T1',l:'Go'},
    {id:'B03',d:'campus_go college_admin 有时能看到并操作其他学院的活动。跟学院名有关。',t:'T2',l:'Go'},
    {id:'B04',d:'campus_go 学生志愿时长统计页面总时长比实际短。没报错，数字不对。学生反映签了10小时页面显示7小时。',t:'T3',l:'Python'},
    {id:'B05',d:'campus_go JWT token 刷新昨天能用今天全401。代码没改，服务器重启过。',t:'T4',l:'Go'},
    {id:'B06',d:'campus_go 活动报名后状态一直pending不会变confirmed。审批流程是自动的。学生等2小时状态没变。',t:'T5',l:'Go'},
    {id:'B07',d:'campus_go 测试本机go1.22全通但CI go1.23 TestListActivities panic nil deref。',t:'T6',l:'Mixed'},
    {id:'B08',d:'产品经理反馈 campus_go "我的报名"列表只显示已确认活动不显示待审批。用户投诉说这是bug——报了名看不到以为没成功。需确认是代码问题还是产品设计。',t:'T7',l:'Go'},
    {id:'B09',d:'Python 后端积分更新偶尔不生效。有时刷新还是旧的。再刷一次对了。不是每次都发生。',t:'T1',l:'Python'},
    {id:'B10',d:'campus_go 活动列表越来越慢。50个活动100ms，200个需3秒。没报错API正常200。',t:'T3',l:'Go'},
    {id:'B11',d:'campus_go 管理后台仪表板在数据库连接池耗尽或网络异常时返回500并panic nil pointer dereference。条件满足时稳定复现。',t:'T0',l:'Go'},
    {id:'B12',d:'学院管理员打开仪表板后看到的统计数据全部是0。但数据库中有该学院的学生和活动。HTTP 200无报错——只是数字全0。',t:'T3',l:'Go'},
    {id:'B13',d:'campus_go 登录接口之前有频率限制(同IP 12秒一次)，最近几个版本限制不生效了。连续100次错误密码全部返回401没被拦截。之前的版本正常。',t:'T4',l:'Go'},
    {id:'B14',d:'学院管理员查看学生列表时某些学生数据缺失。学院50个学生页面只显示48个。缺失学生在数据库中存在且可正常登录。无报错。',t:'T3',l:'Go'},
    {id:'B15',d:'用户通知列表中所有通知 is_read 始终为 false，即使用户已点开阅读。数据库存储整数0/1但API JSON is_read始终false。日志有scan error记录。',t:'T6',l:'Go'},
    {id:'B16',d:'代码审查发现 activities.go Signup 函数 defer Rollback 后又 Commit——审查者认为是bug，Commit后defer会回滚已提交数据。需确认是否真有问题。',t:'T7',l:'Go'},
    {id:'B17',d:'campus_go 注册接口在特定条件下允许普通学生注册为教师或管理员。用户说"没邀请码但注册后变成teacher"。不是每次都触发。',t:'T2',l:'Go'},
    {id:'B18',d:'campus_go 已结束(ended)的活动偶尔变回"已发布(published)"状态。管理员确认没手动改。已结束活动突然又开放报名。',t:'T5',l:'Go'},
    {id:'B19',d:'campus_go 登录限流偶尔不准确——同IP在12秒内能连续尝试多次。go test -race 偶尔出现race detector告警。压力测试时更容易触发。',t:'T1',l:'Go'},
    {id:'B20',d:'campus_go 活动报名截止判断偏差8小时。活动截止时间是今晚23:59但下午16:00就被提示报名已截止。学生反映活动明明没到截止时间系统不让报了。',t:'T6',l:'Go'},
    {id:'B21',d:'Python后端管理员点"完成活动"后活动状态变completed用户收到"学时已发放"通知——但志愿学时实际没增加。如果管理员另外点"生成证书"学时才会正确增加。只点"完成活动"学时永远是0。',t:'T3',l:'Python'},
    {id:'B22',d:'Python后端仪表板统计API在数据库无任何活动记录时返回500。日志 ZeroDivisionError: division by zero。有活动时一切正常。',t:'T0',l:'Python'},
    {id:'B23',d:'campus_go 活动的报名开始时间未设置(留空)，活动状态为published，截止时间在未来。但学生报名时提示"报名尚未开始"。发布者没设开始时间限制。',t:'T2',l:'Go'},
    {id:'B24',d:'campus_go API偶尔返回旧数据。用户刚报名活动刷新后报名状态按钮没变(仍显示"报名")。等1-2分钟再刷新才正确。前端确认没有本地缓存。',t:'T4',l:'Go'},
    {id:'B25',d:'campus_go 用户点击通知后详情页显示"已读"，但返回通知列表后红点仍在(仍然未读)。两个页面显示状态不一致。',t:'T5',l:'Go'},
    {id:'B26',d:'campus_go 处理不带 Authorization 头的请求时发生 panic。日志 runtime error: nil pointer dereference 在 auth.go JWT中间件。正常带token请求没问题。',t:'T0',l:'Go'},
    {id:'B27',d:'TokenLine 平台调用 AI API 时扣费发生在 API 调用之前。AI API 超时或失败时 token 已被扣但用户没收到回复。余额减少但对话历史无对应AI回复。',t:'T3',l:'Python'},
    {id:'B28',d:'TokenLine 充值订单偶尔一直显示"处理中(processing)"不会自动变"已完成"或"失败"。用户已完成支付(微信/支付宝回调已收到)但订单状态没更新。钱付了 token 没到账。',t:'T5',l:'Go'},
    {id:'B29',d:'安全审查报告标记 campus_go 密码哈希使用了"不安全的bcrypt cost值"。auth.go:156 用 bcrypt.DefaultCost(值10)，而OWASP 2026推荐最低cost为12。审查者认为哈希易被暴力破解。',t:'T7',l:'Go'},
    {id:'B30',d:'campus_go WebSocket实时推送偶尔丢消息。用户收到新通知推送时有时WebSocket连接正常但收不到。刷新页面重连后又出现。大概10条丢1-2条。',t:'T1',l:'Go'},
    {id:'B31',d:'Python后端志愿学时统计偶尔有浮点小数偏差。3个活动3.5+2.0+1.5应为7.0但页面显示6.999999999999999。偏差极小但学生注意到了。',t:'T3',l:'Python'},
    {id:'B32',d:'Python后端并发通知发送在Python 3.9不工作。开发机3.12正常但服务器3.9批量通知只发第一条其余丢失。无报错。',t:'T6',l:'Python'},
    {id:'B33',d:'Flutter端在网络慢或API响应异常时每次登录后首页完全白屏——导航栏在但页面主体白色，日志无错误。杀app重开恢复。条件满足时稳定复现。',t:'T0',l:'Flutter'},
    {id:'B34',d:'campus_go 活动列表越来越慢。最早<100ms现在>2秒。管理员后台更慢，活动超50个需5秒+。',t:'T2',l:'Go'},
    {id:'B35',d:'安全审查报告标记campus_go存在"权限绕过"：scope_type=all的活动对所有学院学生可见。审查者认为college_admin也可操作不属于自己学院的scope_type=all活动。标记HIGH severity。',t:'T7',l:'Go'},
]

function chunk(arr, size) {
    const chunks = []
    for (let i = 0; i < arr.length; i += size) chunks.push(arr.slice(i, i + size))
    return chunks
}

function buildClassifyPrompt(bugs) {
    let p = `分类 ${bugs.length} 个 bug。只输出 JSON 数组，不解释。

T0=每次必现crash/500(条件满足时稳定复现=系统状态如空DB导致必现500是T0)。T1=竞态时序(同一操作有时正常有时异常)。T2=多因素(换输入值结果不同)。T3=静默数据错(T1/T2/T5排完才选,跳过直接选=报废)。T4=昨天还好(代码没改环境/版本变了)。T5=状态卡住。T6=环境差异(本机vsCI/OS/Python版本)。T7=NOT_A_BUG(符合设计/OWASP建议非bug)。

致命误判:F1"偶尔+刷新好了"=T1|F2"某些输入触发"=T2|F3"一直pending"=T5|F4"需确认产品设计"=T7|F5"空数据库/初始状态crash"=T0|F6"之前有现在没了"=T4|F7"scan error/类型转换"=T6|F8"固定数值偏差(8h/2人)"=优先T6/T4|F9"偶尔非数据错"(状态回退/支付卡住)=T5/T1
`
    for (const b of bugs) p += `\n${b.id}: ${b.d}`
    p += `\n\n返回: [{"bug_id":"${bugs[0].id}","classification":"Tx","reason":"...","confidence":xx},...] 共${bugs.length}个。`
    return p
}

// ============================================================
phase('Classify')
const batches = chunk(ALL_BUGS, 12)
log(`${batches.length} agents × ~${Math.round(ALL_BUGS.length/batches.length)} bugs each`)

const results = await parallel(
    batches.map((batch, i) => () =>
        agent(buildClassifyPrompt(batch), {label: `batch-${i+1}`, phase: 'Classify'})
    )
)

// Parse all results
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
            log(`Batch ${i+1}: parse fail (${text.substring(0, 100)}...)`)
        }
    } catch(e) { log(`Batch ${i+1}: error ${e}`) }
}

const found = Object.keys(classifications).length
log(`Total classified: ${found}/${ALL_BUGS.length}`)

// ============================================================
phase('Score')
const IN_SAMPLE = ALL_BUGS.filter(b => parseInt(b.id.substring(1)) <= 25)
const HOLD_OUT = ALL_BUGS.filter(b => parseInt(b.id.substring(1)) >= 26)

function scoreSet(bugs, label) {
    log(`--- ${label} (${bugs.length} bugs) ---`)
    log('Bug | Agent | GT | OK? | Conf')
    let correct = 0, total = 0
    for (const b of bugs) {
        const c = classifications[b.id]
        const agentType = c ? c.classification : '?'
        const ok = agentType === b.t
        if (ok) correct++
        total++
        log(` ${b.id} | ${agentType} | ${b.t} | ${ok ? 'OK' : 'FAIL'} | ${c ? c.confidence : 0}%`)
    }
    const pct = total > 0 ? (correct/total*100).toFixed(0) : 'N/A'
    log(`  → ${correct}/${total} (${pct}%)`)
    return {correct, total, pct: total > 0 ? parseFloat(pct) : 0}
}

const inResult = scoreSet(IN_SAMPLE, 'In-Sample B01-B25')
const holdResult = scoreSet(HOLD_OUT, 'Hold-Out B26-B35')
const totalCorrect = inResult.correct + holdResult.correct
const totalPct = (totalCorrect/ALL_BUGS.length*100).toFixed(0)
const gap = inResult.pct - holdResult.pct

log('')
log(`T1 全量 v2: ${totalCorrect}/${ALL_BUGS.length} (${totalPct}%) | In:${inResult.pct}% Hold:${holdResult.pct}% Gap:${gap > 0 ? '+' : ''}${gap}pp`)
if (gap > 5) log('⚠ OVERFIT')

return {total:ALL_BUGS.length, correct:totalCorrect, pct:parseFloat(totalPct), inSample:inResult, holdOut:holdResult, gap, overfit:gap>5, found, cost:'~$0.03'}
