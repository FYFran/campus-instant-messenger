# Q03 — Q2: Threshold Bypass via Metric Manipulation

## Bug 描述

campus_go 的 CI gate 中代码覆盖率阈值可在配置文件中修改，且没有版本控制和审批流程。检查 `.codecov.yml` 或相关 CI 配置，确认阈值是否能被任意修改而不触发告警。

目标：证明阈值可以被静默降低，从而让未达标的代码通过门禁。
