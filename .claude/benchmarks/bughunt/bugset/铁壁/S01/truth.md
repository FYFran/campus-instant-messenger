# S01 Truth

## 分类
S0 - 硬编码密钥

## 位置
campus_go/internal/config/config.go (JWT_SECRET硬编码)

## 根因
JWT签名密钥以明文硬编码在源码中。任何人能看到源码就能伪造JWT token。

## 修复
将JWT_SECRET移到环境变量，config.go通过os.Getenv("JWT_SECRET")读取。

## 评分要点
- [ ] 密钥扫描步骤是否检出此问题？(STEP1)
- [ ] 是否给出file:line证据？
- [ ] 修复建议是否具体(环境变量名+读取方式)？
- [ ] 是否标记为CRITICAL？

## 验证
```bash
rg -n "JWT_SECRET" campus_go/  # 应在源码中找得到硬编码
```
