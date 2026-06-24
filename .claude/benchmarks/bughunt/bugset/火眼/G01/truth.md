# G01 Truth

## 分类
G0 - 缺失ADR

## 位置
docs/adr/ (空目录或不存在)

## 根因
项目无ADR文化。重大决策（框架选型、数据库选型、认证方案）没有记录上下文、备选方案、决策理由。

## 修复
创建docs/adr/目录，每个重大决策写一份ADR：
- 001-choose-gin-framework.md
- 002-choose-postgresql.md
- 003-jwt-auth-strategy.md

## 评分要点
- [ ] PreScan是否检测到docs/adr/缺失？
- [ ] 是否标记为P1(架构债)？
- [ ] 修复建议是否包含具体ADR模板？
