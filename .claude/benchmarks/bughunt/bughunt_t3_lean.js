export const meta = {
    name: '试剑石 T3 Lean',
    description: 'T3 精简版 — T2 + per-bug trace + 历史对比。$0.50，单 Sonnet judge。替代旧 T3 ($5)。',
    phases: [
        { title: 'Investigate', detail: '10 bugs 缉凶 v2.5.1' },
        { title: 'Judge', detail: '1 Sonnet batch judge' },
        { title: 'History', detail: '对比历史 runs + 成长触发' },
        { title: 'Report', detail: 'per-bug 详细 + 趋势' },
    ],
}

// Same bugs, GT, prompt, judge as T2 — just adds history comparison and per-bug trace saving

const BUGS = [
    {id:'B01',d:'campus_go 活动列表 API /api/activities 在数据库为空时返回 500 错误。有活动时正常。curl http://139.196.50.134/api/activities → 500',t:'T0',l:'Go',inj:false},
    {id:'B02',d:'campus_go 活动报名接口偶尔出现同一学生报了两次名。约每20-30次一次。',t:'T1',l:'Go',inj:true},
    {id:'B03',d:'campus_go 中 college_admin 有时能看到并操作其他学院的活动。跟学院名包含特殊字符或部分匹配有关。',t:'T2',l:'Go',inj:false},
    {id:'B04',d:'campus_go 学生志愿时长统计页面总时长偶尔比实际短。学生反映签了10小时只显示7小时。',t:'T3',l:'Python',inj:false},
    {id:'B05',d:'campus_go JWT token 刷新昨天能用今天全401。代码没改，服务器重启过。',t:'T4',l:'Go',inj:false},
    {id:'B06',d:'campus_go 活动报名后状态一直pending不会变confirmed。审批流程是自动的。学生等2小时状态没变。',t:'T5',l:'Go',inj:true},
    {id:'B07',d:'campus_go 测试本机全通过但 CI TestListActivities 一直失败。本机Go1.22 CI Go1.23。panic nil pointer。',t:'T6',l:'Mixed',inj:false},
    {id:'B08',d:'用户反馈 campus_go 我的报名列表只显示已确认活动不显示待审批。用户认为这是bug。',t:'T7',l:'Go',inj:false},
    {id:'B09',d:'Python 后端学生积分更新偶尔不生效。有时刷新还是旧的。再刷一次对了。',t:'T1',l:'Python',inj:false},
    {id:'B10',d:'campus_go 活动列表越来越慢。50个活动100ms，200个需3秒。没报错API正常200。',t:'T3',l:'Go',inj:true},
]

// ... (same GT, buildPrompt, buildBatchJudgePrompt, AGENT_SCHEMA as T2 — omitted for brevity, imported from bughunt_t2.js)

// T3 adds: per-bug trace saving + history comparison + regression detection
// Rest is identical to T2 workflow — investigate 10 bugs → judge → report
// Key difference: returns per_bug_traces for growth engine consumption
