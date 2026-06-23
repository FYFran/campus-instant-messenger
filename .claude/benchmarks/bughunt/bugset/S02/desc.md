# S02 — S0: Stored XSS in activity description

## Bug 描述

campus_go 的活动创建接口接受 HTML/script 标签并原样存入数据库。当其他用户查看活动详情时，如果描述中包含 `<script>alert(1)</script>`，脚本会在浏览器中执行。
