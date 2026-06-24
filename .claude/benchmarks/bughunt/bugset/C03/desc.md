# C03 — C2: SQL String Concatenation Risk

## Bug 描述

campus_go 代码库使用参数化查询，但审查是否存在字符串拼接构造 SQL 的情况。检查所有 handler 文件，找出任何使用 `+` 或 `fmt.Sprintf` 拼接 SQL 而非使用 `$1, $2` 占位符的地方。

关注点：通知插入代码中的字符串拼接。
