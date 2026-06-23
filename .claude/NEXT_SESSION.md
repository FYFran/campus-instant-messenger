# 下一会话

## 系统状态 (2026-06-23)

### 11 Skill — 0 issues, 0 warnings
| Skill | Baseline | pass@k | CNA |
|------|---------|--------|-----|
| 铁壁 v2.1 | 8.0 | pass@3 | 0.009/k |
| 明镜 v2.1 | 8.0 | pass@2 | 0.012/k |
| 破阵 v2.1 | 8.0 L1 | pass@1 | 0.296/k |
| 缉凶 v3.1 | 6.1 | pass@3(v2.5) | 0.020/k |
| 布阵 v3.0 | 8.0 L1 | — | — |
| 门神 v2.1 | 8.0 L1 | — | — |
| 火眼 v1.1 | 8.0 L1 | — | — |
| 试金石 v1.0 | 8.0 L1 | — | — |
| 天眼 v1.0 | — | — | — |
| 架构师 v1.0 | — | — | — |
| 轮回 v1.1 | — | — | — |

### 飞轮 (每次commit自动)
- compat_check → health → drift(L0+L1) → drift.log → GEPA proposal
- L0: file/frontmatter/size/sections
- L1: gotcha ratchet/constitution/red lines
- L2: 待数据积累后启用

### campus_go 线上 (47.82.103.247)
- nginx /campus/ → :9501
- PostgreSQL Docker (glitchtip-postgres-1)
- S01/S03/S05 fixed + upload JWT + register rate limit
- iptables persisted, first DB backup done
- Python: race condition fixed, bare except fixed, hardcoded code fixed
- 天眼 health monitor cron 60s

### 待修
- Python 代码 git 追踪 (submodule残留)
- L2 agent采样门禁 (数据不够)
- 缉凶 v3.1 re-benchmark
- 破阵 pass@2
- DAG 链执行
- Flutter app 连接测试

### 启动
1. `python -m mempalace mine` → wake-up → search
2. `python .claude/scripts/skill_health.py` 看状态
3. 继续飞轮 L2 或修剩余漏洞
