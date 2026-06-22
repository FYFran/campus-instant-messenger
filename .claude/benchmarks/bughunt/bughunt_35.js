export const meta = {
    name: '试剑石35',
    description: '试剑石 v2.1 — 35 bugs全量跑分。缉凶 v2.2 vs 裸 agent。',
    phases: [
        { title: 'Inject', detail: '注入可注入bug (B02/B06/B10)' },
        { title: 'Investigate', detail: '缉凶 + 裸 agent 并行调查 35 bugs' },
        { title: 'Revert', detail: '还原注入' },
        { title: 'Judge', detail: '跨模型Judge (Sonnet) 评分' },
        { title: 'Report', detail: '双Skill对比 + L3 + Gate' },
    ],
}

const T = 'T0=稳定复现(每次都) T1=竞态时序(偶尔,加log消失) T2=多因素(需≥2条件同时满足) T3=无报错数据错/性能退化 T4=昨天还好(代码没改环境变了) T5=状态机卡住 T6=特定环境(本机vsCI/Docker/OS) T7=NOT_A_BUG(行为符合设计)'

// Full 35 bugs — desc from bugset/*/desc.md, GT from bugset/*/truth.md
const BUGS = [
    // === Original 10 (B01-B10) ===
    {id:'B01',d:'campus_go 活动列表 API /api/activities 在数据库为空时返回 500 错误。有活动时正常。curl http://139.196.50.134/api/activities → 500',t:'T0',l:'Go',inj:false},
    {id:'B02',d:'campus_go 活动报名接口偶尔出现同一学生报了两次名。正常逻辑应阻止重复报名，偶发同一个人同一活动出现两条记录。约每20-30次一次。',t:'T1',l:'Go',inj:true},
    {id:'B03',d:'campus_go 中 college_admin 有时能看到并操作其他学院的活动。权限设计是只管自己学院，偶尔跨学院操作成功。跟学院名包含特殊字符或部分匹配有关。',t:'T2',l:'Go',inj:false},
    {id:'B04',d:'campus_go 学生志愿时长统计页面总时长偶尔比实际短。没报错没crash，数字不对。学生反映签了10小时只显示7小时。',t:'T3',l:'Python',inj:false},
    {id:'B05',d:'campus_go JWT token 刷新 /api/token/refresh 昨天能用今天全401。代码没改，服务器重启过。',t:'T4',l:'Go',inj:false},
    {id:'B06',d:'campus_go 活动报名后状态一直pending不会变confirmed。审批流程是自动的(不需人工审核)。学生等2小时状态没变。',t:'T5',l:'Go',inj:true},
    {id:'B07',d:'campus_go 测试本机全通过(go test ./... PASS)但 CI TestListActivities 一直失败。本机Go1.22 CI Go1.23。panic nil pointer dereference。',t:'T6',l:'Mixed',inj:false},
    {id:'B08',d:'用户反馈 campus_go 我的报名列表只显示已确认活动不显示待审批。用户认为这是bug——报名了看不到以为没报上又报一次。',t:'T7',l:'Go',inj:false},
    {id:'B09',d:'Python 后端学生积分更新偶尔不生效。完成活动积分应立刻增加，有时刷新页面还是旧的。再刷一次对了。不是每次都发生。',t:'T1',l:'Python',inj:false},
    {id:'B10',d:'campus_go 活动列表越来越慢。50个活动100ms，200个需3秒。没报错API正常200——就是慢。用户抱怨刷列表要等半天。',t:'T3',l:'Go',inj:true},

    // === New 25 (B11-B35) ===
    {id:'B11',d:'campus_go 学校管理后台仪表板 /api/admin/dashboard 偶尔返回 500 并导致服务 panic 重启。日志有 nil pointer dereference。数据库连接池耗尽或网络抖动时触发。',t:'T0',l:'Go',inj:false},
    {id:'B12',d:'学院管理员打开 campus_go 仪表板 /api/college/dashboard 后，统计数据(学生数、教师数、活动数、总志愿时长)全部是0。实际数据库中有该学院的学生和活动。没报错，HTTP 200。',t:'T3',l:'Go',inj:false},
    {id:'B13',d:'campus_go 登录接口 /api/login 之前有频率限制(同一IP 12秒内只能尝试一次)，但最近几个版本这个限制不生效了。连续100次错误密码全部返回401，没有被拦截。之前版本正常。',t:'T4',l:'Go',inj:false},
    {id:'B14',d:'学院管理员查看 campus_go 学生列表 /api/college/students 时，某些学生的数据缺失。学院有50个学生但页面只显示48个。缺失的学生在数据库中存在且可正常登录。没报错。',t:'T3',l:'Go',inj:false},
    {id:'B15',d:'campus_go 用户系统通知列表 /api/notifications 中，所有通知的 is_read 字段始终为 false。数据库中 is_read 列是整数(0或1)，但API返回的JSON中始终是false。日志有scan error。',t:'T6',l:'Go',inj:false},
    {id:'B16',d:'代码审查发现 campus_go activities.go Signup函数中 defer Rollback 在 Commit 之后仍然执行。审查者认为这是bug——Commit之后Rollback会把刚提交的数据回滚。',t:'T7',l:'Go',inj:false},
    {id:'B17',d:'campus_go 注册接口 /api/register 在特定条件下允许普通学生注册为教师或管理员。用户反映没有邀请码但注册后变成了teacher角色。特定环境配置下出现。',t:'T2',l:'Go',inj:false},
    {id:'B18',d:'campus_go 中已结束(ended)的活动偶尔会变回已发布(published)状态。管理员没手动修改。学生反映已结束活动突然又开放报名。',t:'T5',l:'Go',inj:false},
    {id:'B19',d:'campus_go 登录限流偶尔不准确——有时同IP在12秒内能连续尝试多次登录。go test -race 偶尔出现 race detector 告警。生产环境偶发，压测时更容易触发。',t:'T1',l:'Go',inj:false},
    {id:'B20',d:'campus_go 活动报名截止判断偶尔偏差8小时。活动截止时间今晚23:59，但用户下午16:00就被提示报名已截止。学生反映活动明明没到截止时间但系统不让报名。',t:'T6',l:'Go',inj:false},
    {id:'B21',d:'Python后端 campus_app 管理员点击完成活动后，活动状态变为completed，用户收到学时已发放的通知——但学生志愿学时没增加。如果管理员另外点了生成证书按钮，学时就会正确增加。',t:'T3',l:'Python',inj:false},
    {id:'B22',d:'Python后端 campus_app 仪表板统计 API /api/dashboard/stats 在数据库没有任何活动记录时返回500错误。日志显示 ZeroDivisionError: division by zero。数据库有活动时一切正常。',t:'T0',l:'Python',inj:false},
    {id:'B23',d:'campus_go 某活动报名开始时间(signup_start)未设置(留空)，活动状态published，截止时间在未来。但学生报名时提示报名尚未开始。发布者确认没设置开始时间限制。',t:'T2',l:'Go',inj:false},
    {id:'B24',d:'campus_go API偶尔返回旧数据。用户刚报名的活动，刷新列表后报名状态按钮没变。等1-2分钟后再刷新才正确。前端开发者确认没有本地缓存，API返回的数据就是旧的。',t:'T4',l:'Infra',inj:false},
    {id:'B25',d:'campus_go 用户点击通知后详情页显示已读，但返回通知列表后该通知仍显示未读(红点仍在)。用户再次点击同一条通知，详情页又显示已读，但列表永远是未读。',t:'T5',l:'Mixed',inj:false},
    {id:'B26',d:'campus_go 在特定条件下处理不带Authorization头的请求时发生panic。日志显示 nil pointer dereference 发生在JWT中间件。正常带token的请求没问题。',t:'T0',l:'Go',inj:false},
    {id:'B27',d:'TokenLine平台用户报告：调用AI API时偶尔扣了token但没有返回结果。用户余额减少了但对话历史中没有对应的AI回复。大约20次调用出现1次。',t:'T3',l:'Python',inj:false},
    {id:'B28',d:'TokenLine平台充值订单偶尔一直显示处理中(processing)，不会自动变为已完成或失败。用户已完成支付(微信/支付宝回调已收到)但订单状态没更新。钱付了token没到账。',t:'T5',l:'Python',inj:false},
    {id:'B29',d:'安全审查报告标记 campus_go 密码哈希使用了不安全的bcrypt cost值。auth.go中 bcrypt.DefaultCost 值为10，而OWASP 2026推荐最低cost为12。审查者认为密码哈希易被暴力破解。',t:'T7',l:'Go',inj:false},
    {id:'B30',d:'campus_go WebSocket实时推送偶尔丢消息。用户收到新通知推送时，有时WebSocket连接正常但收不到消息。刷新页面(重新连接)后消息又出现了。大约10条消息丢1-2条。',t:'T1',l:'Go',inj:false},
    {id:'B31',d:'campus_app Python后端志愿学时统计偶尔有小数偏差。学生参加3个活动分别获得3.5、2.0、1.5小时，总计应该7.0小时，但页面显示6.999999999999999。偏差极小但学生注意到了。',t:'T3',l:'Python',inj:false},
    {id:'B32',d:'campus_app Python后端并发通知发送在Python 3.9环境下不工作。代码在开发机(Python 3.12)测试正常，但部署到服务器(Python 3.9)后批量发通知时只发了第一条其余丢失。没报错。',t:'T6',l:'Python',inj:false},
    {id:'B33',d:'campus_app Flutter端在特定条件下完全白屏。用户登录后首页没有显示任何内容——导航栏在但页面主体是白色。日志中没有任何错误。杀掉app重开后恢复正常。主要发生在网络较慢时。',t:'T0',l:'Dart',inj:false},
    {id:'B34',d:'campus_go 活动列表 /api/activities 加载越来越慢。最早<100ms，活动超过50个后>2秒。管理员后台活动管理页面更慢，活动超过50个后需5秒以上才能加载完。',t:'T2',l:'Go',inj:false},
    {id:'B35',d:'安全审查报告标记 campus_go 存在权限绕过漏洞：scope_type=all 的活动对所有学院的学生可见，即使学生学院与活动college字段不匹配。审查者认为college_admin也能操作不属于自己学院的all活动。标记为HIGH severity。',t:'T7',l:'Go',inj:false},
]

