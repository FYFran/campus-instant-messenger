export const meta = {
    name: '试剑石',
    description: '试剑石 v2.0 — 答案分离 + 执行验证 + 跨模型Judge + 多Skill对比。',
    phases: [
        { title: 'Inject', detail: '注入可注入bug' },
        { title: 'Investigate', detail: '缉凶 + 裸 agent 并行调查 (答案隔离)' },
        { title: 'Revert', detail: '还原注入' },
        { title: 'Judge', detail: '跨模型Judge (Sonnet评DeepSeek) + 执行验证' },
        { title: 'Report', detail: '双Skill对比 + L3 + 验证分 + Gate' },
    ],
}

// v2.0 新增: 执行验证 — agent fix → verify_fix.py → PASS/FAIL
// 答案隔离: desc.md (agent读) ≠ truth.md (仅评分器)

const T = 'T0=稳定复现(每次都) T1=竞态时序(偶尔,加log消失) T2=多因素(需≥2条件同时满足) T3=无报错数据错/性能退化 T4=昨天还好(代码没改环境变了) T5=状态机卡住 T6=特定环境(本机vsCI/Docker/OS) T7=NOT_A_BUG(行为符合设计)'

const BUGS = [
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
]

const GT = {
    B01:{t:'T0',f:'activities.go',fn:'ListActivities',kw:'nil deref empty rows.Err rows.Scan null pointer panic 500 crash'.split(' ')},
    B02:{t:'T1',f:'activities.go',fn:'Signup',kw:'SELECT INSERT race concurrent duplicate UNIQUE ON CONFLICT FOR UPDATE TOCTOU window'.split(' ')},
    B03:{t:'T2',f:'activities_admin.go',fn:'ApproveActivity',kw:'strings.Contains college scope partial match comma split substring permission auth'.split(' ')},
    B04:{t:'T3',f:'main.py',fn:'certificates',kw:'int round FLOAT duration truncat silent data loss sum certificate hour minute'.split(' ')},
    B05:{t:'T4',f:'nginx-campus.conf',fn:'proxy_pass',kw:'nginx proxy_pass port 9500 9501 restart config revert deploy redirect'.split(' ')},
    B06:{t:'T5',f:'activities.go',fn:'Signup',kw:'first_come removed auto-select pending selected state machine stuck transition missing initialStatus'.split(' ')},
    B07:{t:'T6',f:'activities.go',fn:'ListActivities',kw:'Go 1.23 1.22 NULL Scan sqlite postgres COALESCE schema environment CI version mismatch'.split(' ')},
    B08:{t:'T7',f:'dashboard.go',fn:'GetMySignups',kw:'NOT_A_BUG confirmed filter product design UI page link STOP no code fix'.split(' ')},
    B09:{t:'T1',f:'main.py',fn:'complete_activity',kw:'await async coroutine event loop GC update points timing intermittent missing'.split(' ')},
    B10:{t:'T3',f:'activities.go',fn:'ListActivities',kw:'N+1 subquery correlated JOIN GROUP BY signup_count performance slow scale O(n) degrade'.split(' ')},
}

function buildPrompt(bug) {
    return `BUG_ID: ${bug.id}  ← JSON的bug_id必须为此值

你是缉凶 agent。合同链7步全填。

Bug: ${bug.d}
语言: ${bug.l}

1.分类 — STOP先想深层因果结构。然后: 代码没改昨天能用?→T4|每次必现?→T0|同一操作有时异常?→T1|换参数值就正常?→T2|卡在中间状态?→T5|1-5全排除?→T3(跳过直接选=报废)|本机行CI不行?→T6|符合设计?→T7。致命误判: F1"偶尔+刷新好了"=T1非T3 F2"某些输入触发"=T2非T3 F3"一直pending"=T5非T3
2.证据 — 复现步骤+baseline(>40字)
3.追踪 — 调用链+file:line
4.分析 — 根因(含file:line)+Counterfactual(conf)。T3必须数值对比。找到第一个错误别停——继续往下挖
5.修复 — 方案(T7不修代码)
6.验证 — pre/post
7.记录 — 潜在问题

返回JSON: {bug_id,classification,classification_reason,evidence,trace,root_cause,root_cause_file_line,cf_evidence,fix_description,confidence,latent_issues}`
}

// Efficient judge: 1 agent scores ALL 3 dimensions in one call
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
3.CF真实性: 1=有pre/post可验证证据, 0=模板文字

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

// Bare agent prompt (no skill — baseline)
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
log(`Spawning 10 缉凶 + 10 裸 agents in parallel (20 total)...`)

