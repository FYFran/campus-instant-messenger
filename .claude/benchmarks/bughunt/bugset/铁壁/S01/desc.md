# S01: 硬编码JWT密钥

## Bug描述
安全审计校园后端代码。发现JWT签名密钥硬编码在源代码中。

## 语言
Go

## 难度
easy

## 注入方法
revert-commit: 回退将JWT_SECRET移到环境变量的commit
