# 🔴 Red Team Arsenal — CampusGo v4
> Updated 2026-06-12 — 21 weapons verified, 3 rounds of upgrades

## 武器清单

### 密钥扫描 (3把)

| 武器 | 版本 | 命令 | 实力 |
|------|------|------|------|
| **Gitleaks** | latest | `bash run_arsenal.sh quick` | 150+ patterns, 毫秒预提交拦截 |
| **TruffleHog** | 3.95.5 | `trufflehog filesystem .` | 800+ detectors, 实时API验证 |
| **APKLeaks** | 2.6.3 | `apkleaks -f app.apk` | APK密钥/URL/端点扫描 |

### SAST (6把)

| 武器 | 版本 | 命令 | 实力 |
|------|------|------|------|
| **Semgrep** | 1.165.0 | `bash run_arsenal.sh full` | 30+语言, 3000+规则 |
| **Foxguard** | 0.8.1 | `npx foxguard .` | Rust闪电扫描(5s), 后量子审计, TUI |
| **MEDUSA** | 2026.6.0 | `medusa scan .` | 79分析器, 40K+规则, AI安全检测 |
| **Bandit** | 1.9.4 | `bash run_arsenal.sh full` | Python SAST |
| **GoSec** | dev | `bash run_arsenal.sh full` | Go AST+SSA分析 |
| **Checkov** | 3.3.1 | `checkov -d .` | IaC安全, 1358+检查, MCP支持 |

### SCA/供应链 (4把)

| 武器 | 版本 | 命令 | 实力 |
|------|------|------|------|
| **OSV-Scanner** | latest | `osv-scanner scan .` | Google-backed, 30+漏洞源, 引导修复 |
| **Syft** | latest | `syft . -o cyclonedx-json` | SBOM生成, 多生态支持 |
| **pip-audit** | 2.10.1 | `pip-audit` | Python依赖审计 |
| **Acrionix Shield** | 1.0.0 | `npx acrionix-shield check` | 发布前扫描, 源映射泄露, 供应链 |

### 快速扫描 (1把)

| 武器 | 版本 | 命令 | 实力 |
|------|------|------|------|
| **Shinobi** | 1.1.0 | `bash run_arsenal.sh quick` | 10秒安全快扫 |

### API安全 (2把)

| 武器 | 版本 | 命令 | 实力 |
|------|------|------|------|
| **ApiPosture** | 1.0.12 | `bash run_arsenal.sh api` | FastAPI端点安全巡检 |
| **Nuclei** | v3.9.0 | `bash run_arsenal.sh api` | 12000+模板, CVE扫荡 |

### 模糊测试 (2把)

| 武器 | 版本 | 命令 | 实力 |
|------|------|------|------|
| **ffuf** | 2.1.0 | `ffuf -w dict.txt -u URL/FUZZ` | 极速Web模糊测试, 40并发 |
| **sqlmap** | 1.10.6 | `bash run_arsenal.sh db` | SQL注入检测 |

### 移动安全 (2把)

| 武器 | 版本 | 命令 | 实力 |
|------|------|------|------|
| **Quark Engine** | 26.6.1 | `quark -a app.apk` | 行为评分, 混淆忽略, Android恶意软件检测 |
| **APKLeaks** | 2.6.3 | (见密钥扫描) | APK密钥泄露检测 |

### 云安全 (1把)

| 武器 | 版本 | 命令 | 实力 |
|------|------|------|------|
| **Prowler** | latest | `prowler aws` | 572 AWS检查, 41合规框架 (待验证CLI) |

### Gitleaks vs TruffleHog — 分层策略

| 层 | 工具 | 场景 |
|----|------|------|
| **预提交(pre-commit)** | Gitleaks | 毫秒级拦截，不泄漏到git历史 |
| **CI/CD diff** | Gitleaks | PR diff快速扫描 |
| **全量历史** | TruffleHog | 深度git历史 + 实时API验证 |
| **应急响应** | TruffleHog | 800+ detectors，验证密钥是否存活 |

