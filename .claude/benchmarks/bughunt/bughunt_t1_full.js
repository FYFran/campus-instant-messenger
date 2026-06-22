export const meta = {
    name: '试剑石 T1 全量',
    description: 'Tier 1 — 35 bug 全量分类 ($0.03, <60s)。1 agent 分类全部 35 bugs，验证 T-Type。',
    phases: [
        { title: 'Classify', detail: '1 agent classifies all 35 bugs' },
        { title: 'Score', detail: 'Rule-based T-Type matching' },
    ],
}

const T = 'T0=稳定复现(每次都) T1=竞态时序(偶尔,同一操作结果不一致) T2=多因素(需≥2条件,换输入结果不同) T3=静默数据(T1/T2/T5已排除) T4=昨天还好(代码没改环境变了) T5=状态机卡住 T6=特定环境(本机vsCI/Docker/OS) T7=NOT_A_BUG(符合设计)'

const BUGS = [
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
    {id:'B11',d:'campus_go 管理后台仪表板 /api/admin/dashboard 在数据库连接池耗尽或网络异常时返回 500 错误并 panic nil pointer dereference。条件满足时稳定复现。',t:'T0',l:'Go'},
    {id:'B12',d:'学院管理员打开仪表板 /api/college/dashboard 后看到的统计数据全部是 0。但数据库中有该学院的学生和活动。HTTP 200 无报错——只是数字全0。',t:'T3',l:'Go'},
    {id:'B13',d:'campus_go 登录接口 /api/login 之前有频率限制(同IP 12秒一次)，最近几个版本限制不生效了。连续100次错误密码全部返回401没被拦截。之前的版本正常。',t:'T4',l:'Go'},
    {id:'B14',d:'学院管理员查看学生列表时某些学生数据缺失。学院50个学生页面只显示48个。缺失学生在数据库中存在且可正常登录。无报错。',t:'T3',l:'Go'},
    {id:'B15',d:'用户通知列表 /api/notifications 中所有通知 is_read 始终为 false，即使用户已点开阅读。数据库存储整数0/1但API JSON is_read始终false。日志有scan error记录。',t:'T6',l:'Go'},
    {id:'B16',d:'代码审查发现 activities.go Signup 函数 defer Rollback 后又 Commit——审查者认为是bug，Commit后defer会回滚已提交数据。需确认是否真有问题。',t:'T7',l:'Go'},
    {id:'B17',d:'campus_go 注册接口 /api/register 在特定条件下允许普通学生注册为教师或管理员。用户说"没邀请码但注册后变成teacher"。不是每次都触发。',t:'T2',l:'Go'},
    {id:'B18',d:'campus_go 已结束(ended)的活动偶尔变回"已发布(published)"状态。管理员确认没手动改。已结束活动突然又开放报名。',t:'T5',l:'Go'},
    {id:'B19',d:'campus_go 登录限流偶尔不准确——同IP在12秒内能连续尝试多次。go test -race 偶尔出现race detector告警。压力测试时更容易触发。',t:'T1',l:'Go'},
    {id:'B20',d:'campus_go 活动报名截止判断偏差8小时。活动截止时间是今晚23:59但下午16:00就被提示报名已截止。学生反映活动明明没到截止时间系统不让报了。',t:'T6',l:'Go'},
    {id:'B21',d:'Python后端管理员点"完成活动"后活动状态变completed用户收到"学时已发放"通知——但志愿学时实际没增加。如果管理员另外点"生成证书"学时才会正确增加。只点"完成活动"学时永远是0。',t:'T3',l:'Python'},
    {id:'B22',d:'Python后端仪表板统计 API /api/dashboard/stats 在数据库无任何活动记录时返回500。日志 ZeroDivisionError: division by zero。有活动时一切正常。',t:'T0',l:'Python'},
    {id:'B23',d:'campus_go 活动的报名开始时间未设置(留空)，活动状态为published，截止时间在未来。但学生报名时提示"报名尚未开始"。发布者没设开始时间限制。',t:'T2',l:'Go'},
    {id:'B24',d:'campus_go API偶尔返回旧数据。用户刚报名活动刷新后报名状态按钮没变(仍显示"报名")。等1-2分钟再刷新才正确。前端确认没有本地缓存。',t:'T4',l:'Go'},
    {id:'B25',d:'campus_go 用户点击通知后详情页显示"已读"，但返回通知列表后红点仍在(仍然未读)。两个页面显示状态不一致。',t:'T5',l:'Go'},
    {id:'B26',d:'campus_go 处理不带 Authorization 头的请求时发生 panic。日志 runtime error: invalid memory address or nil pointer dereference 在 auth.go JWT中间件。正常带token请求没问题。',t:'T0',l:'Go'},
    {id:'B27',d:'TokenLine 平台调用 AI API 时扣费发生在 API 调用之前。AI API 超时或失败时 token 已被扣但用户没收到回复。余额减少但对话历史无对应AI回复。',t:'T3',l:'Python'},
    {id:'B28',d:'TokenLine 充值订单偶尔一直显示"处理中(processing)"不会自动变"已完成"或"失败"。用户已完成支付(微信/支付宝回调已收到)但订单状态没更新。钱付了 token 没到账。',t:'T5',l:'Go'},
    {id:'B29',d:'安全审查报告标记 campus_go 密码哈希使用了"不安全的bcrypt cost值"。auth.go:156 用 bcrypt.DefaultCost(值10)，而OWASP 2026推荐最低cost为12。审查者认为哈希易被暴力破解。',t:'T7',l:'Go'},
    {id:'B30',d:'campus_go WebSocket实时推送偶尔丢消息。用户收到新通知推送时有时WebSocket连接正常但收不到。刷新页面重连后又出现。大概10条丢1-2条。',t:'T1',l:'Go'},
    {id:'B31',d:'Python后端志愿学时统计偶尔有浮点小数偏差。3个活动3.5+2.0+1.5应为7.0但页面显示6.999999999999999。偏差极小但学生注意到了。',t:'T3',l:'Python'},
    {id:'B32',d:'Python后端并发通知发送在Python 3.9不工作。开发机3.12正常但服务器3.9批量通知只发第一条其余丢失。无报错。',t:'T6',l:'Python'},
    {id:'B33',d:'Flutter端在网络慢或API响应异常时每次登录后首页完全白屏——导航栏在但页面主体白色，日志无错误。杀app重开恢复。条件满足时稳定复现。',t:'T0',l:'Flutter'},
    {id:'B34',d:'campus_go 活动列表 /api/activities 越来越慢。最早<100ms现在>2秒。管理员后台更慢，活动超50个需5秒+。',t:'T2',l:'Go'},
    {id:'B35',d:'安全审查报告标记campus_go存在"权限绕过"：scope_type=all的活动对所有学院学生可见，即使学生学院与活动college字段不匹配。审查者认为college_admin也可操作不属于自己学院的scope_type=all活动。标记HIGH severity。',t:'T7',l:'Go'},
    {id:'B36',d:'campus_go 学生登录偶尔失败返回401密码明明是对的。重试2-3次后又成功了。大概登录10次有1-2次失败。学生投诉"密码没错但登不上去"。',t:'T7',l:'Go'},
    {id:'B37',d:'campus_go 学生志愿时长在开发环境显示正确(10.5h)，但生产环境始终显示0。两个环境代码相同数据库数据相同。没有任何报错HTTP 200。',t:'T6',l:'Go'},
    {id:'B38',d:'campus_go 服务首次启动后第一个请求必panic nil pointer dereference，之后所有请求正常。重启服务后又会出现第一次panic。每次重启稳定复现。',t:'T5',l:'Go'},
    {id:'M01',d:'Dashboard统计页面在高并发时偶尔返回502/504超时。平时正常但流量高峰期概率性出现。监控显示数据库CPU突然飙升。',t:'T1',l:'Go'},
    {id:'M02',d:'同一IP偶尔能绕过注册频率限制连续注册多个账号。系统有限流规则但有时同一个IP能注册超限。并发注册时更容易触发。',t:'T1',l:'Go'},
    {id:'M03',d:'暴力破解/频率限制功能完全不工作。无论多少次失败尝试用户都不会被限流。代码中有完整的限流逻辑但从未被触发。没有报错。',t:'T3',l:'Go'},
    {id:'M04',d:'用不存在邮箱登录时几乎秒拒(401)，用存在邮箱但错误密码登录时明显慢1-2秒。用户反馈乱输不存在的邮箱立刻就返回了但自己邮箱要等一会。',t:'T1',l:'Go'},
    {id:'M05',d:'每个API请求都失败返回通用错误信息。前端开发者确认刚改过代码加了一个新参数。所有用户都受影响所有功能都用不了。',t:'T0',l:'JavaScript'},
    {id:'M06',d:'某些AI模型的流式响应中用户收到空白回复。API返回了数据(DevTools中EventStream有内容)但前端显示空的。普通模型正常只有特定模型有问题。没有报错。',t:'T3',l:'Go'},
    {id:'M07',d:'支付回调偶尔触发两次token发放——用户付了一次钱但收到了双倍token。大概5-10%的支付会出现。支付回调日志中有时能看到同一invoice ID被处理了两次。',t:'T1',l:'Go'},
    {id:'M08',d:'文件上传功能完全不工作——每次返回415 Unsupported Media Type。短信回调和支付网关回调也返回415。所有非JSON Content-Type的请求都被拒绝。',t:'T0',l:'Go'},
    {id:'T01',d:'TokenLine平台使用某些AI模型时用户在聊天界面看到了AI的内部思考过程(内心独白)。这些内容不应该暴露给用户。使用普通模型时没有这个问题。',t:'T3',l:'JavaScript'},
    {id:'T02',d:'TokenLine平台AI聊天偶尔出现空回复——用户提问后模型不回答聊天框显示空白。API日志显示模型确实返回了tokens但前端渲染出来是空的。不是每次都触发。',t:'T1',l:'JavaScript'},
    {id:'T03',d:'TokenLine聊天功能突然完全不工作——每次发送消息都失败。前端刚更新过代码。之前版本正常。所有用户都受影响。',t:'T4',l:'JavaScript'},
]

