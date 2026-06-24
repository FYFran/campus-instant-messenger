# B27 — Ground Truth

**Type:** T3（无报错 — 事务顺序错误导致数据不一致）

**根因:** TokenLine 后端处理 API 调用的典型流程：
1. 检查用户余额 → 2. 扣减 token → 3. 调用上游 AI API → 4. 返回结果

问题在于第 2 步（扣减）在第 3 步（API 调用）之前执行。如果第 3 步的 AI API 调用失败（超时、500、rate limit），第 2 步的扣减已经提交且**未回滚**。用户余额减少了，但没有得到任何结果。

正确的顺序应该是：先调用 AI API，成功后再扣减。或使用数据库事务：扣减 + API 调用 + 记录结果在同一事务中，任何一步失败则回滚。

实际上，TokenLine 使用的是第三方 AI API（DeepSeek/OpenAI），无法放在数据库事务中。所以更实际的方案是：
- **先预留后确认**：先标记余额为 reserved，API 成功后 confirm（转为已消费），API 失败后 release（释放余额）。
- 或：**先调用后扣减**：API 调用成功后从余额扣除，失败则只记录错误不扣费。

**正确修复:**
```python
# 方案1: 先调用后扣减
result = await call_ai_api(prompt)
if result.success:
    deduct_credits(user_id, tokens_used)
    return result
else:
    log_error(user_id, "API call failed")
    return error_response
```

**文件:** `_research/tokenline/backend/` (API proxy handler)

**评分要点:**
- 分类: T3 — 无报错，余额减少但无结果，静默数据不一致 (1pt)
- 证据: 用户余额日志 + API 调用日志时间线对比 (1pt)
- 根因: 扣费在 API 调用之前，API 失败后未退款 (2pt)
- CF: 改为先调用后扣减 → API 失败时不扣余额 (1pt)
- 修复: 调整事务顺序或实现预留/确认机制 (1pt)
