export const meta = {
    name: 'Validate F7',
    description: 'F7候选验证: T4 token/401 → curl test before code。B05 only ×3。$0.15。',
    phases: [
        { title: 'F7-R1', detail: 'B05 with F7' },
        { title: 'F7-R2', detail: 'B05 with F7' },
        { title: 'F7-R3', detail: 'B05 with F7' },
        { title: 'Decide', detail: 'mean ≥6/8? → MERGE : DISCARD' },
    ],
}

const B05 = {id:'B05',d:'campus_go JWT token 刷新 /api/token/refresh 昨天能用今天全401。代码没改，服务器重启过。',t:'T4',l:'Go'}
const GT_B05 = {t:'T4',f:'nginx-campus.conf',fn:'proxy_pass',kw:'nginx proxy_pass port 9500 9501 restart config revert deploy redirect'.split(' ')}

function buildPrompt(bug) {
    return `BUG_ID: ${bug.id}

使用缉凶 skill v2.5.1 + F7 实验规则调查此 bug。

Bug描述: ${bug.d}
技术栈: ${bug.l}

严格按 skill 的合同链执行。额外规则:

F7 (实验): "T4 + token/401/认证症状 → 第一步不是读代码。第一步是 curl 测试。
  curl 直连后端端口(绕过nginx) → 后端正常返回? → nginx 问题。
  后端也 401? → 代码/JWT 问题。
  不经过此网络测试不许打开 auth.go 或任何 .go 源码文件。"

返回JSON: {bug_id,classification,classification_reason,evidence,trace,root_cause,root_cause_file_line,cf_evidence,fix_description,confidence,latent_issues}`
}

function buildJudgePrompt(reports) {
    const r = reports[0]
    return `评分 B05。GT Type:T4, GT根因方向:nginx proxy_pass port 9500 9501。

Agent分类: ${r.r.classification||'?'}
Agent证据: ${(r.r.evidence||'').substring(0,300)}
Agent根因: ${(r.r.root_cause||'').substring(0,300)}
Agent文件行: ${r.r.root_cause_file_line||'N/A'}
Agent CF: ${(r.r.cf_evidence||'').substring(0,200)}

评分(3维):
- 证据 (0|1): 有具体复现+baseline? 1=有, 0=无
- 根因 (0|1|2): 方向与GT一致? 2=一致, 1=方向对细节不同, 0=完全不一致
- CF (0|1): 有pre/post可验证证据? 1=有, 0=无

返回JSON: {evidence:0|1, root_cause:0|1|2, cf:0|1, reasoning:"一句话"}`
}

const AGENT_SCHEMA = {
    type:'object', properties:{
        bug_id:{type:'string'}, classification:{type:'string'}, classification_reason:{type:'string'},
        evidence:{type:'string'}, trace:{type:'string'}, root_cause:{type:'string'},
        root_cause_file_line:{type:'string'}, cf_evidence:{type:'string'},
        fix_description:{type:'string'}, confidence:{type:'number'}, latent_issues:{type:'string'},
    }, required:['bug_id','classification','evidence','trace','root_cause','cf_evidence','fix_description'],
}

// Run 3 times, sequential — each is independent
const allScores = []

for (let run = 1; run <= 3; run++) {
    phase('F7-R'+run)
    const result = await agent(buildPrompt(B05), {label:'f7-b05-r'+run, agentType:'debugger', schema:AGENT_SCHEMA})
    if (!result) { allScores.push(null); continue }

    const judgeVerdict = await agent(buildJudgePrompt([{r: result, bug: B05}]), {label:'judge-r'+run, model:'sonnet'})
    let jr = {evidence:0, root_cause:0, cf:0}
    try {
        const text = typeof judgeVerdict === 'string' ? judgeVerdict : JSON.stringify(judgeVerdict)
        const m = text.match(/\{[\s\S]*\}/)
        if (m) jr = JSON.parse(m[0])
    } catch(e) {}

    const at = (result.classification||'').trim().substring(0,2)
    const c1 = at === 'T4' ? 1 : 0
    const c2 = (result.evidence && result.trace && result.root_cause && result.cf_evidence && result.fix_description) ? 1 : 0
    const c3 = jr.evidence || 0
    const c4 = jr.root_cause || 0
    const c5 = jr.cf || 0
    const c6 = (result.fix_description||'').length > 15 ? 1 : 0
    const c7 = c2
    const total = c1+c2+c3+c4+c5+c6+c7

    allScores.push({run, total, c1, c4, root_cause: jr.root_cause, reasoning: jr.reasoning})
    log(`F7 R${run}: ${total}/8 | root_cause=${jr.root_cause} | ${jr.reasoning||''}`)
}

phase('Decide')
const validScores = allScores.filter(Boolean)
const mean = validScores.reduce((a,s)=>a+s.total,0) / validScores.length
const rootMean = validScores.reduce((a,s)=>a+s.root_cause,0) / validScores.length

log(`F7 Validation: mean=${mean.toFixed(1)}/8, root_cause mean=${rootMean.toFixed(1)}/2`)
log(`Baseline B05: mean=5.3/8, root_cause=0.0 (3 runs)`)

const decision = mean >= 6.0 ? 'MERGE' : 'DISCARD'
log(`[DECISION] ${decision} — F7 ${decision === 'MERGE' ? 'improves B05 → add to production skill' : 'does not help → discard'}`)

return { candidate: 'F7', mean, root_mean: rootMean, baseline_mean: 5.3, decision, scores: validScores }
