export const meta = {
    name: '试剑石 T2 Lean',
    description: 'T2 精简版 — 只跑指定 bugs (~$0.05/bug)。用于重跑失败 case、候选验证。',
    phases: [
        { title: 'Investigate', detail: '并行调查指定 bugs' },
        { title: 'Judge', detail: '1 Sonnet judge' },
        { title: 'Report', detail: '分数 + 成长触发' },
    ],
}

// Default: all env-only bugs (no injection overhead)
// Pass args.bugs to override: ["B03","B05","B07"]
const ALL_BUGS = [
    {id:'B01',d:'campus_go 活动列表 API /api/activities 在数据库为空时返回 500 错误。有活动时正常。curl http://139.196.50.134/api/activities → 500',t:'T0',l:'Go'},
    {id:'B02',d:'campus_go 活动报名接口偶尔出现同一学生报了两次名。正常逻辑应阻止重复报名，偶发同一个人同一活动出现两条记录。约每20-30次一次。',t:'T1',l:'Go'},
    {id:'B03',d:'campus_go 中 college_admin 有时能看到并操作其他学院的活动。权限设计是只管自己学院，偶尔跨学院操作成功。跟学院名包含特殊字符或部分匹配有关。',t:'T2',l:'Go'},
    {id:'B04',d:'campus_go 学生志愿时长统计页面总时长偶尔比实际短。没报错没crash，数字不对。学生反映签了10小时只显示7小时。',t:'T3',l:'Python'},
    {id:'B05',d:'campus_go JWT token 刷新 /api/token/refresh 昨天能用今天全401。代码没改，服务器重启过。',t:'T4',l:'Go'},
    {id:'B06',d:'campus_go 活动报名后状态一直pending不会变confirmed。审批流程是自动的(不需人工审核)。学生等2小时状态没变。',t:'T5',l:'Go'},
    {id:'B07',d:'campus_go 测试本机全通过(go test ./... PASS)但 CI TestListActivities 一直失败。本机Go1.22 CI Go1.23。panic nil pointer dereference。',t:'T6',l:'Mixed'},
    {id:'B08',d:'用户反馈 campus_go 我的报名列表只显示已确认活动不显示待审批。用户认为这是bug——报名了看不到以为没报上又报一次。',t:'T7',l:'Go'},
    {id:'B09',d:'Python 后端学生积分更新偶尔不生效。完成活动积分应立刻增加，有时刷新页面还是旧的。再刷一次对了。不是每次都发生。',t:'T1',l:'Python'},
    {id:'B10',d:'campus_go 活动列表越来越慢。50个活动100ms，200个需3秒。没报错API正常200——就是慢。用户抱怨刷列表要等半天。',t:'T3',l:'Go'},
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
    return `BUG_ID: ${bug.id}  ← JSON必须填此值

使用缉凶 skill v2.5.1 的完整合同链调查此 bug。

Bug描述: ${bug.d}
技术栈: ${bug.l}

严格按 skill 的合同链执行: [分类]→[证据]→[追踪]→[分析]→[修复]→[验证]→[记录]
遵循所有 Red Lines、致命误判表 F1-F6、决策流、Gotchas、T4 强制配置检查。

返回JSON: {bug_id,classification,classification_reason,evidence,trace,root_cause,root_cause_file_line,cf_evidence,fix_description,confidence,latent_issues}`
}

function buildBatchJudgePrompt(reports) {
    let p = `你是独立评分agent。一次评估以下全部 ${reports.length} 个 bug report。每 report 评 3 维。

评分标准:
- 证据充分性 (0|1): 1=有具体复现步骤+可验证的baseline输出, 0=笼统描述无具体数据
- 根因正确性 (0|1|2): 2=根因方向与GT方向一致+有file:line引用, 1=方向对但细节/文件不同, 0=方向完全错误或不相关
  ⚠ 不要用关键词匹配。"方向一致"=agent找到的根因和GT指向同一个问题领域。
- CF真实性 (0|1): 1=有pre/post可验证证据(T3必须含数值对比), 0=模板文字无具体对比

`
    for (const {r, bug} of reports) {
        if (!r || !r.root_cause) continue
        const g = GT[bug.id]
        p += `---
Bug ${bug.id} (GT Type:${g.t} | GT根因方向:${g.kw.slice(0,5).join(' ')})
Agent分类: ${r.classification||'?'}
Agent证据: ${(r.evidence||'').substring(0,250)}
Agent根因: ${(r.root_cause||'').substring(0,250)}
Agent文件行: ${r.root_cause_file_line||'N/A'}
Agent CF: ${(r.cf_evidence||'').substring(0,250)}
`
    }
    p += `---
返回JSON数组: [{"bug_id":"Bxx","evidence":0|1,"root_cause":0|1|2,"cf":0|1,"reasoning":"根因方向一致性判断依据"}, ...]`
    return p
}

