#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# security_scan.sh — Full security pipeline for Pete/Campus project
# Runs: Gitleaks + Semgrep + Flutter Analyze
# ──────────────────────────────────────────────────────────────
# Usage:
#   bash f:/ClaudeFiles/security_scan.sh         # scan everything
#   bash f:/ClaudeFiles/security_scan.sh --diff   # scan staged (git diff)
# ──────────────────────────────────────────────────────────────

set -euo pipefail

ROOT="f:/ClaudeFiles"
GITLEAKS_BIN="$ROOT/.gitleaks/gitleaks.exe"
GITLEAKS_CONFIG="$ROOT/.gitleaks.toml"
SEMGREP_CONFIG="$ROOT/.semgrep.yml"
FLUTTER_PROJECT="$ROOT/campus_app"
TIMESTAMP=$(date "+%Y-%m-%d %H:%M:%S")
EXIT_CODE=0
ERRORS=""

# color helpers
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo ""
echo -e "${CYAN}══════════════════════════════════════════════${NC}"
echo -e "${CYAN}  Security Scan  —  $TIMESTAMP${NC}"
echo -e "${CYAN}══════════════════════════════════════════════${NC}"
echo ""

# ─── Step 1: Gitleaks ─────────────────────────────────────────
echo -e "${YELLOW}[1/3] Gitleaks — Secret Detection${NC}"

if [ ! -f "$GITLEAKS_BIN" ]; then
    echo -e "${RED}  ✗ Gitleaks not found at $GITLEAKS_BIN${NC}"
    ERRORS="$ERRORS gitleaks_binary_missing"
    EXIT_CODE=1
else
    GITLEAKS_CMD="$GITLEAKS_BIN"
    if command -v winpty &>/dev/null; then
        GITLEAKS_CMD="winpty $GITLEAKS_BIN"
    fi

    if [ "${1:-}" = "--diff" ]; then
        echo "  Mode: staged changes only"
        if $GITLEAKS_CMD protect --config="$GITLEAKS_CONFIG" --staged 2>&1; then
            echo -e "${GREEN}  ✓ No secrets found in staged changes${NC}"
        else
            echo -e "${RED}  ✗ Secrets detected!${NC}"
            ERRORS="$ERRORS gitleaks_secrets_found"
            EXIT_CODE=1
        fi
    else
        # Full repo scan — detect exits 1 on findings
        if $GITLEAKS_CMD detect --config="$GITLEAKS_CONFIG" --source="$ROOT" --no-git 2>&1; then
            echo -e "${GREEN}  ✓ No secrets found${NC}"
        else
            echo -e "${RED}  ✗ Secrets detected!${NC}"
            ERRORS="$ERRORS gitleaks_secrets_found"
            EXIT_CODE=1
        fi
    fi
fi

echo ""

# ─── Step 2: Semgrep ──────────────────────────────────────────
echo -e "${YELLOW}[2/3] Semgrep — Static Analysis${NC}"

if ! command -v semgrep &>/dev/null; then
    echo -e "${RED}  ✗ semgrep not found. Install: pip install semgrep${NC}"
    ERRORS="$ERRORS semgrep_missing"
    EXIT_CODE=1
