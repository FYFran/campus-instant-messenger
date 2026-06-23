# C01 Truth

## 分类
C1 - 竞态条件

## 位置
signup handler: SELECT count检查与INSERT之间无FOR UPDATE

## 根因
并发报名时，两个请求同时读到count=N-1，都通过检查，都INSERT→超max。

## 修复
SELECT ... FOR UPDATE锁定活动行在事务内

## 评分
- [ ] Stage1竞态检查触发？
- [ ] source→sink追踪完整？
- [ ] 修复建议含FOR UPDATE？
