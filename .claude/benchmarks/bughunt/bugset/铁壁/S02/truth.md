# S02 Truth

## 分类
S1 - SQL注入

## 位置
campus_app/server/main_remote.py 搜索端点

## 根因
用户输入通过f-string拼接到SQL查询。攻击者可通过search参数注入任意SQL。

## 修复
使用参数化查询($1, $2)替代f-string拼接。

## 评分要点
- [ ] SAST/手动GREP是否检出？(STEP2)
- [ ] 是否给出完整的source→sink追踪？
- [ ] 修复是否使用参数化查询？

## 验证
```bash
# 应能通过注入获取额外数据
curl "http://target/api/users/search?q=' OR '1'='1"
```
