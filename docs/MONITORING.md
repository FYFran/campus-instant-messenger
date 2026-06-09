# 校园即时通 监控告警系统

## 概览

| 组件 | 位置 | 说明 |
|------|------|------|
| 健康检查 API | `GET /api/health` | 公共只读端点，返回数据库/缓存/磁盘/内存状态 |
| 详细健康 API | `GET /api/health/detailed` | admin 专用，含表行数估算和环境信息 |
| Shell 监控脚本 | `/usr/local/bin/campus-monitor.sh` | 每 2 分钟运行，告警通过 ntfy.sh 推送 |
| Systemd 定时器 | `campus-monitor.timer` | 触发监控脚本 |
| 结构化日志 | `/var/log/campus/*.log` | JSON 格式，按日轮转 |
| Logrotate | `/etc/logrotate.d/campus-app` | 保留 30 天，100MB 上限 |

## 健康检查端点

### `GET /api/health`

```json
{
  "status": "ok",
  "uptime_seconds": 3600,
  "version": "1.0.4",
  "database": "ok",
  "redis": "ok",
  "pool": {
    "connected_connections": 5,
    "idle_connections": 3,
    "current_size": 8,
    "min_size": 2,
    "max_size": 20
  },
  "disk": {
    "total_gb": 40.0,
    "used_gb": 12.3,
    "free_gb": 27.7,
    "used_pct": 30.8
  },
  "memory": {
    "total_mb": 8192.0,
    "available_mb": 4096.0,
    "used_pct": 50.0
  }
}
```

### `GET /api/health/detailed`

需要 `college_admin` 或 `school_admin` 角色。包含 `/api/health` 全部字段，外加：

- `table_row_estimates` — PostgreSQL 各表行数估算
- `environment` — Python 版本 / 平台 / 工作目录

## 告警阈值

| 指标 | 阈值 | 动作 |
|------|------|------|
| 服务宕机 | 任何检查失败 | ntfy `high` 推送 |
| 磁盘使用率 | > 85% | ntfy `high` 推送 |
| 可用内存 | < 200 MB | ntfy `high` 推送 |
| Nginx 状态 | 非 active | ntfy `high` 推送 |
| SSL 证书 | < 14 天到期 | ntfy `high` 推送 |

## 如何添加新检查

编辑 `scripts/monitor.sh`，添加检查函数：

```bash
check_endpoint "名称" "http://localhost/api/端点" '"expected":"value"'
```

或者对非 API 指标直接写条件判断：

```bash
if [ some_condition ]; then
    notify "告警标题" "告警消息"
fi
```

## 维护期静默告警

创建标记文件阻止通知：

```bash
sudo touch /var/run/campus-monitor.maintenance
sudo chmod 644 /var/run/campus-monitor.maintenance
```

监控脚本会自动检测该文件并跳过所有通知（仅在日志中记录）。

取消静默：

```bash
sudo rm -f /var/run/campus-monitor.maintenance
```

## 日志文件位置

| 文件 | 内容 | 格式 |
|------|------|------|
| `/var/log/campus/app.log` | 全部应用日志 | JSON 行 |
| `/var/log/campus/audit.log` | 安全审计（密码重置/角色变更） | JSON 行 |
| `/var/log/campus/error.log` | 仅 ERROR 级别 | JSON 行 |

日志轮转由 logrotate 管理：每日轮转，保留 30 天，单文件上限 100MB。

各日志行示例：

```json
{"timestamp":"2026-06-09T10:30:00.123","level":"INFO","logger":"app","message":"Server started"}
{"timestamp":"2026-06-09T10:30:05.456","level":"INFO","logger":"audit","message":"AUDIT: password_reset by=1 target=202301001 ip=10.0.0.1"}
{"timestamp":"2026-06-09T10:31:00.789","level":"ERROR","logger":"error","message":"Database connection failed","exception":"Traceback ..."}
```

## 部署步骤

```bash
# 1. 部署监控脚本
sudo cp scripts/monitor.sh /usr/local/bin/campus-monitor.sh
sudo chmod +x /usr/local/bin/campus-monitor.sh

# 2. 配置 ntfy 凭据（替换 CHANGEME）
# 编辑 /etc/systemd/system/campus-monitor.service 中的 NTFY_* 环境变量

# 3. 安装 systemd 单元
sudo cp scripts/campus-monitor.service /etc/systemd/system/
sudo cp scripts/campus-monitor.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now campus-monitor.timer

# 4. 设置日志目录
sudo bash scripts/setup_logging.sh

# 5. 验证
systemctl status campus-monitor.timer
curl http://localhost/api/health | jq .
```