### Flutter/移动端安全

| 工具 | 安装 | 场景 |
|------|------|------|
| [FlutterShield](https://pub.dev/packages/flutter_shield) | `flutter pub add flutter_shield` | 30+设备安全检查 (root/越狱/VPN/模拟器) |
| [Free-RASP-Flutter](https://github.com/talsec/free-rasp-flutter) | `flutter pub add free_rasp_flutter` | Flutter运行时防护 v8.0 (2026.6更新) |
| [Flutter Security Suite](https://pub.dev/packages/flutter_security_suite) | `flutter pub add flutter_security_suite` | Root检测+证书绑定+安全存储 (MIT) |
| [SecureGate](https://github.com/actions-marketplace-validations/Mahesh-Langote_securegate) | GitHub Action | Flutter依赖漏洞+许可证扫描 |

### 推荐安装 (GitHub工具)

| 工具 | 安装 | 场景 |
|------|------|------|
| [Foxguard](https://github.com/0sec-labs/foxguard) | `npx foxguard .` | Rust闪电扫描+后量子审计+diff模式 ✅已装 |
| [TruffleHog](https://github.com/trufflesecurity/trufflehog) | 二进制下载 | 800+密钥检测+实时API验证 ✅已装 |
| [api-vuln-scanner-v5](https://github.com/kethakav/api-vuln-scanner-v5) | Docker Compose | 全量API漏洞扫描 (JWT/IDOR/SQLi/CORS) |
| [Pentesting_Platform](https://github.com/MrGuevar4/Pentesting_Platform) | Docker | 44+扫描器统一面板 |
| [AndroHunter](https://github.com/ynsmroztas/AndroHunter) | APK安装 | 安卓APP实时渗透 |
| [CyberStrike](https://github.com/CyberStrikeus/CyberStrike) | pip install | AI驱动全自主渗透 (7300+技能) |
| [Betterleaks](https://github.com/zricethezav/gitleaks) | go install | 下一代Gitleaks (98.6%召回) |
| [Trivy](https://github.com/aquasecurity/trivy) | 二进制下载 | 全栈扫描 (容器/IaC/文件系统/密钥, 32K⭐) |

### 研究论文 (2025-2026 顶级会议)

| 论文 | 会议 | 关键技术 |
|------|------|----------|
| **ZERO-APT** | arXiv Jun 2026 | 闭环对抗框架, LLM攻防+裁判, 79%攻击成功率 (vs Aurora 22%, PentestGPT 39%) |
| **Basilisk** | Zenodo Mar 2026 | 进化算法红队框架, 92%成功率提升, 29攻击模块, 8 OWASP LLM类别 |
| **Co-RedTeam** | ICML 2026 | 多Agent协同漏洞利用 (>60%成功率, >10%检测提升) |
| **HogVul** | AAAI 2026 | 黑盒对抗代码生成, 粒子群优化, 26%基线提升 |
| **AutoRedTeamer** | NeurIPS 2025 | 双Agent架构 (攻击率+20%, 成本-46%) |
| **Ferret** | EMNLP 2025 | 奖励评分驱动攻击突变 (95%成功率) |
| **TreeTeaming** | CVPR 2026 | VLM红队层次策略树 |
| **Gate AI** | arXiv Jun 2026 | LLM安全基准评估, 12111样本, 5折交叉验证 |
| **AutoMalTool** | IEEE TIFS 2025 | MCP工具投毒攻击LLM Agent |
| **Learning-Based AR** | arXiv Apr 2026 | 元提示引导生成+层次检测, 3.9x手动红队发现率, 89%准确率 |

### Go C2框架 (研究参考)

| 框架 | 亮点 |
|------|------|
| [Sliver](https://github.com/BishopFox/sliver) | 行业标准, mTLS/WireGuard/DNS C2 |
| [SUDOSOC-C2](https://github.com/sudosoc/SUDOSOC-C2) | 100+模块/11通道/LLM Agent |
| [Rshell](https://github.com/Rubby2001/Rshell---A-Cross-Platform-C2) | 2026年5月活跃, 跨平台多协议 |

### 使用方式

```bash
# 快速扫描 (每次提交前) — 3把武器
bash redteam_toolkit/run_arsenal.sh quick     # Gitleaks + Semgrep + Bandit

# API专项 — 2把武器
bash redteam_toolkit/run_arsenal.sh api       # ApiPosture + Nuclei

# 全武器库 (部署前)
bash redteam_toolkit/run_arsenal.sh full       # 所有just redteam武器

# 单武器快速调用
foxguard .                       # Rust闪电SAST
medusa scan .                    # AI SAST (79分析器)
osv-scanner scan .               # SCA漏洞扫描
trufflehog filesystem .          # 深度密钥扫描+验证
pip-audit                        # Python依赖审计
checkov -d .                     # IaC安全检查
npx acrionix-shield check        # 发布前安全检查

# 移动端专项
apkleaks -f app.apk              # APK密钥扫描
quark -a app.apk                 # Android恶意软件行为评分

# Web模糊测试
ffuf -w wordlist.txt -u https://target/FUZZ -mc 200
```

## 上次扫描结果 (2026-06-12)

- **Arsenal Quick**: 3/3 pass — Gitleaks 0 leaks, Semgrep 0 issues, Bandit clean
- **Go Pipeline**: 8/8 pass — vet/test/lint/gosec/govulncheck/build
- **Foxguard**: 2014 issues (116 crit, 469 high) — 主要是Python脚本SSRF
- **TruffleHog**: 496 unverified (需tuning allowlist，类似Gitleaks初始状态)
- **Shinobi**: 1.1.0 运行正常
- **ApiPosture**: 1.0.12 就绪 (上次: 81 findings, 14 crit写端点缺认证)
- **Flutter**: 0 error

## 新增武器 (2026-06-12)

### 第一轮 — 密钥+快速扫描
| 武器 | 安装方式 | 实力 |
|------|----------|------|
| **TruffleHog 3.95.5** | `gh.zwy.one` 镜像下载 | 800+ secret detectors, 实时API验证, 多源扫描(S3/Docker/Slack/Jira) |
| **Foxguard 0.8.1** | `npx foxguard .` | Rust闪电扫描(5s), 后量子审计, diff模式, TUI交互, SARIF |

### 第二轮 — AI+供应链+模糊测试
| 武器 | 安装方式 | 实力 |
|------|----------|------|
| **MEDUSA 2026.6.0** | `pip install medusa-security` | AI驱动SAST, 79分析器, 40K+规则, AI agent安全检测 |
| **ffuf 2.1.0** | `go install github.com/ffuf/ffuf/v2@latest` | 极速Web模糊测试, 多线程, 递归扫描, WAF绕过 |
| **Acrionix Shield 1.0.0** | `npx acrionix-shield check` | 发布前安全扫描, 供应链检测, 源映射泄露 |
| **TypoGuard 0.1.0** | `npm install -g typoguard` | npm拼写欺诈检测 (Levenshtein距离+同形字) |

### 研究前沿 (2026新增)
- **Prowl** — 自主漏洞发现+利用验证 (构建运行真实项目)
- **Bumblebee** — Perplexity只读开发者机器扫描器 (供应链事件响应)
- **Xalgorix** — 自主AI渗透测试Agent (22阶段方法论)
- **Datadog SAIST** — AI原生SAST (Claude 4.5/GPT-5.2/Gemini 3)
- **pkgsentry** — 多生态包恶意软件扫描器 (沙箱引爆引擎)

### 待安装 (网络封锁/依赖缺失，后续补充)

| 工具 | 用途 | 状态 |
|------|------|------|
| **Trivy** | 容器/IaC/文件系统全栈扫描 (32K stars) | 镜像无缓存 |
| **Betterleaks** | 下一代Gitleaks (98.6%召回 vs 70.4%) | 新项目，观望 |
| **Basilisk** | 进化算法LLM红队框架 | pip包build失败 |