// Ground truth keywords for scoring (per bug)
const GT = {
    B01:{t:'T0',f:'activities.go',fn:'ListActivities',kw:'nil deref empty rows.Err rows.Scan null pointer panic 500 crash'.split(' ')},
    B02:{t:'T1',f:'activities.go',fn:'Signup',kw:'SELECT INSERT race concurrent duplicate UNIQUE ON CONFLICT FOR UPDATE TOCTOU window'.split(' ')},
    B03:{t:'T2',f:'activities_admin.go',fn:'ApproveActivity',kw:'strings.Contains college scope partial match comma split substring permission auth'.split(' ')},
    B04:{t:'T3',f:'main.py',fn:'certificates',kw:'int round FLOAT duration truncat silent data loss sum certificate hour minute'.split(' ')},
    B05:{t:'T4',f:'nginx-campus.conf',fn:'proxy_pass',kw:'nginx proxy_pass port 9500 9501 restart config revert deploy redirect'.split(' ')},
    B06:{t:'T5',f:'activities.go',fn:'Signup',kw:'NULL default approval_required pending confirmed state machine stuck boolean migration status transfer'.split(' ')},
    B07:{t:'T6',f:'activities.go',fn:'ListActivities',kw:'Go 1.23 1.22 NULL Scan sqlite postgres COALESCE schema environment CI version mismatch'.split(' ')},
    B08:{t:'T7',f:'dashboard.go',fn:'GetMySignups',kw:'NOT_A_BUG confirmed filter product design UI page link STOP no code fix'.split(' ')},
    B09:{t:'T1',f:'main.py',fn:'complete_activity',kw:'await async coroutine event loop GC update points timing intermittent missing'.split(' ')},
    B10:{t:'T3',f:'activities.go',fn:'ListActivities',kw:'N+1 subquery correlated JOIN GROUP BY signup_count performance slow scale O(n) degrade index'.split(' ')},
    B11:{t:'T0',f:'dashboard.go',fn:'SchoolDashboard',kw:'rows _ := db.Query ignore error nil pointer panic defer rows.Close crash'.split(' ')},
    B12:{t:'T3',f:'dashboard.go',fn:'CollegeDashboard',kw:'QueryRow Scan error ignore zero stats college dashboard empty silently wrong'.split(' ')},
    B13:{t:'T4',f:'auth.go',fn:'Login',kw:'rate limit disabled commented DISABLED FOR TESTING regression brute force login 429'.split(' ')},
    B14:{t:'T3',f:'dashboard.go',fn:'CollegeStudents',kw:'Scan error continue skip row missing data silent loss volunteer_hours NULL COALESCE'.split(' ')},
    B15:{t:'T6',f:'dashboard.go',fn:'GetNotifications',kw:'is_read int bool scan mismatch integer boolean PostgreSQL type environment driver'.split(' ')},
    B16:{t:'T7',f:'activities.go',fn:'Signup',kw:'NOT_A_BUG defer Rollback Commit idiom pattern pgx no-op safe standard Go transaction'.split(' ')},
    B17:{t:'T2',f:'auth.go',fn:'Register',kw:'reg_code empty env var TrimSpace role escalation teacher admin registration code'.split(' ')},
    B18:{t:'T5',f:'activities_admin.go',fn:'ApproveActivity',kw:'ended published status transition validate check illegal back state machine approval'.split(' ')},
    B19:{t:'T1',f:'auth.go',fn:'Login',kw:'race concurrent map read write sync.Mutex RWMutex sync.Map goroutine rate limit'.split(' ')},
    B20:{t:'T6',f:'activities.go',fn:'Signup',kw:'timezone UTC CST ParseInLocation deadline time.Parse 8 hour offset Asia Shanghai'.split(' ')},
    B21:{t:'T3',f:'main.py',fn:'complete_activity',kw:'certificate INSERT missing generate complete activity hours silent no error notification'.split(' ')},
    B22:{t:'T0',f:'main.py',fn:'dashboard stats',kw:'ZeroDivisionError division by zero empty database activity_count crash stable 500'.split(' ')},
    B23:{t:'T2',f:'activities.go',fn:'Signup',kw:'signup_start NULL empty invalid date Parse year 0001 ancient Before always block start time'.split(' ')},
    B24:{t:'T4',f:'nginx-campus.conf',fn:'proxy_pass',kw:'nginx proxy_cache proxy_buffering cache API GET stale old data 60s regression'.split(' ')},
    B25:{t:'T5',f:'dashboard.go',fn:'GetNotifications',kw:'is_read state sync notification list detail page inconsistent refresh markAsRead Cache-Control'.split(' ')},
    B26:{t:'T0',f:'middleware/auth.go',fn:'JWT middleware',kw:'nil token Authorization header empty ParseWithClaims panic Valid Claims check'.split(' ')},
    B27:{t:'T3',f:'tokenline backend',fn:'API proxy',kw:'deduct credits before API call success fail refund order transaction timing silent data loss'.split(' ')},
    B28:{t:'T5',f:'tokenline backend',fn:'order handler',kw:'processing stuck timeout sweep cron webhook callback lost payment status poll'.split(' ')},
    B29:{t:'T7',f:'auth.go',fn:'Register',kw:'NOT_A_BUG bcrypt DefaultCost 10 reasonable Argon2id fallback security performance trade off OWASP'.split(' ')},
    B30:{t:'T1',f:'websocket.go',fn:'WebSocket',kw:'gorilla websocket concurrent write WriteJSON race lock sync.Mutex goroutine ping push message lost'.split(' ')},
    B31:{t:'T3',f:'main.py',fn:'my-stats',kw:'float precision IEEE 754 Decimal round accumulate sum error 6.9999 silent deviation'.split(' ')},
    B32:{t:'T6',f:'main.py',fn:'batch notify',kw:'asyncio.wait gather create_task Python 3.9 3.12 version coroutine Task schedule behavior difference'.split(' ')},
    B33:{t:'T0',f:'home_page.dart',fn:'FutureBuilder',kw:'null assertion snapshot.data bang operator hasData hasError white screen Flutter slow network'.split(' ')},
    B34:{t:'T2',f:'activities.go',fn:'ListActivities',kw:'N+1 subquery scalar correlated index signups activity_id slow JOIN GROUP BY performance degradation scale'.split(' ')},
    B35:{t:'T7',f:'activities_admin.go',fn:'ApproveActivity',kw:'NOT_A_BUG scope_type all product design school wide college view approval permission separate'.split(' ')},
}

