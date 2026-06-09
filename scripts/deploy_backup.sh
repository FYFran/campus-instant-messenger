#!/bin/bash
# 校园即时通 — 备份系统部署
# 将本地 scripts/ 下的备份相关文件上传到服务器并启用
# 用法: ./deploy_backup.sh

set -euo pipefail

SSH_HOST="root@139.196.50.134"
SSH_PORT="22"
SSH_KEY="${SSH_KEY:-}"
LOCAL_SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd)"
REMOTE_SCRIPTS_DIR="/app/scripts"
REMOTE_SYSTEMD_DIR="/etc/systemd/system"

# ── 文件清单 ──
FILES=(
    "backup.sh"
    "restore.sh"
    "verify_backup.sh"
    "campus-backup.service"
    "campus-backup.timer"
)

log() {
    echo "[$(date '+%H:%M:%S')] $*"
}

confirm() {
    echo ""
    echo "=============================================="
    echo "  部署目标: ${SSH_HOST}"
    echo "  本地目录: ${LOCAL_SCRIPTS_DIR}"
    echo "  远程目录: ${REMOTE_SCRIPTS_DIR}"
    echo "=============================================="
    echo ""
    read -r -p "Continue? [y/N] " answer
    case "$answer" in
        y|Y|yes|YES) ;;
        *) echo "Aborted."; exit 1 ;;
    esac
}

upload_scripts() {
    log "CREATE remote directory..."
    ssh ${SSH_KEY:+-i "$SSH_KEY"} "$SSH_HOST" \
        "mkdir -p ${REMOTE_SCRIPTS_DIR} ${REMOTE_SCRIPTS_DIR%/*}/backups"

    for file in "${FILES[@]}"; do
        local src="${LOCAL_SCRIPTS_DIR}/${file}"
        if [ ! -f "$src" ]; then
            log "WARN: ${file} not found locally, skipping"
            continue
        fi

        local dst="${REMOTE_SCRIPTS_DIR}/${file}"
        log "UPLOAD ${file} → ${SSH_HOST}:${dst}"
        scp ${SSH_KEY:+-i "$SSH_KEY"} -P "$SSH_PORT" "$src" "${SSH_HOST}:${dst}"
    done

    log "SET permissions (755)..."
    ssh ${SSH_KEY:+-i "$SSH_KEY"} "$SSH_HOST" \
        "chmod 755 ${REMOTE_SCRIPTS_DIR}/*.sh"
}

install_systemd() {
    log "INSTALL systemd units..."
    for unit in campus-backup.service campus-backup.timer; do
        ssh ${SSH_KEY:+-i "$SSH_KEY"} "$SSH_HOST" \
            "cp ${REMOTE_SCRIPTS_DIR}/${unit} ${REMOTE_SYSTEMD_DIR}/${unit}"
    done

    log "RELOAD systemd..."
    ssh ${SSH_KEY:+-i "$SSH_KEY"} "$SSH_HOST" "systemctl daemon-reload"

    log "ENABLE and START timer..."
    ssh ${SSH_KEY:+-i "$SSH_KEY"} "$SSH_HOST" \
        "systemctl enable campus-backup.timer && systemctl start campus-backup.timer"
}

verify() {
    log "=== Verification ==="
    echo ""
    echo "--- Timer status ---"
    ssh ${SSH_KEY:+-i "$SSH_KEY"} "$SSH_HOST" \
        "systemctl status campus-backup.timer --no-pager 2>&1 | head -15"
    echo ""
    echo "--- Service status ---"
    ssh ${SSH_KEY:+-i "$SSH_KEY"} "$SSH_HOST" \
        "systemctl status campus-backup.service --no-pager 2>&1 | head -10"
    echo ""
    echo "--- Next triggers ---"
    ssh ${SSH_KEY:+-i "$SSH_KEY"} "$SSH_HOST" \
        "systemctl list-timers campus-backup.timer --no-pager 2>&1"
    echo ""
    echo "--- Run test backup ---"
    ssh ${SSH_KEY:+-i "$SSH_KEY"} "$SSH_HOST" \
        "${REMOTE_SCRIPTS_DIR}/backup.sh hourly"
    echo ""
    echo "--- List backups ---"
    ssh ${SSH_KEY:+-i "$SSH_KEY"} "$SSH_HOST" \
        "ls -lh /app/backups/ 2>&1 | head -10"
}

# ── 主流程 ──
main() {
    echo "=============================================="
    echo "  校园即时通 — 备份系统部署"
    echo "=============================================="
    echo ""

    confirm
    upload_scripts
    install_systemd
    verify

    echo ""
    echo "=============================================="
    echo "  部署完成"
    echo "=============================================="
    echo ""
    echo "  文件位置:"
    echo "    ${REMOTE_SCRIPTS_DIR}/backup.sh"
    echo "    ${REMOTE_SCRIPTS_DIR}/restore.sh"
    echo "    ${REMOTE_SCRIPTS_DIR}/verify_backup.sh"
    echo "    ${REMOTE_SYSTEMD_DIR}/campus-backup.{service,timer}"
    echo ""
    echo "  定时计划:"
    echo "    ● 每小时  → hourly 备份 (保留24份)"
    echo "    ● 每日3时 → daily 备份 (保留7份)"
    echo "    ● 周日4时 → weekly 备份 (保留4份)"
    echo ""
    echo "  手动操作:"
    echo "    ssh root@139.196.50.134 \"${REMOTE_SCRIPTS_DIR}/backup.sh\""
    echo "    ssh root@139.196.50.134 \"${REMOTE_SCRIPTS_DIR}/restore.sh list\""
    echo "    ssh root@139.196.50.134 \"${REMOTE_SCRIPTS_DIR}/verify_backup.sh\""
    echo ""
}

main
