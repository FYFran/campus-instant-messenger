# 🔴 Red Team Arsenal — CampusGo

## 武器清单

### 已集成 (本地一键运行)

| 武器 | 命令 | 用途 |
|------|------|------|
| **Gitleaks** | `bash run_arsenal.sh quick` | 密钥/令牌泄露检测 |
| **Semgrep** | `bash run_arsenal.sh full` | 多语言SAST (Python/Go/Dart) |
| **Shinobi** | `bash run_arsenal.sh quick` | 10秒安全快扫 (密钥/危险默认值/AI风险) |
| **ApiPosture** | `bash run_arsenal.sh api` | FastAPI端点安全巡检 (124端点覆盖) |
| **Nuclei** | `bash run_arsenal.sh api` | 漏洞模板扫描 (生产服务器) |
| **sqlmap** | `bash run_arsenal.sh db` | SQL注入检测 |

### 推荐安装 (GitHub工具)

| 工具 | 安装 | 场景 |
|------|------|------|
| [api-vuln-scanner-v5](https://github.com/kethakav/api-vuln-scanner-v5) | Docker Compose | 全量API漏洞扫描 (JWT/IDOR/SQLi/CORS) |
| [Pentesting_Platform](https://github.com/MrGuevar4/Pentesting_Platform) | Docker | 44+扫描器统一面板 |
| [AndroHunter](https://github.com/ynsmroztas/AndroHunter) | APK安装 | 安卓APP实时渗透 |
| [RevEngi App](https://github.com/RevEngiSquad/revengi-app) | Web/APK | Flutter APK逆向分析 |
| [Free-RASP-Flutter](https://github.com/talsec/free-rasp-flutter) | pub add | Flutter运行时防护 |
| [CyberStrike](https://github.com/CyberStrikeus/CyberStrike) | pip install | AI驱动全自主渗透 (7300+技能) |

### 研究论文 (2025-2026 顶级会议)

| 论文 | 会议 | 关键技术 |
|------|------|----------|
| Co-RedTeam | ICML 2026 | 多Agent协同漏洞利用 (>60%成功率) |
| AutoRedTeamer | NeurIPS 2025 | 双Agent架构 (攻击率+20%, 成本-46%) |
| Ferret | EMNLP 2025 | 奖励评分驱动攻击突变 (95%成功率) |
| TreeTeaming | CVPR 2026 | VLM红队层次策略树 |
| AutoMalTool | IEEE TIFS 2025 | MCP工具投毒攻击LLM Agent |

### Go C2框架 (研究参考)

| 框架 | 亮点 |
|------|------|
| [Sliver](https://github.com/BishopFox/sliver) | 行业标准, mTLS/WireGuard/DNS C2 |
| [SUDOSOC-C2](https://github.com/sudosoc/SUDOSOC-C2) | 100+模块/11通道/LLM Agent |
| [Rshell](https://github.com/Rubby2001/Rshell---A-Cross-Platform-C2) | 2026年5月活跃, 跨平台多协议 |

## 使用方式

```bash
# 快速扫描 (每次提交前)
bash redteam_toolkit/run_arsenal.sh quick

# API专项
bash redteam_toolkit/run_arsenal.sh api

# 全武器库 (部署前)
bash redteam_toolkit/run_arsenal.sh full

# 通过just
just redteam          # quick scan
just redteam-full     # full arsenal
```

## 上次扫描结果 (2026-06-11)

- Shinobi: 8 findings (0 crit, 0 high, 3 med)
- ApiPosture: 81 findings across 124 endpoints (14 crit, 64 high)
  - 14 critical: 全部是"写端点缺少认证" — 待修复
- Go Shinobi: 4 findings (1 high: 输入消毒缺失)
