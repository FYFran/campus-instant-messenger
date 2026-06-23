# Phase 1.5 Bug Injection Log — 2026-06-23

## Summary

| Skill | Bugs Ready | Go Injected | Python Natural | Total |
|-------|-----------|-------------|----------------|-------|
| 铁壁 | S01,S02,S03,S05 | S01,S03,S05 | S02 | 4 |
| code-review | C01,C02,C03 | C01 | C02,C03 | 3 |

## 铁壁 (Security Audit) Bugs

| ID | Category | Language | Location | Status |
|----|----------|----------|----------|--------|
| S01 | S0-Hardcoded Key | Go | middleware/auth.go:22 | Injected: JWT falls back to "campus-secret-key-2024" |
| S02 | S1-SQL Injection | Python | db.py, main_remote.py (29 occurrences) | Natural: f-string SQL |
| S03 | S2-Missing Auth | Go | main.go:47 | Injected: ModifyActivity outside JWT group |
| S05 | S4-Missing RateLimit | Go | handlers/auth.go:69 | Natural: DISABLED FOR TESTING |

## code-review Bugs

| ID | Category | Language | Location | Status |
|----|----------|----------|----------|--------|
| C01 | C1-Race Condition | Go | handlers/activities.go:152 | Injected: FOR UPDATE removed |
| C02 | C3-Error Swallowing | Python | proxy_server.py:1 occurrence | Natural: bare except |
| C03 | C2-Data Exposure | Python | db.py, main_remote.py (39 occurrences) | Natural: SELECT * |

## Pending

- S04 (Dependency CVE): No requirements.txt in Python backend
- C04 (Missing Validation): All Pydantic Fields have max_length

## Injection Patches

- `bug_injection/S01_inject.patch` — JWT fallback
- `bug_injection/S03_inject.patch` — Missing auth endpoint
- `bug_injection/C01_inject.patch` — Missing FOR UPDATE

## Campus Go State

Branch: skill-lab/20260621-bughunt
Stashed: "Phase 0.5 campus_go fixes — pre Phase 1.5 baseline"
