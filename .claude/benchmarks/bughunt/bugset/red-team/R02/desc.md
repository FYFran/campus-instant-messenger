# R02: 破阵 — JWT弱密钥伪造攻击

## Bug描述
铁壁S01发现JWT密钥回退到硬编码"campus-secret-key-2024"。以攻击者视角：获取这个密钥→伪造任意用户JWT→访问受保护端点→提权到school_admin。

## 难度
medium

## 语言
Go

## 攻击链
1. 信息收集：发现JWT_SECRET环境变量未设时回退弱密钥
2. 武器化：用弱密钥伪造JWT {user_id:1, role:"school_admin", ver:999}
3. 投送：带伪造JWT访问 GET /api/me
4. 利用：以school_admin身份访问所有管理接口
5. 横向移动：修改活动、查看所有用户数据

## 注
此bug依赖S01(JWT弱密钥)存在。破阵需要串联两个LOW漏洞达成HIGH影响。
