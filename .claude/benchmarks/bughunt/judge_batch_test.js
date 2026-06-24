export const meta = {
    name: 'Judge批处理验证',
    description: '验证 batch judge (1 agent评10 bug) vs 独立judge (10 agent) 评分一致性',
    phases: [
        { title: 'BatchJudge', detail: '1 Sonnet agent judges all 10 reports' },
        { title: 'Compare', detail: '对比 batch vs individual 分数差异' },
    ],
}

// v2.4 缉凶 agent 原始报告 (从 workflow output 提取)
const REPORTS = [
    {bug_id:"B01",classification:"T0",evidence:"curl /api/activities → 500。campus_check baseline。空DB触发，有数据时正常。",root_cause:"ListActivities (activities.go) 在 for rows.Next() 循环后缺少 rows.Err() 检查",root_cause_file_line:"activities.go:75",cf_evidence:"在循环后添加 rows.Err() 检查后，空数据库返回 200 而非 500",fix_description:"在 activities.go:75 的 for rows.Next() 循环后添加 if err := rows.Err(); err != nil { log.Printf(...); c.JSON(500,...); return }",confidence:0.85},
    {bug_id:"B02",classification:"T1",evidence:"并发测试：10并发 → 2条重复。单请求偶发，频率约5%。",root_cause:"Signup handler INSERT 语句缺少 ON CONFLICT (activity_id, user_id) DO NOTHING",root_cause_file_line:"activities.go:205",cf_evidence:"添加 ON CONFLICT → 并发测试 0 重复",fix_description:"在 activities.go:205 INSERT 语句添加 ON CONFLICT (activity_id, user_id) DO NOTHING",confidence:0.99},
    {bug_id:"B03",classification:"T2",evidence:"测试：学院A'计算机'=正常可只看本院。学院B'计算机(师范)'=可看到A院活动。",root_cause:"ListActivities SQL 缺少 college 级过滤。college_admin 应只看到本院或 scope_type='all' 的活动",root_cause_file_line:"activities.go:28-38",cf_evidence:"添加 WHERE (a.college=$4 OR a.scope_type='all') → 学院B不再能看到A院活动",fix_description:"在 activities.go SQL 中添加 college 过滤：AND (a.college=$4 OR a.scope_type='all')",confidence:0.95},
    {bug_id:"B04",classification:"T3",evidence:"GET /api/my-stats → hours:7.0。数据库 SUM=10.0。差值 3.0 固定。每次请求结果一致(总是7.0)。",root_cause:"Python 后端 main.py 和 main_remote.py 证书生成逻辑中 participant_hours 使用 int() 截断而非 round()",root_cause_file_line:"main.py:1083-1095",cf_evidence:"int(3.5)→3, sum(3,2,4)=9 ≠ 10。改 round()→sum(4,2,5)=11≈10。修复前=7.0，修复后=10.0。",fix_description:"将 int(hours) 改为 round(hours) at main.py line ~1088",confidence:0.78},
    {bug_id:"B05",classification:"T4",evidence:"git log → 3天无代码变更。服务器重启时间 = bug 首次出现时间。",root_cause:"nginx proxy_pass 指向旧端口 9500 (Python 旧后端)，非当前 Go 后端端口 9501。重启后 nginx 配置回退",root_cause_file_line:"nginx-campus.conf: proxy_pass",cf_evidence:"改 proxy_pass 为 9501 → token 刷新恢复正常",fix_description:"修改 nginx-campus.conf proxy_pass http://127.0.0.1:9501",confidence:1.0},
    {bug_id:"B06",classification:"T0",evidence:"代码编译失败：go build 报错 undefined: sql。编译错误 100% 复现。",root_cause:"Signup 函数 (activities.go:193) 使用 sql.NullBool 但未导入 database/sql",root_cause_file_line:"activities.go:193-194",cf_evidence:"改用 plain bool + 正确错误处理 → 编译通过 → 活动自动审批正常",fix_description:"移除 sql.NullBool，改用 bool。添加正确错误处理。",confidence:1.0},
    {bug_id:"B07",classification:"T6",evidence:"本机 go1.22 PASS。CI go1.23 panic。环境差异复现。",root_cause:"双重根因:ListActivities 工厂函数接受 *pgxpool.Pool 但 CI 环境传入 nil；Go 1.23 改变了 NULL Scan 行为",root_cause_file_line:"activities.go:14,28",cf_evidence:"加 nil check + COALESCE → CI PASS",fix_description:"添加 db nil 检查 + SQL 中添加 COALESCE 保护 NULL 列",confidence:0.9},
    {bug_id:"B08",classification:"T7",evidence:"GetMySignups SQL: WHERE s.user_id=$1。无 status 过滤。返回所有报名记录。前端正确渲染所有状态。",root_cause:"NOT_A_BUG。产品设计：GetMySignups 返回全部报名状态，前端按状态分 tab 显示",root_cause_file_line:"dashboard.go:149",cf_evidence:"无需修改 — 行为符合产品设计",fix_description:"不修代码。产品建议:前端添加 tab 切换 pending/selected/waitlist",confidence:0.95},
    {bug_id:"B09",classification:"T1",evidence:"连续请求10次→2次积分未更新。同一输入结果不一致。baseline:10次正常全更新。",root_cause:"update_user_points() 是 async 函数，complete_activity handler 中调用时缺少 await 关键字。coroutine 未执行→GC 随机回收→间歇性不更新",root_cause_file_line:"main.py:1095",cf_evidence:"加 await → 连续100次全更新→0失败",fix_description:"在 main.py:1095 的 update_user_points() 调用前添加 await",confidence:0.95},
    {bug_id:"B10",classification:"T3",evidence:"50个活动→>2秒加载。200个活动→>5秒。每次结果一致(都慢)。API正常200。",root_cause:"ListActivities 的 signup_count 使用硬编码 0 as signup_count 替代原本的子查询 (SELECT COUNT(*) FROM signups...)",root_cause_file_line:"activities.go:30",cf_evidence:"恢复子查询→数据正确。添加索引→50活动<100ms",fix_description:"恢复 (SELECT COUNT(*) FROM signups WHERE activity_id=a.id) as signup_count 子查询。添加 signups.activity_id 索引。",confidence:0.95},
]

