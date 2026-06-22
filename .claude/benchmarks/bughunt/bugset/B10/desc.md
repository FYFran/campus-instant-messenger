# B10 — T3: N+1 query silent degradation

## Bug 描述

campus_go 的活动列表页面加载越来越慢。活动只有 50 个时加载只需 100ms，现在活动 200 个时需要 3 秒。没有报错，API 正常返回 200——就是越来越慢。用户抱怨"刷个列表要等半天"。
