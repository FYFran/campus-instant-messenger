# TokenLine 完整代码审计 — 新对话启动文档

## 背景

TokenLine = AI写作工具，印尼市场。前端HTML+JS，后端Go，DeepSeek V4 API。服务器47.82.103.247。

网站 https://tokenline.top/ 聊天页 /chat/ 经历5层bug，用户连续报错"AI tidak menghasilkan respons"。每层修完下一层才暴露。需要完整审计，一次性找出所有残留问题。

## 服务器访问
```
ssh root@47.82.103.247
```
- 后端: systemctl tokenline, 端口9100, 二进制 /app/rewriter-go/rewriter → /app/rewriter-go/rewriter-linux
- 前端: /app/static/chat/index.html
- Nginx: /etc/nginx/sites-enabled/tokenline
- 数据库: /app/new-api/data/tokenline.db
- 测试账号: testlive@tokenline.top / Test123456! (uid 224, flash平衡100000)

## 已知5层Bug（全部已修，需验证修复完整性）

### Bug 1: currentLang ReferenceError
- chat_index_server.html:998 — `lang: currentLang` 变量不存在
- 修复: `getUserLang()` 函数

### Bug 2: reasoning_content 未累积
- chat_index_server.html:1037 — `full` 只累积 `delta.content`
- 修复: `full += delta.reasoning_content`

### Bug 3: thinking:disabled 隐形token消耗
- client.go:68 — 强制 `thinking: {type: "disabled"}`，长对话时内部推理消耗token但不输出
- 修复: Thinking=nil，json omitempty

### Bug 4: Service Worker 缓存
- /app/static/chat/sw.js — v1 cache-first，部署的新JS对回头用户不可见
- 修复: v3 network-first，install清旧缓存

### Bug 5: reasoning 渲染不透明
- chat_index_server.html:1038 — reasoning 渲染为 opacity:0.45
- 修复: SSE结束后强制全不透明重新渲染

## 审计清单

### 后端Go代码 (f:/ClaudeFiles/_research/rewriter-go/)

**internal/deepseek/client.go** — DeepSeek客户端
- ChatStream: 检查 thinking参数、SSE流处理、circuit breaker、max_tokens逻辑
- 关注: 长对话时是否有其他token消耗路径、错误是否被正确传播

**internal/handler/chat.go** — 聊天Handler
- Chat函数: 认证、内容过滤、余额检查、扣费/退款、历史加载、system prompt、流式写入
- getBalance函数: SQL查询、免费额度逻辑
- refundReserved函数: 退款是否正确区分flash/pro
- 检查: TOCTOU竞态（扣费和实际调用之间）、401/403/500错误处理

**internal/config/config.go** — 配置
- requireEnv vs envOr: DEEPSEEK_API_KEY是否正确加载
- 是否有遗漏的必要配置

**internal/handler/auth.go** — 认证
- Login: JWT生成、cookie设置(HttpOnly/Secure/SameSite/Path/MaxAge)
- Register: 手机号验证逻辑
- Logout: cookie清除
- 检查: token_version递增逻辑、7天过期是否正确

**internal/middleware/auth.go** — 认证中间件
- cookie优先→Authorization header回退
- JWT验证、token_version检查
- 错误信息是否泄露过多信息

**main.go** — 路由和中间件
- 路由注册完整性
- 中间件链顺序
- CORS设置

### 前端JS (f:/ClaudeFiles/_research/rewriter-go/chat_index_server.html)

**send() 函数** (~line 944-1085)
- isStreaming状态管理: 是否有竞态条件
- finalMessage构建: 文件上传、mode prefix、citation注入是否正确
- fetch请求: URL、headers、credentials、body
- 错误处理: 401/403/非OK的处理是否完整
- SSE解析: data:行解析、JSON容错、delta.content/content vs reasoning_content处理
- botWrap创建: DOM结构、CSS class
- 全文累积: full变量包含所有内容类型
- 最终渲染: mdToHtml调用、不透明度
- token用量显示: 如何在bubbleBody中追加
- fallback: 空内容判断条件
- saveConvs: 是否存储完整内容
- refreshBalance: 是否触发额外请求
- catch块: 错误消息是否准确

**其他函数**
- getUserLang: localStorage读取+fallback
- mdToHtml: 渲染安全性
- escHtml: XSS防护是否完整
- handleFileUpload: upload到/api/upload
- loadUserData: /api/me调用
- logout: cookie清除
- conversations管理: 本地vs服务器同步
- appendMsg: 消息追加逻辑

### 服务器配置

**Nginx** /etc/nginx/sites-enabled/tokenline
- SSL证书路径
- /api/ → 后端代理（timeout、buffering）
- 静态文件服务
- 是否还有旧config残留

**Systemd** /etc/systemd/system/tokenline.service
- 环境变量完整性(DEEPSEEK_API_KEY, JWT_SECRET, ADMIN_PASSWORD等)
- Restart策略
- 工作目录

**Service Worker** /app/static/chat/sw.js
- 版本号
- 缓存策略
- install/activate逻辑

### 关键验证

每个修复点必须用curl从服务器直接测试:
```bash
# 1. 登录
curl -s -c /tmp/c -X POST https://tokenline.top/api/auth/login --resolve "tokenline.top:443:127.0.0.1" -H "Content-Type: application/json" -d '{"email":"testlive@tokenline.top","password":"Test123456!"}'

# 2. 聊天（中文短消息）
curl -s --max-time 30 -b /tmp/c -X POST https://tokenline.top/api/chat --resolve "tokenline.top:443:127.0.0.1" -H "Content-Type: application/json" -d '{"message":"你好","model":"deepseek-v4-flash","lang":"zh"}'

# 3. 检查输出：必须有 content 字段（不只是 reasoning_content），token 用量合理
```

## CI 管道
f:/ClaudeFiles/_research/rewriter-go/ci-pipeline.sh — 运行: `cd f:/ClaudeFiles/_research/rewriter-go && RUNS=2 FAST=1 bash ci-pipeline.sh`

## 项目根
f:/ClaudeFiles/ — git仓库，分支master
