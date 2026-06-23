# S05: 端点审计 — POST端点缺少速率限制

## Bug描述
登录端点没有速率限制，可被暴力破解。

## 语言
Mixed

## 难度
medium

## 注入方法
edit-file: 移除登录端点的limiter装饰器
