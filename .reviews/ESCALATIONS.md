# ESCALATIONS — Cross-Audit Recurring Vulnerability Tracker

> If same vulnerability appears in 2+ consecutive audits → auto-escalate severity one level (LOW→MEDIUM→HIGH→CRITICAL).

| Date | Audit | Finding | Original Severity | Escalated | Count | Status |
|------|-------|---------|-------------------|-----------|-------|--------|
| — | — | — | — | — | 0 | — |

## Escalation Rules

- Same file:line + same vulnerability type in 2 consecutive audits → +1 severity
- 3 consecutive → flag as systemic, escalate to architect
- 4+ consecutive → BLOCK deployment until resolved

## Unresolved Criticals

(None recorded yet)
