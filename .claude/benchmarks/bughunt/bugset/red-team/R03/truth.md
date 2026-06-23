# R03 Truth

## 分类
R2 - 暴力破解

## 位置
- 攻击面: POST /api/login
- 缺失防御: campus_go/internal/handlers/auth.go:69-78 (速率限制被注释)

## 根因
速率限制代码被注释标注"DISABLED FOR TESTING"但未恢复。
破阵应确认：代码注释掉≠防御不存在。需要实际测试。

## 修复
1. 恢复速率限制代码（去掉注释）
2. 从内存map升级为Redis（跨实例共享）
3. 添加账号锁定机制（5次失败→锁定15分钟）

## 评分要点
- [ ] Phase 1(侦察)是否识别登录端点无速率限制？
- [ ] 是否实际发送多次请求验证（非仅看代码）？
- [ ] 攻击链5阶段是否完整？
- [ ] 是否给出升级到Redis的具体建议？
- [ ] 是否考虑分布式爆破（多IP绕过IP限流）？

## 攻击验证
```bash
# 连续6次登录应全部返回401而非429
for i in $(seq 1 20); do
  curl -s -X POST http://target/api/login \
    -H "Content-Type: application/json" \
    -d "{\"student_id\":\"2024001\",\"password\":\"wrong$i\"}" \
    | jq -r '.detail'
done
# 预期：20次全部返回"学号或密码错误"=无速率限制
# 正常：第6次开始返回"登录过于频繁"
```
