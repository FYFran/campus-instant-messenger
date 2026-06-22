export const meta = {
    name: '试剑石 T2',
    description: 'Tier 2 — 全调查+batch judge (~$0.5, ~5min)。10 缉凶 agent 并行 + 1 Sonnet batch judge。',
    phases: [
        { title: 'EnvBugs', detail: '7 env-only bugs 并行调查' },
        { title: 'Inj-B02', detail: '注入→调查→还原' },
        { title: 'Inj-B06', detail: '注入→调查→还原' },
        { title: 'Inj-B10', detail: '注入→调查→还原' },
        { title: 'Judge', detail: '1 Sonnet batch judge 评 10 报告' },
        { title: 'Report', detail: '8分制汇总' },
    ],
}

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
    B10:{t:'T3',f:'activities.go',fn:'ListActivities',kw:'N+1 subquery correlated JOIN GROUP BY signup_count performance slow scale O(n) degrade index'.split(' ')},
}

function buildPrompt(bug) {
    return `BUG_ID: ${bug.id}  ← JSON的bug_id必须为此值

你是缉凶 agent v2.7-hybrid。线性分类 + 可证伪假设追踪。

Bug: ${bug.d}
语言: ${bug.l}

合同链(8步全填):
0.分类+H — STOP先想深层因果结构。决策流: 代码没改昨天能用?→T4|每次必现crash/panic/500?→T0|同一操作有时异常?→T1|换参数值就正常?→T2|卡在中间状态回不来?→T5|1-5全排除了?→T3(跳过直接选=报废)|本机行CI不行?→T6|符合设计?→T7|症状可被配置差异解释且近期有部署/重启?→T4。致命误判: F1"偶尔+刷新好了"=T1非T3 F2"某些输入触发"=T2非T3 F3"一直pending"=T5非T3 F4"间歇但非竞态"=T3 F5"安全审查说"=T7 F6"昨天好+重启+代码没改"被当代码bug→T4专属配置检查通过前不许读源码。
  输出: Type: T___ 依据: ___ + 假设H: "如果我对，___应该为真。验证方法: ___"
  ⚠ T4必须走3步配置检查(nginx/env/port/startup log)才能读源码。3步全过无异常→门禁解除。

1.证据 — 复现步骤+baseline(>40字) + H验证结果: 成立/推翻(证据:___)
  如果H被推翻 → 查F1-F6找替代方向 → 修正分类+H2 → 重新收集证据。

2.追踪 — 调用链+file:line+Expected vs Actual。H被推翻→修正H2记录。

3.分析 — 根因(含file:line)+Counterfactual(conf)。T3必须数值对比。找到第一个错误别停——继续往下挖。

4.修复 — 方案(T7不修代码)

5.验证 — pre/post

6.记录 — 潜在问题

返回JSON: {bug_id,classification,classification_reason,hypothesis,falsifiable_test,evidence,h_verification,trace,root_cause,root_cause_file_line,cf_evidence,fix_description,confidence,latent_issues}`
}

function buildBatchJudgePrompt(reports) {
    let p = `你是独立评分agent。一次评估以下全部 ${reports.length} 个 bug report。每 report 评 4 维。

评分标准:
- 证据充分性 (0|1): 1=有具体复现步骤+可验证的baseline输出, 0=笼统描述无具体数据
- 根因正确性 (0|1|2): 2=根因方向与GT方向一致+有file:line引用, 1=方向对但细节/文件不同, 0=方向完全错误或不相关
  ⚠ 不要用关键词匹配。"方向一致"意思是:agent找到的根因和GT指向同一个问题领域。比如GT说"nginx端口配错"但agent说"JWT密钥丢失"→方向不同=0分。GT说"ON CONFLICT缺失导致竞态"但agent说"FOR UPDATE没添加导致并发插入"→方向一致(都是并发报名保护缺失)=2分。
- CF真实性 (0|1): 1=有pre/post可验证证据(T3必须含数值对比), 0=模板文字无具体对比
- bonus_real_bug (0|1): 1=agent发现了一个真实的代码问题(不是幻觉/瞎编),这个问题与GT不同(不同文件或不同根因方向),但确实是合法的bug。0=agent要么和GT一致,要么没发现任何真实问题。

`
    for (const {r, bug} of reports) {
        if (!r || !r.root_cause) continue
        const g = GT[bug.id]
        p += `---
Bug ${bug.id} (GT Type:${g.t} | GT根因方向:${g.kw.slice(0,5).join(' ')})
Agent分类: ${r.classification||'?'}
Agent假设H: ${(r.hypothesis||'').substring(0,200)}
Agent H验证: ${(r.h_verification||'').substring(0,150)}
Agent证据: ${(r.evidence||'').substring(0,250)}
Agent根因: ${(r.root_cause||'').substring(0,250)}
Agent文件行: ${r.root_cause_file_line||'N/A'}
Agent CF: ${(r.cf_evidence||'').substring(0,250)}
`
    }
    p += `---
返回JSON数组: [{"bug_id":"Bxx","evidence":0|1,"root_cause":0|1|2,"cf":0|1,"bonus_real_bug":0|1,"reasoning":"根因方向一致性+bonus判断依据"}, ...]`
    return p
}

