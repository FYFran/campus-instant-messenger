# C03 Truth

## 分类
C2 - 数据暴露

## 根因
SELECT *在用户查询中返回password_hash。即使API层面过滤，DB层已泄露。

## 修复
显式列名SELECT排除password_hash, refresh_token_hash

## 评分
- [ ] Stage2数据暴露检查触发？
- [ ] 是否检测到SELECT *？
- [ ] 修复是否使用显式列名？
