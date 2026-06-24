# Growth Candidates — 自动生成, 待 GEPA 验证

> 从 3-run per-bug 数据 + judge reasoning 提取
> 每个候选 → Lean T2 3-run 验证 → MERGE/DISCARD

---

## Candidate F7: T4 Token/401 Bypass Check ✅ MERGED

**触发 bug:** B05 (3-run mean 5.3/8, root_cause 持续 0)

**结果:** 3-run mean 7.7/8, root_cause 2.0/2 → MERGED to production skill v2.5.1

---

## Candidate F8: Assert-Missing Must Prove Absent ❌ DISCARD

**触发 bug:** B03 (3-run mean 6.3/8, root_cause 持续 0-1)

**结果:** 3-run mean 4.0/8, root_cause 0.0/2 → DISCARD

**根因分析:** 不是 F8 规则有问题 — 是 B03 基准构造效度问题。GT 描述 `strings.Contains` 部分匹配 (T2)，但实际注入代码中 ListActivities SQL 完全没有 college 过滤 (T0)。代码中无任何 `strings.Contains` 学院匹配。所有 3 个 agent 正确识别了真实 bug (T0: missing filter)，但 judge 因 GT 不一致扣分。

**修复:** B03 desc.md + truth.md 已更新为匹配实际注入 (T0: missing college filter)。

---

## Saturated Bugs (已退役)

| Bug | Runs at 8/8 | Type | Variant |
|-----|-----------|------|---------|
| B01 | 3/3 | T0 nil deref | → B01v2: cache indirection + misleading stack |
| B02 | 3/3 | T1 race condition | → B02v2: cross-endpoint + misleading UNIQUE |
| B06 | 3/3 | T5 state machine | → pending |
| B08 | 3/3 | T7 NOT_A_BUG | → pending |
| B09 | 3/3 | T1 missing await | → pending |

---

## 经验教训

1. **构造效度 > skill 优化。** F8 失败不是规则不好 — 是基准描述不匹配注入代码。修基准比修 skill 更优先。
2. **GT 必须验证。** 写 GT 时必须确认注入代码实际存在 GT 描述的症状。B03 的 `strings.Contains` 从未在代码中存在。
3. **当 agent 连续 3 次找到"不同但真实的" bug 时 → 基准有问题，不是 agent 有问题。**