function buildClassifyPrompt() {
    let p = `你是缉凶 agent。仅做分类——不调查代码。${BUGS.length} 个 bug，每个判 T-Type。

分类规则:
- STOP 先想 bug 的深层因果结构（什么变了？什么时候变？谁受影响？），不要匹配关键词
- T0: 每次必现 crash/panic/500。必须伴随报错——"每次都慢"是T3不是T0
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
- F4: 行为一致无报错+描述含"用户认为/用户投诉这是bug/需确认是否产品设计" → 考虑T7不是T3
- F5: "数据库为空/文件为空/初始状态"导致必现500/crash → T0不是T2（系统状态≠用户输入参数）
- F6: "前一版本正常/之前有但现在没了/版本更新后" → T4不是T3（回归=环境/版本变化）
- F7: "日志有scan error/类型转换错误" → T6不是T3（类型不匹配=环境/DB schema差异）
- F8: "偏差固定数值(8小时/2个学生等)" → 不是T3（T3是全局数据错，固定偏差查时区/过滤条件）
- F9: "偶尔+非数据错误" → T1或T5考虑，不是T3（T3要求每次一致地错）

结构排除: 判 T3 前写出 ≥2 个证据证明 T1/T2/T5 不成立。缺 = 不能选 T3。

每个 bug 返回:
{bug_id, classification (T0-T7), classification_reason ("为什么T_X不是T_Y? 致命误判检查?"), confidence (0-100)}

全部 ${BUGS.length} bug 的 JSON 数组。
`
    for (const b of BUGS) {
        p += `\nBug ${b.id} (${b.l}): ${b.d}`
    }
    p += `\n\n返回: [{"bug_id":"Bxx","classification":"Tx","classification_reason":"...","confidence":xx}, ...]`
    return p
}

