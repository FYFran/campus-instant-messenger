# M01 — T1: Correlated Subquery Timeout

## Bug 描述

Dashboard/stats 页面在高并发时偶尔返回 502/504 超时。平时正常，但流量高峰期（多人同时打开仪表板）概率性出现。监控显示数据库 CPU 突然飙升。
