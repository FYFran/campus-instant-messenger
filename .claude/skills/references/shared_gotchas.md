# Shared Gotchas — 跨Skill知识传播总线

> 每个skill发现的新模式→写入此文件。其他skill运行时→读取此文件→自动更新审查清单。
> GEPA飞轮的L2层：跨skill知识传播。

## 传播规则

| 源skill | 发现类型 | → 目标skill |
|---------|---------|------------|
| 铁壁 | 新漏洞模式(CWE) | 明镜(审查清单) 破阵(攻击面) 缉凶(debug模式) |
| 明镜 | 新反模式 | 铁壁(扫描规则) 门神(门禁检查) |
| 破阵 | 新攻击链 | 铁壁(防御加固) 明镜(审查清单) |
| 缉凶 | 新bug根因 | 明镜(审查清单) 门神(门禁检查) |
| 布阵 | 部署失败模式 | 门神(部署前检查) 天眼(监控指标) |
| 门神 | 漏放模式 | 明镜(审查清单) 铁壁(扫描规则) |

## 当前活跃知识（Phase 1.5 + Phase 2 积累）

### 来自 铁壁 baseline (2026-06-23)

**模式 #S01: JWT密钥回退到硬编码**
- 发现: 铁壁 C-1
- 描述: 环境变量未设时回退到弱密钥，允许JWT伪造
- → 明镜: 审查时检查所有密钥/secret是否有硬编码回退
- → 破阵: 攻击面——检查所有JWT签发点是否有弱密钥
- → 门神: 门禁检查——JWT_SECRET环境变量是否已设

**模式 #S02: f-string SQL拼接(列名+值)**
- 发现: 铁壁 H-4
- 描述: 动态列名通过f-string拼接到SQL，虽经白名单但脆弱
- → 明镜: 审查时GREP所有f-string+SQL组合，不只WHERE也在SET子句
- → 缉凶: 新增debug模式——数据异常时检查动态SQL

**模式 #S03: 端点分组外注册=无认证**
- 发现: 铁壁 H-1
- 描述: 路由在JWT中间件组外注册，任何人可访问
- → 明镜: 审查时逐端检查是否在protected group内
- → 破阵: 攻击面——枚举所有非认证POST端点

**模式 #S05: 速率限制被注释=不存在**
- 发现: 铁壁 H-3
- 描述: 代码被注释"DISABLED FOR TESTING"，防御实际不存在
- → 明镜: 审查时不仅看代码存在，还要验证未被注释/未绕过
- → 破阵: 攻击面——测试所有限流端点是否实际生效

### 来自 明镜 baseline (2026-06-23)

**模式 #C01: TOCTOU竞态——事务内读无FOR UPDATE**
- 发现: 明镜 C01
- 描述: 事务内SELECT读count未加FOR UPDATE，并发超额报名
- → 铁壁: 扫描规则——GREP事务内SELECT是否缺FOR UPDATE
- → 缉凶: debug模式——超额报名→优先检查FOR UPDATE

**模式 #C02: bare except吞噬所有异常**
- 发现: 明镜 C02 (Python proxy_server.py)
- 描述: except: pass吞噬KeyboardInterrupt/SystemExit，静默失败
- → 铁壁: 扫描规则——GREP "except:" 检查是否裸except
- → 缉凶: debug模式——静默失败→检查异常处理

**模式 #C03: SELECT * 泄露内部字段**
- 发现: 明镜 C03 (39 occurrences)
- 描述: SELECT * 可能返回password_hash等内部字段
- → 铁壁: 扫描规则——GREP "SELECT *" 标记数据暴露风险
- → 明镜: 审查时逐SQL检查是否显式列名

### 来自 布阵部署实战 (2026-06-23)

**模式 #D01: Docker容器端口→iptables DNAT**
- 发现: 布阵 campus_go 部署
- 描述: PG容器(glitchtip-postgres-1)端口5432仅Docker内部可达。需iptables DNAT转发+持久化
- → 布阵: gotcha#9 部署前检查端口映射
- → 门神: 部署前检查——所有依赖服务端口可达性

**模式 #D02: nginx conf.d在http层→location必须server内**
- 发现: 布阵 nginx配置
- 描述: /etc/nginx/conf.d/*.conf在http块include，裸location指令非法
- → 布阵: gotcha#10 直改sites-enabled

**模式 #D03: 云安全组→非标端口不可达**
- 发现: 布阵 campus_go部署
- 描述: 阿里云安全组仅放80/443，9501外部不可达
- → 布阵: gotcha#11 新服务走nginx反向代理
- → 破阵: 攻击面枚举时考虑nginx代理层

**模式 #D04: bcrypt哈希→shell参数毁坏**
- 发现: 布阵 seed数据
- 描述: bcrypt哈希含$符号，经ssh/bash→psql时被展开毁坏
- → 布阵: gotcha#12 scp sql文件→docker exec < file

### 来自 部署验证 (2026-06-23)

**模式 #S05确认: 速率限制禁用=真实漏洞**
- 确认: 铁壁+破阵双重验证 live server
- 描述: campus_go auth.go:69-78 速率限制注释未恢复。nginx /campus/ location无限流。双重防御失效。
- → 破阵: 攻击面——登录端点可暴力破解
- → 门神: 部署前检查——不仅检查代码存在，curl验证实际生效
- → 门神: gotcha#6#7 防御有效性验证

**模式 #AV6: 新路径绕过已有防御**
- 发现: 破阵R03 live攻击
- 描述: 部署新增/campus/前缀→nginx location无限流→绕过已有/api/login的limit_req
- → 布阵: gotcha#11 新路径独立验证所有防御
- → 门神: 部署前逐location验证速率限制

## 过期策略
- 模式被修复后30天→降级为历史记录
- 连续3次skill运行未触发→标记为已修复
- 每年清理一次历史模式