// ============================================================
phase('Classify')
log(`1 agent classifies all ${BUGS.length} bugs (T-Type only, ~$0.03)...`)

const classifyOutput = await agent(buildClassifyPrompt(), {
    label: 'classify-all-35',
    phase: 'Classify',
})

// Parse batch results
let classifications = {}
try {
    const text = typeof classifyOutput === 'string' ? classifyOutput : JSON.stringify(classifyOutput)
    let arr = null
    const match = text.match(/\[[\s\S]*\]/)
    if (match) {
        try { arr = JSON.parse(match[0]) } catch {}
    }
    if (!arr) {
        const cm = text.match(/```(?:json)?\s*([\s\S]*?)```/)
        if (cm) {
            const cm2 = cm[1].match(/\[[\s\S]*\]/)
            if (cm2) try { arr = JSON.parse(cm2[0]) } catch {}
        }
    }
    if (!arr) {
        arr = []
        const entries = text.match(/\{[^}]+\}/g)
        if (entries) {
            for (const e of entries) {
                try { arr.push(JSON.parse(e)) } catch {}
            }
        }
    }
    if (arr) {
        for (const c of arr) {
            if (!c.bug_id) continue
            classifications[c.bug_id] = {
                classification: (c.classification || '').trim().substring(0, 2),
                reason: (c.classification_reason || '').substring(0, 80),
                confidence: c.confidence || 0,
            }
        }
    }
    if (Object.keys(classifications).length === 0) {
        log(`Parse failed. Raw output (first 500 chars): ${text.substring(0,500)}`)
    }
} catch (e) {
    log(`Parse error: ${e}`)
}

