# D03 — D2: No Abort Conditions Defined Before Deploy

## Bug 描述

campus_go 部署流水线中，Iron Law 要求"NO DEPLOY WITHOUT ABORT CONDITIONS DEFINED FIRST"。检查部署配置，确认中止条件是否被明确定义并自动化执行。

如果 pre-flight 检查失败，部署会自动停止吗？还是依赖人工判断？