const AGENT_SCHEMA = {
    type:'object', properties:{
        bug_id:{type:'string'}, classification:{type:'string'}, classification_reason:{type:'string'},
        evidence:{type:'string'}, trace:{type:'string'}, root_cause:{type:'string'},
        root_cause_file_line:{type:'string'}, cf_evidence:{type:'string'},
        fix_description:{type:'string'}, confidence:{type:'number'}, latent_issues:{type:'string'},
    }, required:['bug_id','classification','evidence','trace','root_cause','cf_evidence','fix_description'],
}

// ===== MAIN =====
const targetIds = (args && args.bugs) ? args.bugs : ALL_BUGS.map(b=>b.id)
const BUGS = ALL_BUGS.filter(b => targetIds.includes(b.id))
log(`Lean T2: ${BUGS.length} bugs (${BUGS.map(b=>b.id).join(',')})`)

phase('Investigate')
const results = await parallel(BUGS.map(b => () => agent(buildPrompt(b), {label:'zx-'+b.id, agentType:'debugger', schema:AGENT_SCHEMA})))
const allReports = {}
BUGS.forEach((b,i) => { allReports[b.id] = results[i] })
log(`Investigated: ${results.filter(Boolean).length}/${BUGS.length}`)

phase('Judge')
const judgeInput = BUGS.map(bug => ({r: results[BUGS.indexOf(bug)], bug}))
const batchVerdict = await agent(buildBatchJudgePrompt(judgeInput), {label:'batch-judge', model:'sonnet'})

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
            judgeResults[v.bug_id] = {evidence:parseInt(v.evidence)||0, root_cause:parseInt(v.root_cause)||0, cf:parseInt(v.cf)||0, reasoning:v.reasoning||''}
        })
    }
} catch(e) { log(`Judge error: ${e}`) }

phase('Report')
function makeScores() {
    return BUGS.map(b => {
        const r = results[BUGS.indexOf(b)]
        if (!r||!r.root_cause) return {bug_id:b.id,gt_type:GT[b.id].t,agent_type:'?',total:0,c1:0,c2:0,c3:0,c4:0,c5:0,c6:0,c7:0,l3:'WRONG'}
        const g=GT[b.id]; const jr=judgeResults[b.id]||null
        const at=(r.classification||'').trim().substring(0,2)
        const hasFileLine = !!(r.root_cause_file_line)
        const c1=at===g.t?1:0
        const c2=(r.evidence&&r.trace&&r.root_cause&&r.cf_evidence&&r.fix_description)?1:0
        const c3=jr?jr.evidence:((r.evidence||'').length>30 && hasFileLine?1:0)
        const c4=jr?jr.root_cause:(hasFileLine?1:0)
        const c5=jr?jr.cf:((r.cf_evidence||'').length>30?1:0)
        const c6=(r.fix_description||'').length>15?1:0
        const c7=c2
        let l3='TEMPLATE'
        if(jr){const jo=[c3,c4,c5].filter(x=>x>0).length; if(jo===3&&c1)l3='REAL'; else if(jo>=2&&c1)l3='REAL*'; else if(jo===0)l3='WRONG'}
        else if(c4===2&&c1)l3='REAL'; else if(c4>=1&&c1)l3='REAL*'
        return {bug_id:b.id,gt_type:g.t,agent_type:at,total:c1+c2+c3+c4+c5+c6+c7,c1,c2,c3,c4,c5,c6,c7,l3,conf:r.confidence||0}
    })
}

const scores = makeScores()
const total = scores.reduce((a,s)=>a+s.total,0)
const pct = scores.length>0 ? (total/(scores.length*8)*100).toFixed(1) : 0

// Growth trigger check
const growthCandidates = scores.filter(s => s.total <= 5)
const growthIds = growthCandidates.map(s => s.bug_id)

log('============================================')
log(`T2 Lean — ${scores.length} bugs | Score: ${total}/${scores.length*8} = ${pct}%`)
if (growthIds.length > 0) {
    log(`[GROWTH] ${growthIds.length} candidates for growth: [${growthIds.join(',')}]`)
    log(`[GROWTH] Run again for 2nd ≤5/8 → trigger GEPA analysis`)
}
log('Bug | GT | Agent | Score | Judge(E/R/C)')
for (const s of scores) {
    const jr = judgeResults[s.bug_id]
    const grow = s.total <= 5 ? ' ← GROWTH' : ''
    log(` ${s.bug_id} | ${s.gt_type} | ${s.agent_type} | ${s.total}/8 | ${jr?jr.evidence+'/'+jr.root_cause+'/'+jr.cf:'rule'}${grow}`)
}

return { total, pct: parseFloat(pct), scores, judgeResults, growth_candidates: growthIds, cost: `~$0.${scores.length}0` }