function buildPrompt(bug) {
    return `BUG_ID: ${bug.id}  ← JSON的bug_id必须为此值

你是缉凶 agent。合同链7步全填。

Bug: ${bug.d}
语言: ${bug.l}

1.分类 — 先看症状: 代码没改昨天能用?→T4|每次必现?→T0|偶尔出现?→T1|≥2条件同时满足?→T2|卡在中间状态回不来?→T5|没报错结果不对?→T3(T5已排除)|本机行CI不行?→T6|读代码发现行为符合设计?→T7。分类不自洽→回第一步重判。
2.证据 — 复现步骤+baseline(>40字)
3.追踪 — 调用链+file:line
4.分析 — 根因(含file:line)+Counterfactual(conf)。T3必须含数值对比(修前=X vs 修后=Y)
5.修复 — 方案(T7不修代码)
6.验证 — pre/post
7.记录 — 潜在问题

返回JSON: {bug_id,classification,classification_reason,evidence,trace,root_cause,root_cause_file_line,cf_evidence,fix_description,confidence,latent_issues}`
}

function buildJudgePrompt(report, bug) {
    return `你是独立评分agent。评估以下bug report的全部3个维度。

Bug: ${bug.d}
GT根因方向: ${GT[bug.id].kw.slice(0,5).join(' ')}

Agent证据: ${(report.evidence||'').substring(0,300)}
Agent根因: ${(report.root_cause||'').substring(0,300)}
Agent文件行: ${report.root_cause_file_line||'N/A'}
Agent CF: ${(report.cf_evidence||'').substring(0,300)}
Agent分类: ${report.classification||'N/A'} (GT: ${GT[bug.id].t})

评分(3维):
1.证据充分性: 1=具体复现步骤+可验证baseline, 0=笼统
2.根因正确性: 2=根因方向一致+file:line正确, 1=方向对细节偏, 0=完全错误
3.CF真实性: 1=有pre/post可验证证据, 0=模板文字。T3必须含数值对比

返回JSON: {"evidence":0|1,"root_cause":0|1|2,"cf":0|1,"reasoning":"简要说明每维评分理由"}`
}