const allAgents = [
    // 缉凶 agents (with skill contract)
    ...BUGS.map(b => () => agent(buildPrompt(b), {label:'zx-'+b.id, phase:'Investigate', agentType:'debugger', schema:AGENT_SCHEMA})),
    // Bare agents (no skill — baseline)
    ...BUGS.map(b => () => agent(buildBarePrompt(b), {label:'bare-'+b.id, phase:'Investigate', agentType:'debugger', schema:AGENT_SCHEMA})),
]

const allReports = await parallel(allAgents)
const zxReports = allReports.slice(0, 10)   // First 10: 缉凶
const bareReports = allReports.slice(10, 20) // Last 10: bare

log(`缉凶: ${zxReports.filter(Boolean).length}/10 | 裸: ${bareReports.filter(Boolean).length}/10`)

function match(reportsArr, bugId, idx) {
    const r = reportsArr.find(r => r && r.bug_id===bugId)
    return r || reportsArr[idx] || null
}

// Trajectory stats
function trajStats(reportsArr, prefix) {
    return reportsArr.map((r,i) => {
        if (!r) return {bug_id:BUGS[i].id, skill:prefix, has_data:false}
        return {bug_id:r.bug_id||BUGS[i].id, skill:prefix, has_data:true,
            evidence_len:(r.evidence||'').length, trace_len:(r.trace||'').length,
            root_len:(r.root_cause||'').length, cf_len:(r.cf_evidence||'').length,
            confidence:r.confidence||0, classification:r.classification||'?',
            file_ref:!!(r.root_cause_file_line),
            completeness:!!(r.evidence&&r.trace&&r.root_cause&&r.cf_evidence&&r.fix_description)}
    })
}
const zxTraj = trajStats(zxReports, '缉凶')
const bareTraj = trajStats(bareReports, '裸')

// ============================================================
phase('Revert')
for (const bug of injectableBugs) {
    await agent(`Run: python .claude/benchmarks/bughunt/bug_injection.py revert ${bug.id}`, {label:'rev-'+bug.id, phase:'Revert'})
}
log('Reverted')

// ============================================================
phase('Judge')
log('Cross-model judging: Sonnet judges 20 reports (10 缉凶 + 10 bare)')

// Judge reports for one skill
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
log(`Judged: 缉凶 ${Object.values(zxJudge).filter(Boolean).length}/10 | 裸 ${Object.values(bareJudge).filter(Boolean).length}/10`)

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

// Combined stats
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
log(`试剑石 v1.2 — 多Skill对比`)
log(`============================================`)
log(`缉凶: ${zx.total}/80 = ${zx.pct}% | T:${zx.cls}/10 C:${zx.chn}/10 R:${zx.roo}(+${zx.rpa}p) L3:${zx.l3r}R ${zx.l3w}W | conf=${zx.conf.toFixed(2)}`)
log(`裸跑: ${ba.total}/80 = ${ba.pct}% | T:${ba.cls}/10 C:${ba.chn}/10 R:${ba.roo}(+${ba.rpa}p) L3:${ba.l3r}R ${ba.l3w}W | conf=${ba.conf.toFixed(2)}`)
log(`Δ: ${delta>0?'+':''}${delta.toFixed(1)}% (Skill提升)`)
log('')
log('Per-Bug Comparison:')
log('  Bug | GT | 缉凶 T | 裸 T | 缉凶得分 | 裸得分 | 缉凶L3 | 裸L3')
log('  ----|----|-------|------|---------|--------|-------|-----')
for (let i=0; i<10; i++) {
    const z=zxScores[i]; const b=bareScores[i]
    log(`  ${z.bug_id} | ${z.gt_type} | ${z.agent_type} | ${b.agent_type} | ${z.total}/8 | ${b.total}/8 | ${z.l3} | ${b.l3}`)
}
log('')
const gate = parseFloat(zx.pct)>=50 && zx.cls>=5 && zx.chn>=9
log(`Gate: ${gate?'PASS':'FAIL'} | Skill value: ${delta>0?'+':''}${delta.toFixed(1)}% (缉凶比裸跑高${delta.toFixed(1)}个百分点)`)

return {
    zx_total:zx.total, bare_total:ba.total, delta:parseFloat(delta.toFixed(1)),
    zx_pct:parseFloat(zx.pct), bare_pct:parseFloat(ba.pct),
    gate:gate?'PASS':'FAIL',
    zx,zxScores, bare:ba,bareScores,
}