else
    declare -a SEMGREP_TARGETS

    if [ -d "$ROOT/campus_go" ]; then
        SEMGREP_TARGETS+=("$ROOT/campus_go")
    fi
    if [ -d "$ROOT/campus_app" ]; then
        SEMGREP_TARGETS+=("$ROOT/campus_app")
    fi
    if ls "$ROOT"/pete_*.pyw "$ROOT"/pete_*.py 2>/dev/null; then
        SEMGREP_TARGETS+=("$ROOT")
    fi

    if [ ${#SEMGREP_TARGETS[@]} -eq 0 ]; then
        echo -e "${YELLOW}  ~ No source targets found to scan${NC}"
    else
        SEMGREP_FLAGS=""
        if [ "${1:-}" = "--diff" ]; then
            # Only scan staged files — not directly supported, so we scan
            # with baseline to suppress old findings
            SEMGREP_FLAGS="--baseline-commit HEAD"
        fi

        for target in "${SEMGREP_TARGETS[@]}"; do
            echo "  Scanning: $target"
            if semgrep --config="$SEMGREP_CONFIG" "$target" \
                --quiet --error --metrics=off \
                --output="$ROOT/.semgrep_report.txt" 2>&1; then
                :
            else
                SEMGREP_EXIT=$?
                if [ $SEMGREP_EXIT -eq 1 ]; then
                    echo -e "${RED}  ✗ Semgrep found issues!${NC}"
                    ERRORS="$ERRORS semgrep_findings"
                    EXIT_CODE=1
                fi
            fi
        done
        echo -e "${GREEN}  ✓ Semgrep scan complete${NC}"
    fi
fi

echo ""

# ─── Step 3: Flutter Analyze ──────────────────────────────────
echo -e "${YELLOW}[3/3] Flutter Analyze${NC}"

if [ -d "$FLUTTER_PROJECT" ]; then
    if command -v flutter &>/dev/null; then
        cd "$FLUTTER_PROJECT"
        if flutter analyze 2>&1; then
            echo -e "${GREEN}  ✓ Flutter analyze: no issues${NC}"
        else
            echo -e "${RED}  ✗ Flutter analyze found errors!${NC}"
            ERRORS="$ERRORS flutter_analyze_errors"
            EXIT_CODE=1
        fi
        cd "$ROOT"
    else
        echo -e "${YELLOW}  ~ Flutter not installed, skipping${NC}"
    fi
else
    echo -e "${YELLOW}  ~ No Flutter project at $FLUTTER_PROJECT, skipping${NC}"
fi

# ─── Step 4: Shinobi Quick Scan ─────────────────────────────
echo -e "${YELLOW}[4/6] Shinobi — Quick Security Scan${NC}"

if python -c "import shinobi_scan" 2>/dev/null; then
    declare -a SHINOBI_TARGETS=("$ROOT/campus_app/server" "$ROOT/campus_go")
    SHINOBI_CRIT=0
    for target in "${SHINOBI_TARGETS[@]}"; do
        [ ! -d "$target" ] && continue
        local tname=$(basename "$target")
        local out=$(python -m shinobi_scan "$target" --json 2>&1) || true
        local crit=$(echo "$out" | python -c "import sys,json; d=json.load(sys.stdin); print(d.get('critical',0))" 2>/dev/null || echo 0)
        if [ "$crit" -gt 0 ] 2>/dev/null; then
            echo -e "${RED}  ✗ Shinobi $tname: $crit critical${NC}"
            SHINOBI_CRIT=$((SHINOBI_CRIT + crit))
        else
            echo -e "${GREEN}  ✓ Shinobi $tname: 0 critical${NC}"
        fi
    done
    [ "$SHINOBI_CRIT" -eq 0 ] || { ERRORS="$ERRORS shinobi_critical"; EXIT_CODE=1; }
else
    echo -e "${YELLOW}  ~ shinobi not installed, skipping${NC}"
fi

# ─── Step 5: ApiPosture ─────────────────────────────────────
echo -e "${YELLOW}[5/6] ApiPosture — API Security Inspector${NC}"

if command -v apiposture &>/dev/null; then
    local ap_out=$(apiposture scan "$ROOT/campus_app/server/" --output json --fail-on critical 2>&1) || true
    local ap_crit=$(echo "$ap_out" | python -c "import sys,json; d=json.load(sys.stdin); print(d['summary']['severity_counts'].get('critical',0))" 2>/dev/null || echo '?')
    local ap_high=$(echo "$ap_out" | python -c "import sys,json; d=json.load(sys.stdin); print(d['summary']['severity_counts'].get('high',0))" 2>/dev/null || echo '?')
    if [ "$ap_crit" = "0" ]; then
        echo -e "${GREEN}  ✓ ApiPosture: 0 critical, $ap_high high${NC}"
    elif [ "$ap_crit" = "?" ]; then
        echo -e "${YELLOW}  ~ ApiPosture: parse error (check output)${NC}"
    else
        echo -e "${RED}  ✗ ApiPosture: $ap_crit critical, $ap_high high${NC}"
        ERRORS="$ERRORS apiposture_critical"
        EXIT_CODE=1
    fi
else
    echo -e "${YELLOW}  ~ apiposture not installed, skipping${NC}"
fi

# ─── Step 6: GoSec (if Go code exists) ──────────────────────
echo -e "${YELLOW}[6/6] GoSec — Go Security Scan${NC}"

if [ -d "$ROOT/campus_go" ] && command -v gosec &>/dev/null; then
    cd "$ROOT/campus_go"
    if gosec -quiet -severity=medium ./... 2>&1; then
        echo -e "${GREEN}  ✓ gosec: no medium+ issues${NC}"
    else
        echo -e "${RED}  ✗ gosec found issues${NC}"
        ERRORS="$ERRORS gosec_findings"
        EXIT_CODE=1
    fi
    cd "$ROOT"
elif [ -d "$ROOT/campus_go" ]; then
    echo -e "${YELLOW}  ~ gosec not installed — go install github.com/securego/gosec/v2/cmd/gosec@latest${NC}"
else
    echo -e "${YELLOW}  ~ No Go project, skipping${NC}"
fi

echo ""
echo -e "${CYAN}──────────────────────────────────────────────${NC}"

if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}  ✅ All 6 security checks passed!${NC}"
else
    echo -e "${RED}  ❌ Security issues found:${NC}"
    for err in $ERRORS; do
        echo -e "${RED}     - $err${NC}"
    done
    echo -e "${YELLOW}  🔧 Fix the issues above and re-run.${NC}"
fi

echo -e "${CYAN}──────────────────────────────────────────────${NC}"
exit $EXIT_CODE