const AGENT_SCHEMA = {
    type:'object', properties:{
        bug_id:{type:'string'}, classification:{type:'string'}, classification_reason:{type:'string'},
        hypothesis:{type:'string'}, falsifiable_test:{type:'string'},
        evidence:{type:'string'}, h_verification:{type:'string'}, trace:{type:'string'}, root_cause:{type:'string'},
        root_cause_file_line:{type:'string'}, cf_evidence:{type:'string'},
        fix_description:{type:'string'}, confidence:{type:'number'}, latent_issues:{type:'string'},
    }, required:['bug_id','classification','hypothesis','evidence','trace','root_cause','cf_evidence','fix_description'],
}

// ============================================================
// Serialized injection: inject→investigate→revert per injected bug
// Prevents cross-contamination when multiple bugs modify same file
// ============================================================

const envBugs = BUGS.filter(b => !b.inj)
const injBugs = BUGS.filter(b => b.inj)
const allReports = {}

// Phase 1: Investigate env-only bugs in parallel (no injection)
phase('EnvBugs')
log(`Investigating ${envBugs.length} env-only bugs in parallel...`)
const envResults = await parallel(envBugs.map(b => () => agent(buildPrompt(b), {label:'zx-'+b.id, phase:'EnvBugs', agentType:'debugger', schema:AGENT_SCHEMA})))
envBugs.forEach((b,i) => { allReports[b.id] = envResults[i] })
log(`Env bugs: ${envResults.filter(Boolean).length}/${envBugs.length}`)

// Phase 2+: Serialize each injected bug: inject→investigate→revert
for (const bug of injBugs) {
    phase('Inj-'+bug.id)
    log(`Inject ${bug.id}...`)
    await agent(`Run: python .claude/benchmarks/bughunt/bug_injection.py inject ${bug.id}`, {label:'inj-'+bug.id, phase:'Inj-'+bug.id})

    log(`Investigate ${bug.id}...`)
    const result = await agent(buildPrompt(bug), {label:'zx-'+bug.id, phase:'Inj-'+bug.id, agentType:'debugger', schema:AGENT_SCHEMA})
    allReports[bug.id] = result

    log(`Revert ${bug.id}...`)
    await agent(`Run: python .claude/benchmarks/bughunt/bug_injection.py revert ${bug.id}`, {label:'rev-'+bug.id, phase:'Inj-'+bug.id})
    log(`  ${bug.id}: ${result ? 'OK' : 'FAIL'}`)
}

function match(rid) {
    return allReports[rid] || null
}

log(`Total: ${Object.values(allReports).filter(Boolean).length}/${BUGS.length}`)

// ============================================================
phase('Judge')
log('1 Sonnet batch judge evaluates all reports...')

const judgeInput = BUGS.map(bug => ({r: match(bug.id), bug}))
const batchVerdict = await agent(buildBatchJudgePrompt(judgeInput), {label:'batch-judge', phase:'Judge', model:'sonnet'})

let judgeResults = {}
try {
    const text = typeof batchVerdict === 'string' ? batchVerdict : JSON.stringify(batchVerdict)
    let arr = null
    const m = text.match(/\[[\s\S]*\]/)
    if (m) { try { arr = JSON.parse(m[0]) } catch {} }
    if (!arr) {
        const cm = text.match(/```(?:json)?\s*([\s\S]*?)```/)
        if (cm) { const cm2 = cm[1].match(/\[[\s\S]*\]/); if (cm2) try { arr = JSON.parse(cm2[0]) } catch {} }
    }
    if (arr) {
        arr.forEach(v => {
            judgeResults[v.bug_id] = {evidence:parseInt(v.evidence)||0, root_cause:parseInt(v.root_cause)||0, cf:parseInt(v.cf)||0, bonus_real_bug:parseInt(v.bonus_real_bug)||0, reasoning:v.reasoning||''}
        })
    }
    if (Object.keys(judgeResults).length === 0) {
        log(`Judge parse failed. Raw (first 500): ${text.substring(0,500)}`)
    }
} catch(e) { log(`Judge parse error: ${e}`) }
log(`Judged: ${Object.keys(judgeResults).length}/${BUGS.length}`)

