export const meta = {
    name: '试剑石 A/B — 螺旋 vs 线性',
    description: 'Exp B: 同 3 bugs, 螺旋(v3.0-alpha) vs 线性(v2.5.1)。$0.15, ~2min。',
    phases: [
        { title: 'Spiral', detail: '3 bugs 螺旋合同链并行' },
        { title: 'Linear', detail: '3 bugs 线性合同链并行' },
        { title: 'Compare', detail: '对比 score/time/hypothesis quality' },
    ],
}

const COMPARE_BUGS = [
    {id:'B05',d:'campus_go JWT token 刷新 /api/token/refresh 昨天能用今天全401。代码没改，服务器重启过。',t:'T4',l:'Go'},
    {id:'B07',d:'campus_go 测试本机全通过(go test ./... PASS)但 CI TestListActivities 一直失败。本机Go1.22 CI Go1.23。panic nil pointer dereference。',t:'T6',l:'Mixed'},
    {id:'M03',d:'暴力破解/频率限制功能似乎完全不工作。无论多少次失败尝试，用户都不会被限流或锁定。代码中有完整的限流逻辑但似乎从未被触发。没有报错。',t:'T3',l:'Go'},
]

// ===== LINEAR PROMPT (v2.5.1 contract chain) =====
function buildLinearPrompt(bug) {
    return `BUG_ID: ${bug.id}

你是缉凶 agent v2.5.1。合同链7步全填。

Bug: ${bug.d}
语言: ${bug.l}

1.分类 — STOP先想深层因果结构。决策流: 代码没改昨天能用?→T4|每次必现crash/panic/500?→T0|同一操作有时异常?→T1|换参数值就正常?→T2|卡在中间状态回不来?→T5|1-5全排除了?→T3(跳过直接选=报废)|本机行CI不行?→T6|符合设计?→T7|症状可被配置差异解释且近期有部署/重启?→T4。致命误判: F1"偶尔+刷新好了"=T1非T3 F2"某些输入触发"=T2非T3 F3"一直pending"=T5非T3 F4"间歇但非竞态"=T3 F5"安全审查说"=T7 F6"昨天好+重启+代码没改"被当代码bug→T4专属配置检查通过前不许读源码。
⚠ 判T3前必须对照F1-F5。命中→改选。T4必须走3步配置检查(nginx/env/port/startup log)才能读源码。3步全过无异常→门禁解除。

2.证据 — 复现步骤+baseline(>40字)
3.追踪 — 调用链+file:line+Expected vs Actual
4.分析 — 根因(含file:line)+Counterfactual(conf)。T3必须数值对比。找到第一个错误别停——继续往下挖
5.修复 — 方案(T7不修代码)
6.验证 — pre/post
7.记录 — 潜在问题

返回JSON: {bug_id,classification,classification_reason,evidence,trace,root_cause,root_cause_file_line,cf_evidence,fix_description,confidence,latent_issues}`
}

// ===== SPIRAL PROMPT (v3.0-alpha hypothesis loop) =====
function buildSpiralPrompt(bug) {
    return `BUG_ID: ${bug.id}

你是缉凶 agent v3.0-alpha。螺旋假设驱动——不预分类，渐进逼近根因。

Bug: ${bug.d}
语言: ${bug.l}

螺旋循环:
[H1: 初始假设] → [验证H1] → [推翻?] → [H2: 修正假设] → [验证H2] → [确认] → [深度追踪] → [修复]

H1 规则: 读2遍bug描述→最可能出错的组件是什么?→生成一个可证伪的假设。
  证伪格式: "如果H1对，___应该为真/假。验证方法: ___"
  信号速查: crash/panic+稳定=代码错误 | 间歇+同操作不同结果=时序 | 间歇+不同输入=数据 | 昨天能用+重启=配置 | 卡住=状态机 | 没报错+数据不对=计算 | 本机OK+CI挂=环境

H1被推翻→记录推翻证据→查致命误判表找替代方向→生成H2。
F1:刷新变化→T1 F2:某些输入触发→T2 F3:一直pending→T5 F4:间歇非竞态→T3 F5:第三方报告→T7 F6:昨天好+重启→T4配置检查

3轮假设未确认→STOP。质疑架构。

H确认后:
- 证据: 复现步骤+baseline(>40字)
- 追踪: 调用链+file:line+Expected vs Actual
- 分析: 根因(含file:line)+Counterfactual(conf)。数值对比。
- 修复: 方案(如果NOT_A_BUG不修)
- 根因确认后贴T0-T7标签(用于统计)

返回JSON: {bug_id, classification (出口标签T0-T7), classification_reason, evidence, trace, root_cause, root_cause_file_line, cf_evidence, fix_description, confidence, hypothesis_chain: [{round:1, hypothesis, falsifiable_test, verification_result, confirmed:bool}, ...], latent_issues}`
}