const AGENT_SCHEMA = {
    type:'object', properties:{
        bug_id:{type:'string'}, classification:{type:'string'}, classification_reason:{type:'string'},
        evidence:{type:'string'}, trace:{type:'string'}, root_cause:{type:'string'},
        root_cause_file_line:{type:'string'}, cf_evidence:{type:'string'},
        fix_description:{type:'string'}, confidence:{type:'number'}, latent_issues:{type:'string'},
    }, required:['bug_id','classification','evidence','trace','root_cause','cf_evidence','fix_description'],
}

// ============================================================
phase('Inject')
const injectableBugs = BUGS.filter(b => b.inj)
log(`Injecting ${injectableBugs.length} bugs...`)
for (const bug of injectableBugs) {
    await agent(`Run: python .claude/benchmarks/bughunt/bug_injection.py inject ${bug.id}`, {label:'inj-'+bug.id, phase:'Inject'})
}

function buildBarePrompt(bug) {
    return `BUG_ID: ${bug.id}  ← JSON的bug_id必须为此值

调查这个bug并给出诊断:

Bug: ${bug.d}
语言: ${bug.l}

请读取相关代码文件，找出根因，给出修复方案。

返回JSON: {bug_id,classification,classification_reason,evidence,trace,root_cause,root_cause_file_line,cf_evidence,fix_description,confidence,latent_issues}`
}

