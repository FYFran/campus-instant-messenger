#!/usr/bin/env bash
# Pre-commit hook for POSIX environments (Linux/Mac/Git Bash)
# Usage: ln -s ../../scripts/pre-commit.sh .git/hooks/pre-commit
# Or run: cp scripts/pre-commit.sh .git/hooks/pre-commit

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
GITLEAKS_BIN="${GITLEAKS_BIN:-gitleaks}"
GITLEAKS_CONFIG="$PROJECT_DIR/.gitleaks.toml"

if [ "${SKIP_CHECKS:-}" = "1" ]; then
    echo "SKIP_CHECKS=1 — bypassing all pre-commit checks"
    exit 0
fi

HAD_ERROR=0

# --- Gitleaks ---
if [ "${SKIP_GITLEAKS:-}" != "1" ]; then
    if command -v "$GITLEAKS_BIN" &>/dev/null; then
        echo "[gitleaks] Scanning staged changes for secrets..."
        if "$GITLEAKS_BIN" protect --config="$GITLEAKS_CONFIG" --staged 2>&1; then
            echo "[gitleaks] OK"
        else
            echo "[gitleaks] FAIL — secrets detected. Remove or use SKIP_GITLEAKS=1."
            HAD_ERROR=1
        fi
    else
        echo "[gitleaks] WARNING — not installed (install: https://github.com/gitleaks/gitleaks/releases)"
    fi
else
    echo "[gitleaks] skipped (SKIP_GITLEAKS=1)"
fi

# --- Semgrep ---
if [ "${SKIP_SEMGREP:-}" != "1" ]; then
    if command -v semgrep &>/dev/null; then
        echo "[semgrep] Scanning staged Python/Go files..."
        STAGED=$(git diff --cached --name-only --diff-filter=ACM | grep -E '\.(py|go)$' || true)
        if [ -n "$STAGED" ]; then
            echo "$STAGED" | tr '\n' '\0' | xargs -0 semgrep --config="$PROJECT_DIR/.semgrep.yml" --error --no-rewrite-rule-ids 2>&1 && echo "[semgrep] OK" || {
                echo "[semgrep] FAIL — issues found. Fix or use SKIP_SEMGREP=1."
                HAD_ERROR=1
            }
        else
            echo "[semgrep] No staged Python/Go files to scan."
        fi
    else
        echo "[semgrep] WARNING — not installed (install: pip install semgrep)"
    fi
else
    echo "[semgrep] skipped (SKIP_SEMGREP=1)"
fi

if [ "$HAD_ERROR" -eq 1 ]; then
    echo ""
    echo "COMMIT BLOCKED by pre-commit checks."
    echo "Bypass: SKIP_CHECKS=1 git commit"
    exit 1
fi

echo "[OK] Pre-commit checks passed."
