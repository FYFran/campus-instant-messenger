# B28 — Ground Truth

**Type:** T5（状态机异常 — 订单状态无超时转移）

**根因:** TokenLine 的订单状态机只有两种触发方式转入终态：
1. 支付回调成功 → processing → completed
2. 支付回调失败 → processing → failed

**缺少第三种转移路径**：如果支付回调因为网络问题没到达（webhook 丢失、回调服务器临时不可用、防火墙拦截），订单永远停留在 `processing`，没有任何定时任务或超时机制来转移到 `failed` 或查询支付状态。

**正确修复:**
1. 添加定时任务（cron/daily sweep），查询所有 `processing` 状态超过 30 分钟的订单
2. 主动查询支付网关（微信/支付宝）的订单状态
3. 根据查询结果更新订单状态（completed 或 failed）
4. 如果支付网关也查询不到（极端情况），设置 24 小时超时自动标记为 `timeout` 并通知人工处理

```python
async def sweep_stale_orders():
    stale = await db.fetch(
        "SELECT * FROM orders WHERE status='processing' AND created_at < NOW() - INTERVAL '30 minutes'")
    for order in stale:
        payment_status = await check_payment_gateway(order['payment_ref'])
        if payment_status == 'paid':
            await complete_order(order['id'])
        elif payment_status == 'not_found':
            await fail_order(order['id'], reason='payment_not_found')
```

**文件:** `_research/tokenline/backend/` (order handler)

**评分要点:**
- 分类: T5 — 状态机缺少超时/兜底转移路径 (1pt)
- 证据: 订单永远 processing + 支付回调日志缺失 (1pt)
- 根因: 订单状态机仅依赖回调驱动，无主动轮询或超时机制 (2pt)
- CF: 加定时 sweep → 超过 30 分钟的订单自动查询支付状态 (1pt)
- 修复: 定时任务 + 支付状态主动查询 (1pt)