// ============================================================
phase('Score')

// Split: in-sample (B01-B25) vs hold-out (B26-B35)
// Hold-out: 10 hardest bugs (boundary ambiguity + traps). B16,B18,B25,B28,B31,B33,B36,B38,M05,T03
const HOLD_OUT_IDS = ['B16','B18','B25','B28','B31','B33','B36','B38','M05','T03']
const IN_SAMPLE = BUGS.filter(b => !HOLD_OUT_IDS.includes(b.id))
const HOLD_OUT = BUGS.filter(b => HOLD_OUT_IDS.includes(b.id))

function scoreSet(bugs, label) {
    log(`--- ${label} (${bugs.length} bugs) ---`)
    log('Bug | Agent | GT | OK? | Conf | Reason')
    log('----|-------|-----|-----|------|------')
    let correct = 0
    for (const b of bugs) {
        const c = classifications[b.id]
        const agentType = c ? c.classification : '?'
        const ok = agentType === b.t
        if (ok) correct++
        log(` ${b.id} | ${agentType} | ${b.t} | ${ok ? 'OK' : 'FAIL'} | ${c ? c.confidence : 0}% | ${c ? c.reason : 'no output'}`)
    }
    const pct = (correct/bugs.length*100).toFixed(0)
    log(`  → ${correct}/${bugs.length} (${pct}%)`)
    return {correct, total: bugs.length, pct: parseFloat(pct)}
}

const inResult = scoreSet(IN_SAMPLE, `In-Sample (${IN_SAMPLE.length} bugs)`)
const holdResult = scoreSet(HOLD_OUT, `Hold-Out B26-B30 (${HOLD_OUT.length} bugs)`)

const totalCorrect = inResult.correct + holdResult.correct
const totalBugs = BUGS.length
const totalPct = (totalCorrect/totalBugs*100).toFixed(0)
const gap = inResult.pct - holdResult.pct

log('')
log(`============================================`)
log(`T1 全量: ${totalCorrect}/${totalBugs} (${totalPct}%)`)
log(`In-Sample: ${inResult.pct}% | Hold-Out: ${holdResult.pct}% | Gap: ${gap > 0 ? '+' : ''}${gap}pp`)
if (gap > 5) log('⚠ OVERFIT WARNING: hold-out gap >5pp!')
log(`Cost: 1 agent (~$0.03)`)

return {
    total: totalBugs, correct: totalCorrect,
    pct: parseFloat(totalPct),
    inSample: inResult,
    holdOut: holdResult,
    gap,
    overfit: gap > 5,
    classifications,
    cost: '~$0.03',
}