// ============================================================
phase('Report')

function makeScores() {
    return BUGS.map((b,i) => {
        const r = match(b.id)
        if (!r||!r.root_cause) return {bug_id:b.id,gt_type:GT[b.id].t,agent_type:'?',total:0,c1:0,c2:0,c3:0,c4:0,c5:0,c6:0,c7:0,l3:'WRONG'}
        const g=GT[b.id]; const jr=judgeResults[b.id]||null
        const at=(r.classification||'').trim().substring(0,2)
        const hasFileLine = !!(r.root_cause_file_line)
        // c1: T-Type string match (rule)
        const c1=at===g.t?1:0
        // c2: chain completeness (rule)
        const c2=(r.evidence&&r.trace&&r.root_cause&&r.cf_evidence&&r.fix_description)?1:0
        // c3: evidence (judge, or fallback: has file:line + evidence >30 chars)
        const c3=jr?jr.evidence:((r.evidence||'').length>30 && hasFileLine?1:0)
        // c4: root cause (judge, or conservative: has file:line → 1, else 0)
        const c4=jr?jr.root_cause:(hasFileLine?1:0)
        // c5: CF (judge, or fallback: CF >30 chars)
        const c5=jr?jr.cf:((r.cf_evidence||'').length>30?1:0)
        // c6: fix quality (rule)
        const c6=(r.fix_description||'').length>15?1:0
        // c7: trajectory (rule)
        const c7=c2
        let l3='TEMPLATE'
        if(jr){const jo=[c3,c4,c5].filter(x=>x>0).length; if(jo===3&&c1)l3='REAL'; else if(jo>=2&&c1)l3='REAL*'; else if(jo===0)l3='WRONG'}
        else if(c4===2&&c1)l3='REAL'; else if(c4>=1&&c1)l3='REAL*'
        return {bug_id:b.id,gt_type:g.t,agent_type:at,total:c1+c2+c3+c4+c5+c6+c7,c1,c2,c3,c4,c5,c6,c7,l3,conf:r.confidence||0}
    })
}

const scores = makeScores()
const total = scores.reduce((a,s)=>a+s.total,0)
const pct = (total/(BUGS.length*8)*100).toFixed(1)
const ttype = scores.filter(s=>s.c1).length
const chain = scores.filter(s=>s.c2).length
const real = scores.filter(s=>s.l3==='REAL'||s.l3==='REAL*').length
const bonusBugs = Object.values(judgeResults).filter(j=>j.bonus_real_bug).length
const bonusIds = Object.entries(judgeResults).filter(([k,v])=>v.bonus_real_bug).map(([k])=>k)

log('============================================')
log(`试剑石 T2 — ${BUGS.length} Bug Batch Judge`)
log('============================================')
log(`Score: ${total}/${BUGS.length*8} = ${pct}% | T-Type: ${ttype}/${BUGS.length} | Chain: ${chain}/${BUGS.length} | L3: ${real}R`)
log(`BONUS (real bug != GT): ${bonusBugs}/${BUGS.length} ${bonusIds.length ? '['+bonusIds.join(',')+']' : ''}`)
if (bonusBugs >= 3) log('[Exp C] >=3 bonus -> scoring needs bonus dimension')
else if (bonusBugs <= 1) log('[Exp C] <=1 bonus -> B03/B04 likely noise, no scoring change')
else log('[Exp C] 2 bonus -> borderline, run 1 more T2')
log('')
log('Bug | GT | Agent | Score | L3 | Judge(E/R/C/B)')
log('----|----|-------|-------|----|--------------')
for (const s of scores) {
    const jr = judgeResults[s.bug_id]
    const b = jr && jr.bonus_real_bug ? '★' : ''
    log(` ${s.bug_id} | ${s.gt_type} | ${s.agent_type} | ${s.total}/8 | ${s.l3} | ${jr?jr.evidence+'/'+jr.root_cause+'/'+jr.cf+'/'+b:'rule'}`)
}
log('')
log(`Cost: ~$0.5 (10 investigate + 1 batch judge) vs Tier 3 $5 (10 invest + 10 bare + 20 judge)`)

return {
    total, pct: parseFloat(pct), ttype, chain, real,
    bonus_count: bonusBugs, bonus_ids: bonusIds,
    exp_c_decision: bonusBugs >= 3 ? 'ADD_BONUS_DIMENSION' : bonusBugs <= 1 ? 'NOISE' : 'BORDERLINE',
    scores, judgeResults,
    cost: '~$0.50',
}
