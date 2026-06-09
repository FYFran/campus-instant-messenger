#!/bin/bash
# 校园即时通 — 全面安全扫描执行器
# Runs all security tools in sequence. Exit code tracks failures.
# Usage: ./scripts/full_security_scan.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
HAD_ERROR=0

cd "$PROJECT_DIR"

echo "=========================================="
echo "  校园即时通 — Full Security Scan"
echo "  $(date '+%Y-%m-%d %H:%M')"
echo "=========================================="
echo ""

# 1. Secret scan — gitleaks
echo "--- 1. Secret Scan (gitleaks) ---"
if command -v "$PROJECT_DIR/.gitleaks/gitleaks.exe" &>/dev/null; then
    if "$PROJECT_DIR/.gitleaks/gitleaks.exe" detect --source . --no-git -v 2>&1 | tail -5; then
        echo "[gitleaks] OK"
    else
        echo "[gitleaks] FAIL — secrets detected"
        HAD_ERROR=1
    fi
elif command -v gitleaks &>/dev/null; then
    if gitleaks detect --source . --no-git -v 2>&1 | tail -5; then
        echo "[gitleaks] OK"
    else
        echo "[gitleaks] FAIL — secrets detected"
        HAD_ERROR=1
    fi
else
    echo "[gitleaks] NOT INSTALLED — skipping"
fi
echo ""

# 2. SAST — semgrep
echo "--- 2. SAST (semgrep) ---"
if command -v semgrep &>/dev/null; then
    if semgrep --config auto --error 2>&1 | tail -5; then
        echo "[semgrep] OK"
    else
        echo "[semgrep] FAIL — issues found"
        HAD_ERROR=1
    fi
else
    echo "[semgrep] NOT INSTALLED — skipping"
fi
echo ""

# 3. Flutter analyze
echo "--- 3. Flutter analyze ---"
if command -v flutter &>/dev/null; then
    if cd campus_app && flutter analyze --no-pub 2>&1 | tail -3; then
        echo "[flutter] OK"
    else
        echo "[flutter] FAIL"
        HAD_ERROR=1
    fi
    cd "$PROJECT_DIR"
else
    echo "[flutter] NOT INSTALLED — skipping"
fi
echo ""

# 4. Python AST check
echo "--- 4. Python AST check ---"
PY_OK=0
for f in campus_app/server/main.py campus_app/server/main_remote.py; do
    if python -c "import ast; ast.parse(open('$f', encoding='utf-8').read()); print('OK: $f')" 2>&1; then
        : $((PY_OK++))
    else
        echo "FAIL: $f"
        HAD_ERROR=1
    fi
done
echo "[Python] $PY_OK of 2 files passed"
echo ""

# 5. Go build
echo "--- 5. Go build ---"
if command -v go &>/dev/null; then
    cd campus_go && go build ./... 2>&1 || { echo "[go] BUILD FAILED"; HAD_ERROR=1; }
    cd "$PROJECT_DIR"
else
    echo "[go] NOT INSTALLED — skipping"
fi
echo ""

# 6. Campus check
echo "--- 6. Campus check ---"
if python campus_check.py 2>&1 | tail -5; then
    echo "[campus_check] OK"
else
    echo "[campus_check] FAIL"
    HAD_ERROR=1
fi
echo ""

# Summary
echo "=========================================="
if [ "$HAD_ERROR" -eq 1 ]; then
    echo "RESULT: FAILURES DETECTED"
    exit 1
else
    echo "RESULT: ALL CHECKS PASSED"
fi
echo "=========================================="
