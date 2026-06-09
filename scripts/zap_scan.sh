#!/bin/bash
# 校园即时通 — ZAP DAST 自动化扫描
# Requires: docker (zap runs via ghcr.io/zaproxy/zaproxy:stable)
# Usage: ./scripts/zap_scan.sh [target_url]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Source context config if present
CONTEXT_FILE="$SCRIPT_DIR/zap_context.config"
[ -f "$CONTEXT_FILE" ] && source "$CONTEXT_FILE"

TARGET="${1:-${ZAP_TARGET_URL:-http://139.196.50.134}}"
REPORT_DIR="$PROJECT_DIR/reports/zap"
mkdir -p "$REPORT_DIR"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
HTML_REPORT="${TIMESTAMP}_zap_report.html"
MARKDOWN_REPORT="${TIMESTAMP}_zap_report.md"

echo "[ZAP] Target: $TARGET"
echo "[ZAP] Reports: $REPORT_DIR"

# On Windows (Git Bash/MSYS2), Docker Desktop handles /f/... paths natively
docker run --rm \
  -v "$REPORT_DIR:/zap/wrk" \
  ghcr.io/zaproxy/zaproxy:stable \
  zap-baseline.py \
    -t "$TARGET" \
    -r "$HTML_REPORT" \
    -w "$MARKDOWN_REPORT" \
    -I "/api/" \
    -X "/api/health" \
    -X "/api/version" \
    --auto \
    -j

echo "[ZAP] HTML report: reports/zap/$HTML_REPORT"
echo "[ZAP] Markdown report: reports/zap/$MARKDOWN_REPORT"

# Check for HIGH or CRITICAL alerts in the markdown report
if [ -f "$REPORT_DIR/$MARKDOWN_REPORT" ]; then
    HIGH_COUNT=$(grep -cE '^\|.*\bHigh\b' "$REPORT_DIR/$MARKDOWN_REPORT" 2>/dev/null || true)
    CRIT_COUNT=$(grep -cE '^\|.*\bCritical\b' "$REPORT_DIR/$MARKDOWN_REPORT" 2>/dev/null || true)
    if [ "$HIGH_COUNT" -gt 0 ] || [ "$CRIT_COUNT" -gt 0 ]; then
        echo "[ZAP] WARNING: High=$HIGH_COUNT Critical=$CRIT_COUNT alerts found!"
        exit 1
    fi
fi

echo "[ZAP] OK — no HIGH/CRITICAL alerts."
