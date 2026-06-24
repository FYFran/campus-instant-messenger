# S05 Truth

## 分类
S4 - 缺失速率限制

## 位置
登录端点

## 根因
登录端点无速率限制。攻击者可暴力破解密码。

## 修复
添加limiter: 5次/分钟(登录)

## 评分要点
- [ ] 端点审计是否检查了速率限制？(STEP3)
- [ ] 是否识别出这是Auth类端点的安全要求？
- [ ] 修复建议是否包含具体限制值(5/min)？

## 验证
```bash
# 连续6次登录应触发429
for i in 1 2 3 4 5 6; do curl -X POST /api/login -d '{"student_id":"test","password":"wrong"}'; done
```