// ============================================================
phase('Investigate')
const N = BUGS.length
log(`Spawning ${N} 缉凶 + ${N} 裸 agents in parallel (${N*2} total)...`)

const allAgents = [
    ...BUGS.map(b => () => agent(buildPrompt(b), {label:'zx-'+b.id, phase:'Investigate', agentType:'debugger', schema:AGENT_SCHEMA})),
    ...BUGS.map(b => () => agent(buildBarePrompt(b), {label:'bare-'+b.id, phase:'Investigate', agentType:'debugger', schema:AGENT_SCHEMA})),
]

const allReports = await parallel(allAgents)
const zxReports = allReports.slice(0, N)
const bareReports = allReports.slice(N, N*2)

log(`缉凶: ${zxReports.filter(Boolean).length}/${N} | 裸: ${bareReports.filter(Boolean).length}/${N}`)

function match(reportsArr, bugId, idx) {
    const r = reportsArr.find(r => r && r.bug_id===bugId)
    return r || reportsArr[idx] || null
}

// ============================================================
phase('Revert')
for (const bug of injectableBugs) {
    await agent(`Run: python .claude/benchmarks/bughunt/bug_injection.py revert ${bug.id}`, {label:'rev-'+bug.id, phase:'Revert'})
}
log('Reverted')

