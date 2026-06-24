# S04: 过期依赖CVE

## Bug描述
requirements.txt中某依赖版本存在已知CVE漏洞。pip-audit应检出。

## 语言
Python

## 难度
easy

## 注入方法
edit-file: 降级某依赖到有已知CVE的版本
