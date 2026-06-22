export const meta = {
    name: '试剑石 Bonus Bug Check',
    description: 'Exp C: 检测 agent 发现真bug但非GT的模式。跑在 T2 judge 之后。$0.03, 10 bugs。',
    phases: [
        { title: 'Check', detail: '10 bugs 并行 bonus 检测' },
        { title: 'Report', detail: '汇总 prevalence 数据' },
    ],
}

// GT keywords for each bug — what the "correct" answer should point to
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

function buildBonusCheckPrompt(bugId, agentReport) {
    const gt = GT[bugId]
    return `检查 agent 的 bug report 是否发现了真实但非 GT 的 bug。

Bug ID: ${bugId}
预期 GT 类型: ${gt.t}, 文件: ${gt.f}, 函数: ${gt.fn}, 关键词: ${gt.kw.join(', ')}

Agent 报告:
- 分类: ${agentReport.classification}
- 根因: ${agentReport.root_cause}
- 文件: ${agentReport.root_cause_file_line}
- 修复: ${agentReport.fix_description}
- 置信度: ${agentReport.confidence}

判断标准:
1. agent 找到了代码库中真实存在的问题吗? (不是幻觉/编造)
2. agent 的发现与 GT 指向的是同一个 bug 吗? (比对文件+函数+根因方向)
3. 如果 agent 发现的是真问题但不是 GT 指定的那个 → bonus_real_bug=true

返回 JSON: {bug_id, is_real_issue (bool), matches_gt (bool), bonus_real_bug (bool), reasoning (1句话)}`
}

// ===== MAIN =====
// NOTE: 这个 workflow 需要 T2 的 agent report 作为输入。
// 在 T2 完成后，取每个 bug 的 agent classification/root_cause/file/fix 传入。
// args 格式: [{bug_id:'B01', classification:'T0', root_cause:'...', root_cause_file_line:'...', fix_description:'...', confidence:0.9}, ...]

phase('Check')
const bonusResults = await parallel(
    args.reports.map(r => () =>
        agent(buildBonusCheckPrompt(r.bug_id, r), {
            label: `bonus:${r.bug_id}`,
            schema: {
                type: 'object',
                properties: {
                    bug_id: {type:'string'},
                    is_real_issue: {type:'boolean'},
                    matches_gt: {type:'boolean'},
                    bonus_real_bug: {type:'boolean'},
                    reasoning: {type:'string'},
                },
                required: ['bug_id','is_real_issue','matches_gt','bonus_real_bug']
            }
        })
    )
)

phase('Report')
const clean = bonusResults.filter(Boolean)
const bonusCount = clean.filter(r => r.bonus_real_bug).length
const realIssueCount = clean.filter(r => r.is_real_issue).length
const matchCount = clean.filter(r => r.matches_gt).length

log(`Bonus Bug Check Results (${clean.length} bugs):`)
log(`  Found real issue (any): ${realIssueCount}/${clean.length}`)
log(`  Matches GT: ${matchCount}/${clean.length}`)
log(`  BONUS (real but not GT): ${bonusCount}/${clean.length}`)
log(`  Prevalence: ${(bonusCount/clean.length*100).toFixed(0)}%`)

if (bonusCount >= 3) {
    log(`[DECISION] >=3/10 bonus bugs → scoring system needs bonus dimension`)
} else if (bonusCount <= 1) {
    log(`[DECISION] <=1/10 bonus bugs → B03/B04 likely noise, no scoring change`)
} else {
    log(`[DECISION] 2/10 borderline → run 1 more T2 to confirm`)
}

for (const r of clean) {
    if (r.bonus_real_bug) {
        log(`  ${r.bug_id}: BONUS — ${r.reasoning}`)
    }
}

return {
    bonus_count: bonusCount,
    real_issue_count: realIssueCount,
    gt_match_count: matchCount,
    prevalence_pct: (bonusCount/clean.length*100),
    details: clean,
    decision: bonusCount >= 3 ? 'ADD_BONUS_DIMENSION' : bonusCount <= 1 ? 'NOISE' : 'BORDERLINE',
}