// ============================================================
phase('Judge')
log(`Cross-model judging: Sonnet judges ${N*2} reports`)

async function judgeSkill(reportsArr, prefix) {
    const results = {}
    for (const bug of BUGS) {
        const r = match(reportsArr, bug.id, BUGS.indexOf(bug))
        if (!r || !r.root_cause) { results[bug.id]=null; continue }
        const verdict = await agent(buildJudgePrompt(r,bug), {label:'judge-'+prefix+'-'+bug.id, phase:'Judge', model:'sonnet'})
        try {
            const v = typeof verdict==='string' ? JSON.parse((verdict.match(/\{[^}]+\}/)||['{}'])[0]) : (verdict||{})
            results[bug.id] = {evidence:parseInt(v.evidence)||0, root_cause:parseInt(v.root_cause)||0, cf:parseInt(v.cf)||0, reasoning:v.reasoning||''}
        } catch { results[bug.id]=null }
        log(`  ${prefix}-${bug.id}: ${results[bug.id]?`E=${results[bug.id].evidence} R=${results[bug.id].root_cause} C=${results[bug.id].cf}`:'FAIL'}`)
    }
    return results
}

const zxJudge = await judgeSkill(zxReports, 'zx')
const bareJudge = await judgeSkill(bareReports, 'bare')
log(`Judged: 缉凶 ${Object.values(zxJudge).filter(Boolean).length}/${N} | 裸 ${Object.values(bareJudge).filter(Boolean).length}/${N}`)

// ============================================================
phase('Report')

function makeScores(reportsArr, judgeResults, prefix) {
    return BUGS.map((b,i) => {
        const r = match(reportsArr,b.id,i)
        if (!r||!r.root_cause) return {bug_id:b.id,gt_type:GT[b.id].t,agent_type:'?',inj:b.inj,judged:!!judgeResults[b.id],skill:prefix,
            c1:0,c2:0,c3:0,c4:0,c5:0,c6:0,c7:0,total:0,max:8,l3:'WRONG',kw:0,kwT:0,fm:false,fnm:false,txt:'',conf:0}
        const g=GT[b.id]; const jr=judgeResults[b.id]||null
        const txt=((r.root_cause||'')+' '+(r.root_cause_file_line||'')).toLowerCase()
        const at=(r.classification||'').trim().substring(0,2)
        const fm=txt.includes(g.f.toLowerCase()); const fnm=txt.includes(g.fn.toLowerCase())
        const kwHits=g.kw.filter(k=>txt.includes(k.toLowerCase()))
        const c1=at===g.t?1:0; const c2=(r.evidence&&r.trace&&r.root_cause&&r.cf_evidence&&r.fix_description)?1:0
        const c3=jr?jr.evidence:((r.evidence||'').length>30?1:0)
        const c4=jr?jr.root_cause:((fm&&fnm)?2:(fm||kwHits.length>=Math.ceil(g.kw.length*0.3))?1:0)
        const c5=jr?jr.cf:((r.cf_evidence||'').length>30?1:0)
        const c6=(r.fix_description||'').length>15?1:0; const c7=c2
        let l3='TEMPLATE'
        if(jr){const jo=[c3,c4,c5].filter(x=>x>0).length; if(jo===3&&c1)l3='REAL'; else if(jo>=2&&c1)l3='REAL*'; else if(jo===0)l3='WRONG'}
        else if(c4===2&&c1)l3='REAL'; else if(c4>=1&&c1)l3='REAL*'
        return {bug_id:b.id,gt_type:g.t,agent_type:at,inj:b.inj,judged:!!jr,skill:prefix,
            c1,c2,c3,c4,c5,c6,c7,total:c1+c2+c3+c4+c5+c6+c7,max:8,l3,kw:kwHits.length,kwT:g.kw.length,fm,fnm,txt:txt.substring(0,60),conf:r.confidence||0}
    })
}

