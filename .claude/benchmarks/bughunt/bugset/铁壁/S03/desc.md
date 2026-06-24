# S03: 缺失认证的写端点

## Bug描述
一个POST端点没有认证检查——任何人无需登录就能调用。

## 语言
Go

## 难度
medium

## 注入方法
edit-file: 移除某个写端点的Depends(get_current_user)