const GT = {
    B01:{t:'T0',kw:'nil deref empty rows.Err rows.Scan null pointer panic 500 crash'.split(' ')},
    B02:{t:'T1',kw:'SELECT INSERT race concurrent duplicate UNIQUE ON CONFLICT FOR UPDATE TOCTOU window'.split(' ')},
    B03:{t:'T2',kw:'strings.Contains college scope partial match comma split substring permission auth'.split(' ')},
    B04:{t:'T3',kw:'int round FLOAT duration truncat silent data loss sum certificate hour minute'.split(' ')},
    B05:{t:'T4',kw:'nginx proxy_pass port 9500 9501 restart config revert deploy redirect'.split(' ')},
    B06:{t:'T5',kw:'NULL default approval_required pending confirmed state machine stuck boolean migration status transfer'.split(' ')},
    B07:{t:'T6',kw:'Go 1.23 1.22 NULL Scan sqlite postgres COALESCE schema environment CI version mismatch'.split(' ')},
    B08:{t:'T7',kw:'NOT_A_BUG confirmed filter product design UI page link STOP no code fix'.split(' ')},
    B09:{t:'T1',kw:'await async coroutine event loop GC update points timing intermittent missing'.split(' ')},
    B10:{t:'T3',kw:'N+1 subquery correlated JOIN GROUP BY signup_count performance slow scale O(n) degrade index'.split(' ')},
}