// ===== COMPARE =====
function compareResults(spiral, linear) {
    const comparisons = []
    for (const bugId of COMPARE_BUGS.map(b => b.id)) {
        const s = spiral.find(r => r.bug_id === bugId)
        const l = linear.find(r => r.bug_id === bugId)
        if (!s || !l) continue

        const gtBug = COMPARE_BUGS.find(b => b.id === bugId)
        comparisons.push({
            bug_id: bugId,
            gt_type: gtBug.t,
            spiral_type: s.classification,
            linear_type: l.classification,
            spiral_root: s.root_cause?.substring(0, 100),
            linear_root: l.root_cause?.substring(0, 100),
            spiral_conf: s.confidence,
            linear_conf: l.confidence,
            spiral_has_hypothesis_chain: !!s.hypothesis_chain,
            hypothesis_count: s.hypothesis_chain?.length || 0,
        })
    }
    return comparisons
}

// ===== MAIN =====
phase('Spiral')
const spiralResults = await parallel(
    COMPARE_BUGS.map(b => () =>
        agent(buildSpiralPrompt(b), {
            label: `spiral:${b.id}`,
            schema: {
                type: 'object',
                properties: {
                    bug_id: {type:'string'},
                    classification: {type:'string'},
                    classification_reason: {type:'string'},
                    evidence: {type:'string'},
                    trace: {type:'string'},
                    root_cause: {type:'string'},
                    root_cause_file_line: {type:'string'},
                    cf_evidence: {type:'string'},
                    fix_description: {type:'string'},
                    confidence: {type:'number'},
                    hypothesis_chain: {type:'array', items: {type:'object', properties: {
                        round: {type:'number'},
                        hypothesis: {type:'string'},
                        falsifiable_test: {type:'string'},
                        verification_result: {type:'string'},
                        confirmed: {type:'boolean'},
                    }}},
                    latent_issues: {type:'string'},
                },
                required: ['bug_id','classification','classification_reason','root_cause','confidence']
            }
        })
    )
)

phase('Linear')
const linearResults = await parallel(
    COMPARE_BUGS.map(b => () =>
        agent(buildLinearPrompt(b), {
            label: `linear:${b.id}`,
            schema: {
                type: 'object',
                properties: {
                    bug_id: {type:'string'},
                    classification: {type:'string'},
                    classification_reason: {type:'string'},
                    evidence: {type:'string'},
                    trace: {type:'string'},
                    root_cause: {type:'string'},
                    root_cause_file_line: {type:'string'},
                    cf_evidence: {type:'string'},
                    fix_description: {type:'string'},
                    confidence: {type:'number'},
                    latent_issues: {type:'string'},
                },
                required: ['bug_id','classification','classification_reason','root_cause','confidence']
            }
        })
    )
)

phase('Compare')
const comparison = compareResults(
    spiralResults.filter(Boolean),
    linearResults.filter(Boolean)
)

log(`A/B Comparison Results:`)
for (const c of comparison) {
    log(`${c.bug_id}: spiral=${c.spiral_type}(conf=${c.spiral_conf}) vs linear=${c.linear_type}(conf=${c.linear_conf}) | GT=${c.gt_type}`)
    if (c.hypothesis_count > 0) {
        log(`  spiral hypothesis chain: ${c.hypothesis_count} rounds`)
    }
}

return { comparison, spiralResults: spiralResults.filter(Boolean), linearResults: linearResults.filter(Boolean) }
