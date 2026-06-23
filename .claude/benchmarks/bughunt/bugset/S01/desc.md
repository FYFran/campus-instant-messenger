# S01 — S1: Weak JWT secret

## Bug 描述

campus_go 的 JWT token 可以被人伪造。攻击者拿到了一个学生的 token，发现可以自己生成任意角色的 token。JWT secret 似乎太弱了，用常见的密码列表就能暴力破解。