// Build batch judge prompt — all 10 bugs in one call
function buildBatchJudgePrompt() {
    let p = `你是独立评分agent。一次评估以下全部 10 个 bug report。每个 report 评 3 个维度。

评分标准:
- 证据充分性 (evidence 0|1): 1=具体复现步骤+可验证baseline, 0=笼统
- 根因正确性 (root_cause 0|1|2): 2=根因方向一致+file:line正确, 1=方向对细节偏, 0=完全错误
- CF真实性 (cf 0|1): 1=有pre/post可验证证据, 0=模板文字

`
    for (const r of REPORTS) {
        const g = GT[r.bug_id]
        p += `---
Bug ${r.bug_id} (GT: ${g.t}, GT方向: ${g.kw.slice(0,4).join(' ')})
分类: ${r.classification}
证据: ${(r.evidence||'').substring(0,250)}
根因: ${(r.root_cause||'').substring(0,250)}
文件行: ${r.root_cause_file_line||'N/A'}
CF: ${(r.cf_evidence||'').substring(0,250)}
`
    }
    p += `---
返回JSON数组，每元素: {"bug_id":"Bxx","evidence":0|1,"root_cause":0|1|2,"cf":0|1,"reasoning":"一句话"}`
    return p
}

// ============================================================
phase('BatchJudge')
log('1 Sonnet agent judges all 10 bug reports in one call...')

const batchVerdict = await agent(buildBatchJudgePrompt(), {
    label: 'batch-judge-all',
    phase: 'BatchJudge',
    model: 'sonnet',
})

// Parse batch results
let batchResults = {}
try {
    const text = typeof batchVerdict === 'string' ? batchVerdict : JSON.stringify(batchVerdict)
    const match = text.match(/\[[\s\S]*\]/)
    if (match) {
        const arr = JSON.parse(match[0])
        for (const v of arr) {
            batchResults[v.bug_id] = {
                evidence: parseInt(v.evidence) || 0,
                root_cause: parseInt(v.root_cause) || 0,
                cf: parseInt(v.cf) || 0,
                reasoning: v.reasoning || '',
            }
        }
    }
} catch (e) {
    log(`Parse error: ${e}`)
}

// ============================================================
phase('Compare')

// v2.4 individual judge scores (from workflow output)
const individualResults = {
    B01: {evidence:1, root_cause:2, cf:1},  // judged:false — rule fallback
    B02: {evidence:1, root_cause:2, cf:1},  // judged:false — rule fallback
    B03: {evidence:1, root_cause:1, cf:1},  // Sonnet judge
    B04: {evidence:1, root_cause:2, cf:1},  // Sonnet judge
    B05: {evidence:1, root_cause:2, cf:1},  // Sonnet judge
    B06: {evidence:1, root_cause:2, cf:1},  // Sonnet judge
    B07: {evidence:1, root_cause:1, cf:1},  // Sonnet judge
    B08: {evidence:1, root_cause:2, cf:1},  // Sonnet judge
    B09: {evidence:1, root_cause:2, cf:1},  // Sonnet judge
    B10: {evidence:1, root_cause:2, cf:1},  // Sonnet judge
}

log('Bug | Ind E/R/C | Bat E/R/C | Match?')
log('----|----------|----------|-------')
let matchCount = 0
let totalDims = 0
for (const bugId of Object.keys(individualResults)) {
    const ind = individualResults[bugId]
    const bat = batchResults[bugId] || {evidence:-1, root_cause:-1, cf:-1}
    const eMatch = ind.evidence === bat.evidence
    const rMatch = ind.root_cause === bat.root_cause
    const cMatch = ind.cf === bat.cf
    const matches = [eMatch, rMatch, cMatch].filter(Boolean).length
    matchCount += matches
    totalDims += 3
    log(` ${bugId} | ${ind.evidence}/${ind.root_cause}/${ind.cf} | ${bat.evidence}/${bat.root_cause}/${bat.cf} | ${matches}/3 ${matches===3?'OK':''}`)
}
const agree = (matchCount/totalDims*100).toFixed(0)
log(``)
log(`Agreement: ${matchCount}/${totalDims} = ${agree}%`)
log(`Cost: batch=1 Sonnet call vs individual=10 Sonnet calls (90% savings)`)

return {
    batchResults,
    individualResults,
    matchCount,
    totalDims,
    agreement: parseFloat(agree),
    cost_savings: '90%',
}
