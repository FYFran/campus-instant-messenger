#!/bin/bash
# 校园即时通 — 数据库自动备份
# 用法: ./backup.sh [hourly|daily|weekly]
# 不传参数时自动根据当前时间决定类型

set -euo pipefail

# ── 配置 ──
BACKUP_DIR="/app/backups"
DB_NAME="campus_app"
DB_USER="campus_admin"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
PGPASSFILE="${PGPASSFILE:-}"
LOCKFILE="/tmp/campus-backup.lock"
RETENTION_HOURLY=24
RETENTION_DAILY=7
RETENTION_WEEKLY=4
LOG_FILE="${BACKUP_DIR}/backup.log"

# ── 自动检测备份类型 ──
detect_type() {
    local hour day
    hour=$(date +%H)
    day=$(date +%u)  # 1=Mon .. 7=Sun
    if [ "$day" = "7" ] && [ "$hour" = "04" ]; then
        echo "weekly"
    elif [ "$hour" = "03" ]; then
        echo "daily"
    else
        echo "hourly"
    fi
}

# ── 日志 ──
log() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $*"
    echo "$msg" | tee -a "$LOG_FILE"
}

# ── 锁 — 防止并发 ──
check_lock() {
    if [ -f "$LOCKFILE" ]; then
        local pid
        pid=$(cat "$LOCKFILE" 2>/dev/null || echo "")
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            log "SKIP: another backup is running (pid $pid)"
            exit 0
        fi
        log "WARN: stale lock removed (pid $pid)"
    fi
    echo $$ > "$LOCKFILE"
    trap 'rm -f "$LOCKFILE"' EXIT
}

# ── 备份 ──
do_backup() {
    local type="$1"
    local timestamp
    timestamp=$(date +%Y%m%d_%H%M%S)
    local filename="campus_${type}_${timestamp}.sql.gz"
    local filepath="${BACKUP_DIR}/${filename}"

    mkdir -p "$BACKUP_DIR"

    log "BACKUP start: type=${type} file=${filename}"

    # 连接参数（支持密码文件）
    if [ -n "$PGPASSFILE" ] && [ -f "$PGPASSFILE" ]; then
        export PGPASSFILE="$PGPASSFILE"
    fi

    # 执行备份
    if PGPASSWORD="${PGPASSWORD:-}" pg_dump \
        -h "$DB_HOST" \
        -p "$DB_PORT" \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        --no-owner \
        --no-acl \
        --verbose 2>> "$LOG_FILE" \
        | gzip > "$filepath"; then

        local size
        size=$(du -h "$filepath" | cut -f1)
        log "BACKUP done: ${filename} (${size})"
    else
        log "BACKUP FAILED: ${filename}"
        rm -f "$filepath"
        return 1
    fi
}

# ── 清理旧备份 ──
rotate() {
    local type="$1"
    local kept=0
    case "$type" in
        hourly) kept=$RETENTION_HOURLY ;;
        daily)  kept=$RETENTION_DAILY ;;
        weekly) kept=$RETENTION_WEEKLY ;;
    esac

    # 保留最新的 N 个，其余删除
    local count before
    before=$(find "$BACKUP_DIR" -maxdepth 1 -name "campus_${type}_*" | wc -l)
    find "$BACKUP_DIR" -maxdepth 1 -name "campus_${type}_*.sql.gz" \
        -printf '%T@\t%p\n' \
        | sort -t$'\t' -k1 -rn \
        | tail -n +$((kept + 1)) \
        | cut -f2 \
        | while IFS= read -r f; do
            rm -f "$f"
            log "ROTATE deleted: $(basename "$f")"
        done

    count=$(find "$BACKUP_DIR" -maxdepth 1 -name "campus_${type}_*" | wc -l)
    local removed=$((before - count))
    if [ "$removed" -gt 0 ]; then
        log "ROTATE done: type=${type} removed=${removed} remaining=${count}"
    fi
}

# ── 健康上报（可选 Webhook） ──
health_report() {
    local status="$1"
    local msg="$2"
    local webhook="${BACKUP_WEBHOOK:-}"
    if [ -n "$webhook" ]; then
        curl -sf -X POST "$webhook" \
            --data-raw "status=${status}&message=${msg}" \
            > /dev/null 2>&1 || true
    fi
}

# ── 主流程 ──
main() {
    local type="${1:-}"
    if [ -z "$type" ]; then
        type=$(detect_type)
    fi
    case "$type" in
        hourly|daily|weekly) ;;
        *) echo "usage: $0 [hourly|daily|weekly]"; exit 1 ;;
    esac

    check_lock
    log "=== Backup session start (type=${type}) ==="

    if do_backup "$type"; then
        rotate "$type"
        health_report "success" "backup ${type} completed"
        log "=== Backup session end (OK) ==="
    else
        health_report "failure" "backup ${type} FAILED"
        log "=== Backup session end (FAILED) ==="
        exit 1
    fi
}

main "$@"
