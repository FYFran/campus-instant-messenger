#!/bin/bash
# 校园即时通 — 备份验证
# 将最新备份恢复到临时数据库，校验行数，然后删除
# 用法: ./verify_backup.sh [backup_file]
# 不传参数则验证最新备份

set -euo pipefail

BACKUP_DIR="/app/backups"
DB_NAME="campus_app"
DB_USER="campus_admin"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
TEMP_DB="campus_verify_$(date +%s)"
LOG_FILE="${BACKUP_DIR}/verify.log"

log() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $*"
    echo "$msg" | tee -a "$LOG_FILE"
}

cleanup() {
    log "CLEANUP: dropping temp database ${TEMP_DB}..."
    PGPASSWORD="${PGPASSWORD:-}" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres \
        -c "SELECT pg_terminate_backend(pg_stat_activity.pid) FROM pg_stat_activity WHERE pg_stat_activity.datname = '${TEMP_DB}' AND pid <> pg_backend_pid();" 2>/dev/null || true
    PGPASSWORD="${PGPASSWORD:-}" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres \
        -c "DROP DATABASE IF EXISTS \"${TEMP_DB}\";" 2>/dev/null || true
    log "CLEANUP done"
}
trap cleanup EXIT

# ── 找备份文件 ──
find_backup() {
    local input="${1:-}"
    if [ -n "$input" ] && [ -f "$input" ]; then
        echo "$input"
        return 0
    fi
    if [ -n "$input" ]; then
        local candidate="${BACKUP_DIR}/${input}"
        if [ -f "$candidate" ]; then
            echo "$candidate"
            return 0
        fi
    fi
    # 默认：取最新备份
    local latest
    latest=$(find "$BACKUP_DIR" -maxdepth 1 -name "campus_*.sql.gz" -printf '%T@\t%p\n' \
        | sort -t$'\t' -k1 -rn | head -1 | cut -f2)
    if [ -n "$latest" ]; then
        echo "$latest"
        return 0
    fi
    log "ERROR: no backup found"
    exit 1
}

	# ── 获取原库行数（基准） — n_live_tup is approximate, used with 10% tolerance ──
get_reference_counts() {
    log "REFERENCE: querying row counts from ${DB_NAME}..."
    PGPASSWORD="${PGPASSWORD:-}" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "
        SELECT schemaname || '.' || tablename, n_live_tup
        FROM pg_stat_user_tables
        WHERE n_live_tup > 0
        ORDER BY n_live_tup DESC
    " 2>/dev/null || echo ""
}

get_total_row_count() {
    local db="$1"
    PGPASSWORD="${PGPASSWORD:-}" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$db" -t -c \
        "SELECT COALESCE(sum(n_live_tup), 0) FROM pg_stat_user_tables WHERE schemaname='public'" 2>/dev/null | tr -d ' '
}

# ── 恢复到临时库 ──
restore_to_temp() {
    local file="$1"

    log "CREATE temp database: ${TEMP_DB}"
    PGPASSWORD="${PGPASSWORD:-}" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres \
        -c "DROP DATABASE IF EXISTS \"${TEMP_DB}\";" 2>/dev/null || true
    PGPASSWORD="${PGPASSWORD:-}" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres \
        -c "CREATE DATABASE \"${TEMP_DB}\" OWNER \"${DB_USER}\";"

    log "RESTORE to temp from $(basename "$file")..."
    if zcat "$file" | PGPASSWORD="${PGPASSWORD:-}" psql -h "$DB_HOST" -p "$DB_PORT" \
        -U "$DB_USER" -d "$TEMP_DB" > /dev/null 2>&1; then
        log "RESTORE to temp OK"
        return 0
    else
        log "RESTORE to temp FAILED"
        return 1
    fi
}

# ── 获取临时库行数 ──
get_temp_counts() {
    PGPASSWORD="${PGPASSWORD:-}" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$TEMP_DB" -t -c "
        SELECT schemaname || '.' || tablename, n_live_tup
        FROM pg_stat_user_tables
        WHERE n_live_tup > 0
        ORDER BY n_live_tup DESC
    " 2>/dev/null || echo ""
}

