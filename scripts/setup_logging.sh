#!/bin/bash
# setup_logging.sh — 配置校园即时通结构化JSON日志
# 运行: sudo bash setup_logging.sh
# 创建 /var/log/campus/ 目录 + logrotate 配置

set -euo pipefail

LOG_DIR="/var/log/campus"
APP_USER="${APP_USER:-campus}"
APP_GROUP="${APP_GROUP:-campus}"

echo "=== 校园即时通 日志目录搭建 ==="

# 1. 创建日志目录
mkdir -p "$LOG_DIR"
chown "$APP_USER:$APP_GROUP" "$LOG_DIR"
chmod 755 "$LOG_DIR"
echo "[OK] $LOG_DIR 已创建"

# 2. 创建logrotate配置
cat > /etc/logrotate.d/campus-app << 'LOGROTATE'
/var/log/campus/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    copytruncate
    maxsize 100M
    dateext
    dateformat -%Y%m%d
    postrotate
        # FIXME: verify actual service name on target server
        # systemctl reload campus-app 2>/dev/null || true
    endscript
}
LOGROTATE
chmod 644 /etc/logrotate.d/campus-app
echo "[OK] logrotate 配置已创建 (/etc/logrotate.d/campus-app)"

# 3. 创建日志文件(供Python写入)
touch "$LOG_DIR/app.log" "$LOG_DIR/audit.log" "$LOG_DIR/error.log"
chown "$APP_USER:$APP_GROUP" "$LOG_DIR"/*.log
chmod 644 "$LOG_DIR"/*.log
echo "[OK] 日志文件已创建: app.log audit.log error.log"

# 4. 立即应用logrotate测试
logrotate -d /etc/logrotate.d/campus-app 2>/dev/null && echo "[OK] logrotate 配置验证通过" || echo "[WARN] logrotate 配置测试有警告"

echo ""
echo "=== 完成 ==="
echo "Python 应用启动后会自动检测 $LOG_DIR 并使用结构化 JSON 格式写入"
echo "日志文件:"
echo "  $LOG_DIR/app.log    — 全部应用日志"
echo "  $LOG_DIR/audit.log  — 安全审计事件(密码重置/角色变更)"
echo "  $LOG_DIR/error.log  — 错误日志(仅 ERROR 级别)"
echo ""
echo "手动测试: journalctl -u campus-app --since '5 min ago'"
