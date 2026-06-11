# 新对话开头 — 直接复制粘贴给 Claude Code

---

**项目概况：** 校园即时通 (Campus Instant Messenger)，泰州学院志愿活动管理App。Flutter + Python FastAPI + Go + PostgreSQL。服务器 `139.196.50.134` (root / @Yf773711)。

**上次会话做了什么（2026-06-10 ~ 06-11）：**

### 代码质量
1. **登录页无限转圈修复** — vsync阻塞导致AnimationController永远不播
2. **Toast从未工作过** — Toast.init()从未被调用，所有提示静默失败
3. **备份全是空文件** — backup_db.sh DB密码写错，0字节备份
4. **is_read类型bug** — 服务端返回整数0/1，Flutter用布尔比较，消息永远显示未读
5. **token_version列缺失** — 顶号功能迁移未执行，全部登录失败
6. **IOClient web不兼容** — Flutter web版用dart:io的IOClient，浏览器崩溃

### 后端增强
7. **顶号功能（token_version）** — 设备B登录，设备A被踢
8. **强制更新（min_version_code=22）** — 低于22强制升级
9. **更新红点引导** — 取消更新后"我的"tab小红点，学微信
10. **ActivityCreate +14字段** — 活动创建不再丢数据
11. **11个缺失后端端点** — close-signup/modify/manual-add/notify-all/info-change/pending-approvals...
12. **消息页7条路径纠错** — approve/reject/appeal/convert路径全修

### 前端增强
13. **Flutter Web版** — flutter build web，一套代码两端运行
14. **活动详情底部固定报名按钮** — 不再滚到最底才看到
15. **登录页3-tab→2-tab** — 学生/老师身份下拉切换
16. **底部导航M3胶囊风格** — 去掉M2顶部边框，改药丸Indicator
17. **消息通知分类分组** — 同类型合并+角标计数
18. **角标直传（onBadgeUpdate）** — 不再走6个API，瞬间更新
19. **首页过滤按钮缩小** — 48→36px + 内边距缩减
20. **个人面板压缩** — 去大emoji，紧凑排版
21. **看板4个图表接通** — 趋势图/柱状图/排名已接线
22. **暗黑模式→日间模式** — ThemeMode.light强制白天模式
23. **颜色全部WCAG AA达标** — textSec/success/danger/warning/info全调暗
24. **Toast TalkBack无障碍** — Semantics liveRegion + 2s时长

### 后端基础设施
25. **GlitchTip→Bugsink** — Docker太重换pip安装，100MB内存
26. **备份密码修复+还原测试通过** — 19用户/5活动验证
27. **systemd Restart=always确认** — 两个服务均已配置
28. **日志轮转配置** — daily rotate 7 compress max 100M
29. **swap 2GB已存在** — 防OOM
30. **Docker已禁用** — 不再自动启动吃内存

### 工具链
31. **pete.py超级修复流水线** — super-fix命令：fix→critic→repair→review→verify
32. **Critic agent注册** — 8项批判维度，改完代码自动找问题
33. **Bug模式库** — memory/bug-patterns.md，7条已记录
34. **三源搜索规范写入CLAUDE.md** — 改前先搜Web+论文+GitHub
35. **复活包** — F:\ClaudeFiles\resurrection-kit\复活指南_README.md

### 鸿蒙版
36. **HAP编译通过** — 129MB unsigned，卡在签名（需DevEco Studio生成profile）
37. shadcn_ui补丁打好（TargetPlatform.ohos支持）

### 学院数据
38. **泰州学院14个学院完整列表** — 已导入DB

### AI模型调研
39. **DeepSeek V4 Pro vs Claude Opus 4.8完整对比** — 编码持平，Agent弱40%，价格差11倍
40. **AI+CAD工程制图完整调研** — 21个工具对比，最终方案：SW2026+Leo AI+agentcad

### ⚠️ 已知限制
- HTTPS证书待配
- Go后端仅覆盖20%端点
- 鸿蒙HAP未签名
- PWA登录偶发401（token_version迁移需验证）

**当前状态：**
- 服务器：healthy，v1.0.7 build 24
- campus_check：11/11 ✅
- flutter analyze：0 errors ✅
- 测试账号：10000/10000（学校超管，college=校级部门）
- 工具：petectl已配置，just可用，复活包已备
- Web版：http://139.196.50.134/（Flutter Web，跟手机同代码）
- APK下载：http://139.196.50.134/static/app-release.apk

**常用命令：**
```bash
python pete.py status      # 全览状态
python pete.py deploy      # 一键部署
python pete.py test        # 三管线快速检查
python test_e2e.py         # 25项API核心流程 (需连服务器)
python campus_check.py     # 11项冒烟检查
just redteam               # 红队武器库快速扫描
just test-e2e              # 同上E2E (快捷方式)
```

**E2E测试覆盖 (2026-06-11上线):**
- Auth: 登录/Token刷新/401/403 (9项)
- Activity: 列表/创建/详情/报名/取消 (7项)
- Notice: 列表/创建/验证 (3项)
- Permission: 版本/健康/权限边界 (6项)
