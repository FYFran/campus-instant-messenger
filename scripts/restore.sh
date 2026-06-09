#!/bin/bash
# 校园即时通 — 数据库恢复
# 用法:
#   ./restore.sh list                        列出可用备份
#   ./restore.sh latest [type]               恢复最新的指定类型备份
#   ./restore.sh <filename>                  恢复指定文件（不含路径）
#   ./restore.sh /full/path/to/file.sql.gz   恢复完整路径

set -euo pipefail

BACKUP_DIR="/app/backups"
DB_NAME="campus_app"
DB_USER="campus_admin"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
PGPASSFILE="${PGPASSFILE:-}"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >&2
}

confirm() {
    echo ""
    echo "=============================================="
    echo "  DANGER: this will OVERWRITE ${DB_NAME}"
    echo "=============================================="
    echo ""
    read -r -p "Type YES to proceed: " answer
    if [ "$answer" != "YES" ]; then
        echo "Aborted."
        exit 1
    fi
}

list_backups() {
    local filter="${1:-}"
    local pattern="campus_*.sql.gz"
    if [ -n "$filter" ]; then
        pattern="campus_${filter}_*.sql.gz"
    fi

    echo "Available backups in ${BACKUP_DIR}:"
    echo ""
    find "$BACKUP_DIR" -maxdepth 1 -name "$pattern" -printf '%T@\t%p\n' \
        | sort -t$'\t' -k1 -rn \
        | awk -F'\t' '{
            cmd="date -d @"$1" +\"%Y-%m-%d %H:%M:%S\"";
            cmd | getline d; close(cmd);
            n=split($2, a, "/");
            s=$2; gsub(/.*\//,"",s);
            printf "  %s  %s  %s\n", d, s, $2
        }'
    echo ""
}

find_backup() {
    local input="$1"

    # Full path
    if [ -f "$input" ]; then
        echo "$input"
        return 0
    fi

    # Just filename → search in BACKUP_DIR
    local candidate="${BACKUP_DIR}/${input}"
    if [ -f "$candidate" ]; then
        echo "$candidate"
        return 0
    fi

    # Latest by type
    if [ "$input" = "latest" ]; then
        local type="${2:-}"
        local pattern="campus_*.sql.gz"
        if [ -n "$type" ]; then
            pattern="campus_${type}_*.sql.gz"
        fi
        local latest
        latest=$(find "$BACKUP_DIR" -maxdepth 1 -name "$pattern" -printf '%T@\t%p\n' \
            | sort -t$'\t' -k1 -rn \
            | head -1 \
            | cut -f2)
        if [ -n "$latest" ]; then
            echo "$latest"
            return 0
        fi
    fi

    log "ERROR: backup not found: $input"
    exit 1
}

check_integrity() {
    local file="$1"
    log "CHECK integrity: $(basename "$file")"

    # Verify gzip
    if ! gunzip -t "$file" 2>/dev/null; then
        log "ERROR: file is corrupt (gzip check failed)"
        return 1
    fi

    # Try pg_restore --list (works for custom/directory format)
    local format
    format=$(file "$file" | grep -oP 'gzip|PostgreSQL|custom' || echo "plain")
    if echo "$format" | grep -qi "gzip"; then
        # Plain SQL dump compressed — check for valid SQL header
        if ! zcat "$file" | head -5 | grep -q "^--\|^CREATE\|^INSERT\|^COPY"; then
            log "WARN: compressed SQL dump has no SQL header markers (may still be valid)"
        else
            log "OK: compressed SQL dump looks valid"
        fi
    fi

    return 0
}

do_restore() {
    local file="$1"
    local basename
    basename=$(basename "$file")

    log "RESTORE start: ${basename}"

    # Build connection args
    local conn_args="-h $DB_HOST -p $DB_PORT -U $DB_USER"
    if [ -n "$PGPASSFILE" ] && [ -f "$PGPASSFILE" ]; then
        export PGPASSFILE="$PGPASSFILE"
    fi

    # Drop and recreate database (disconnect all clients first)
    log "DROP and recreate database ${DB_NAME}..."
    PGPASSWORD="${PGPASSWORD:-}" psql $conn_args -d postgres <<-EOSQL
        UPDATE pg_database SET datallowconn = 'false' WHERE datname = '${DB_NAME}';
        SELECT pg_terminate_backend(pg_stat_activity.pid)
        FROM pg_stat_activity
        WHERE pg_stat_activity.datname = '${DB_NAME}' AND pid <> pg_backend_pid();
        DROP DATABASE IF EXISTS "${DB_NAME}";
        CREATE DATABASE "${DB_NAME}" OWNER "${DB_USER}";
EOSQL

    log "RESTORE data from ${basename}..."
    if echo "$basename" | grep -q '\.sql\.gz$'; then
        zcat "$file" | PGPASSWORD="${PGPASSWORD:-}" psql $conn_args -d "$DB_NAME" 2>&1
    else
        log "ERROR: unknown backup format: ${basename}"
        exit 1
    fi

    log "RESTORE complete: ${basename}"
}

main() {
    local cmd="${1:-list}"
    shift 2>/dev/null || true

    # Safety: never run without terminal input for destructive ops
    if [ "$cmd" != "list" ]; then
        if [ ! -t 0 ]; then
            echo "ERROR: restore must be run interactively (not from cron/pipe)" >&2
            exit 1
        fi
    fi

    case "$cmd" in
        list)
            local filter="${1:-}"
            list_backups "$filter"
            ;;
        latest)
            local type="${1:-}"
            local file
            file=$(find_backup "latest" "$type")
            echo "Selected: $file"
            check_integrity "$file"
            confirm
            do_restore "$file"
            ;;
        *)
            local file
            file=$(find_backup "$cmd" "")
            echo "Selected: $file"
            check_integrity "$file"
            confirm
            do_restore "$file"
            ;;
    esac
}

main "$@"
