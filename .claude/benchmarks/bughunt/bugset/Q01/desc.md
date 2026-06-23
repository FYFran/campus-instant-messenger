# Q01 — Q0: False-Positive Test (Always-Green Check)

## Bug 描述

campus_go 的 CI 管线中有一个质量检查总是 PASS，即使代码有严重问题也拦不住。检查 `.claude/` 目录下的质量门禁配置，找出哪个检查是"恒真"的——即无论输入如何都返回 PASS。

目标：找到这个 always-green 的检查，证明它拦不住已知的坏代码。