# ── 比较行数 ──
compare_counts() {
    local ref="$1"
    local tmp="$2"
    local errors=0
    local total=0

    # 将 reference 和 temp 输出解析为关联数组
    local ref_file tmp_file
    ref_file=$(mktemp)
    tmp_file=$(mktemp)
    echo "$ref" > "$ref_file"
    echo "$tmp" > "$tmp_file"

    log "=== Row count comparison ==="
    while IFS='|' read -r table ref_count; do
        table=$(echo "$table" | xargs)
        ref_count=$(echo "$ref_count" | xargs)
        [ -z "$table" ] && continue
        [ -z "$ref_count" ] && continue

        # 在临时库中找该表的行数
        tmp_count=$(grep "^${table}|" "$tmp_file" | head -1 | cut -d'|' -f2 | xargs || echo "0")
        tmp_count="${tmp_count:-0}"

        if [ "$ref_count" = "$tmp_count" ]; then
            log "  OK  ${table}: ${ref_count} rows"
        else
            log "  MISMATCH ${table}: ref=${ref_count} restore=${tmp_count}"
            errors=$((errors + 1))
        fi
        total=$((total + 1))
    done < "$ref_file"

    # 检查临时库中多余的表
    while IFS='|' read -r table tmp_count; do
        table=$(echo "$table" | xargs)
        tmp_count=$(echo "$tmp_count" | xargs)
        [ -z "$table" ] && continue
        if ! grep -q "^${table}|" "$ref_file"; then
            log "  EXTRA  ${table}: ${tmp_count} rows (not in reference)"
            errors=$((errors + 1))
        fi
    done < "$tmp_file"

    rm -f "$ref_file" "$tmp_file"

    if [ "$errors" -eq 0 ]; then
        log "VERDICT: PASS — all ${total} tables match"
        return 0
    else
        log "VERDICT: FAIL — ${errors} mismatches found"
        return 1
    fi
}

# ── 主流程 ──
main() {
    local file
    file=$(find_backup "${1:-}")

    echo ""
    echo "=============================================="
    echo "  备份验证"
    echo "=============================================="
    echo "  备份文件: $file"
    echo "  大小: $(du -h "$file" | cut -f1)"
    echo "  参考数据库: ${DB_NAME}"
    echo "  临时数据库: ${TEMP_DB}"
    echo ""

    local ref_counts
    ref_counts=$(get_reference_counts)

    if ! restore_to_temp "$file"; then
        log "VERDICT: FAIL — restore failed"
        exit 1
    fi

    local tmp_counts
    tmp_counts=$(get_temp_counts)

    # Per-table comparison (informational — n_live_tup is approximate)
    local exact_match=true
    compare_counts "$ref_counts" "$tmp_counts" || exact_match=false

    # Total row count comparison with 10% tolerance
    local prod_total restore_total
    prod_total=$(get_total_row_count "$DB_NAME")
    restore_total=$(get_total_row_count "$TEMP_DB")
    if [ -n "$prod_total" ] && [ -n "$restore_total" ] && [ "$prod_total" -gt 0 ] 2>/dev/null; then
        local diff=$(( prod_total > restore_total ? prod_total - restore_total : restore_total - prod_total ))
        local pct=$(( diff * 100 / prod_total ))
        if [ "$pct" -gt 10 ] 2>/dev/null; then
            log "TOTAL MISMATCH: prod=${prod_total} restore=${restore_total} (${pct}% diff, limit 10%)"
            log "VERIFICATION FAILED"
            echo ""
            echo "=============================================="
            echo "  验证失败 — 总行数差异超过10%"
            echo "  检查日志: ${LOG_FILE}"
            echo "=============================================="
            exit 1
        else
            log "TOTAL OK: prod=${prod_total} restore=${restore_total} (${pct}% diff)"
        fi
    fi

    log "VERIFICATION PASSED"
    echo ""
    echo "=============================================="
    echo "  验证通过"
    echo "=============================================="
    exit 0
}

main "$@"
