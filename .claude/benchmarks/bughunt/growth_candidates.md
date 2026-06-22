# Growth Candidates — 自动生成, 待 GEPA 验证

> 从 3-run per-bug 数据 + judge reasoning 提取
> 每个候选 → Lean T2 3-run 验证 → MERGE/DISCARD

---

## Candidate F7: T4 Token/401 Bypass Check

**触发 bug:** B05 (3-run mean 5.3/8, root_cause 持续 0)

**失败模式:** Agent 看到 "token 刷新全 401 + 重启" → 直接进入 JWT_SECRET 代码分析 → 忽略 nginx 配置。
F6 说 "T4 专属配置检查通过前不许读源码" 但 agent 仍然去了 auth.go:15 查 JWT_SECRET。

**根因:** desc "昨天能用今天全401。代码没改，服务器重启过" → 同时匹配 "JWT 密钥丢失" 和 "nginx 端口回退"。
Agent 无法区分。需要物理测试而非代码分析。

**候选 F-rule:**
```
F7: "T4 + token/401/认证症状 → 第一步不是读代码。第一步是 curl 测试。
     curl 直连后端端口(绕过nginx) → 后端正常? → nginx问题。
     后端也401? → 代码/JWT问题。不经过此测试不许读 auth.go。"
```

**预期效果:** B05 root_cause 从 0→2 (agent 会用 curl 区分 nginx vs 代码)

**验证成本:** Lean T2 B05 only ×3 = $0.15

---

## Candidate F8: Assert-Missing Must Prove Absent

**触发 bug:** B03 (3-run mean 6.3/8, root_cause 持续 0-1)

**失败模式:** Agent 看到 "跨学院可见" → 判为 "SQL 缺少 college 过滤" → 但实际上 college 过滤存在,
只是用了 strings.Contains (部分匹配) 而非精确匹配。

**根因:** Agent 断言 "某机制不存在" → 没先 search 确认是否已存在另一种实现。

**候选 F-rule:**
```
F8: "断言'缺少X'前必须先 search X 的关键词。
     找到 X 存在但实现不同(如 Contains vs ==) → 不是 '缺失', 是 '实现不精确' → T2 不是 T0。
     找不到 X → 才能断言缺失。"
```

**预期效果:** B03 agent 会 search "college" → 找到 strings.Contains → 修正根因

**验证成本:** Lean T2 B03 only ×3 = $0.15

---

## Saturated Bugs (可退役)

| Bug | Runs at 8/8 | Type |
|-----|-----------|------|
| B01 | 3/3 | T0 nil deref |
| B02 | 3/3 | T1 race condition |
| B06 | 3/3 | T5 state machine |
| B08 | 3/3 | T7 NOT_A_BUG |
| B09 | 3/3 | T1 missing await |

**退役规则:** 连续 3 次 8/8 → 退役 → GEPA 生成同 type 更难变体
**变体生成:** GEPA reads original bug + truth → generates new desc with:
  - +1 indirection layer
  - +1 misleading signal
  - same root cause type, harder to spot

---

## 首次成长循环计划

```
1. 选 F7 (更便宜, B05 单一 bug 验证)
2. 创建 skill 副本 → 加 F7
3. Lean T2 B05 only ×3 ($0.15)
4. mean ≥ 6/8? → MERGE F7 到 production skill
   mean < 6/8? → DISCARD F7, 试 F8
5. growth.log 记录
```