const zxScores = makeScores(zxReports, zxJudge, '缉凶')
const bareScores = makeScores(bareReports, bareJudge, '裸')

function stats(scores) {
    const t=scores.reduce((a,s)=>a+s.total,0); const n=scores.length
    return {total:t,pct:(t/(n*8)*100).toFixed(1),cls:scores.filter(s=>s.c1).length,chn:scores.filter(s=>s.c2).length,
        roo:scores.filter(s=>s.c4===2).length,rpa:scores.filter(s=>s.c4===1).length,
        l3r:scores.filter(s=>s.l3==='REAL'||s.l3==='REAL*').length,
        l3w:scores.filter(s=>s.l3==='WRONG').length,
        conf:scores.filter(s=>s.conf>0).reduce((a,s)=>a+s.conf,0)/Math.max(1,scores.filter(s=>s.conf>0).length),
    }
}

const zx = stats(zxScores); const ba = stats(bareScores)
const delta = parseFloat(zx.pct)-parseFloat(ba.pct)

log('============================================')
log(`试剑石 v2.1 — ${N} Bug 多Skill对比`)
log('============================================')
log(`缉凶 v2.2: ${zx.total}/${N*8} = ${zx.pct}% | T:${zx.cls}/${N} C:${zx.chn}/${N} R:${zx.roo}(+${zx.rpa}p) L3:${zx.l3r}R ${zx.l3w}W | conf=${zx.conf.toFixed(2)}`)
log(`裸跑: ${ba.total}/${N*8} = ${ba.pct}% | T:${ba.cls}/${N} C:${ba.chn}/${N} R:${ba.roo}(+${ba.rpa}p) L3:${ba.l3r}R ${ba.l3w}W | conf=${ba.conf.toFixed(2)}`)
log(`Δ: ${delta>0?'+':''}${delta.toFixed(1)}% (Skill提升)`)
log('')
log('Per-Bug Comparison:')
log('  Bug | GT | 缉凶 T | 裸 T | 缉凶得分 | 裸得分 | 缉凶L3 | 裸L3')
log('  ----|----|-------|------|---------|--------|-------|-----')
for (let i=0; i<N; i++) {
    const z=zxScores[i]; const b=bareScores[i]
    if (!z) continue
    log(`  ${z.bug_id} | ${z.gt_type} | ${z.agent_type} | ${b?b.agent_type:'?'} | ${z.total}/8 | ${b?b.total:'-'}/8 | ${z.l3} | ${b?b.l3:'-'}`)
}
log('')
const gate = parseFloat(zx.pct)>=50 && zx.cls>=Math.floor(N*0.5) && zx.chn>=Math.floor(N*0.9)
log(`Gate: ${gate?'PASS':'FAIL'} | Skill value: ${delta>0?'+':''}${delta.toFixed(1)}%`)

return {
    zx_total:zx.total, bare_total:ba.total, delta:parseFloat(delta.toFixed(1)),
    zx_pct:parseFloat(zx.pct), bare_pct:parseFloat(ba.pct),
    gate:gate?'PASS':'FAIL', N,
    zx,zxScores, bare:ba,bareScores,
}
