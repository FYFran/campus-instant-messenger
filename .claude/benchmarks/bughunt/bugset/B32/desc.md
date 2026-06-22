# B32 — T6: Python 3.9 asyncio.wait 行为差异

## Bug 描述

campus_app Python 后端的并发通知发送在 Python 3.9 环境下不工作。代码在开发机（Python 3.12）上测试正常，但部署到服务器（Python 3.9）后，批量发通知时而只发了第一条，其余丢失。没有报错。
