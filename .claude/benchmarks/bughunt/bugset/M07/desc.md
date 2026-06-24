# M07 — T1: Payment Webhook TOCTOU Double Token Grant

## Bug 描述

支付回调偶尔触发两次 token 发放——用户付了一次钱但收到了双倍的 token。不是每次都发生，大概 5-10% 的支付会出现。支付回调日志中有时能看到同一 invoice ID 被处理了两次。
