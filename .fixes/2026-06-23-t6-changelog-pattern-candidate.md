# Pattern Candidate: T6 → Code-First Not Environment-First

**Date:** 2026-06-23
**Bug:** B07 (Go 1.22 vs 1.23 NULL Scan)
**Submitted by:** 缉凶 v2.8.1 contract step 8

Pattern: Agent classifies T6 correctly but then finds code-level fix (nil guard/param validation) instead of environment root cause (Go version NULL Scan).

Signal: Bug description has version/OS/env difference keywords. Agent traces code, finds plausible code bug, stops — never investigates environment diff.

Suggested F-rule: F9 — "T6 bug→agent找代码修复不查环境差异" | 症状含版本/OS/环境差异但agent追到第一个代码级bug就停 | T6强制环境检查走完, H1必须是环境/版本差异
"T6 bug → agent 找代码修复不查环境差异" |
症状含版本/OS/环境差异，但 agent 追到第一个代码级 bug 就停 |
T6 强制环境检查(见下)必须走完，分析步 H1 必须是环境/版本差异 |
环境版本差异

## Evidence
5 consecutive B07 runs (v2.6→v2.8.1): root_cause=0 every time.
Agent always finds nil guard, never Go 1.23 NULL Scan.

## Status
✅ Applied as F9 in v2.8
