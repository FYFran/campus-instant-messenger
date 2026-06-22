# B28 — T5: TokenLine 订单状态卡在 processing

## Bug 描述

TokenLine 平台的充值订单偶尔一直显示"处理中 (processing)"，不会自动变为"已完成 (completed)"或"失败 (failed)"。用户已经完成了支付（微信/支付宝回调已收到），但订单状态没更新。用户的钱付了，token 没到账。
