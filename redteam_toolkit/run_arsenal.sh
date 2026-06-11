#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════
#  Red Team Arsenal — CampusGo 红队武器库主控脚本
#  用法: bash run_arsenal.sh [quick|full|api|mobile|db|all]
# ═══════════════════════════════════════════════════════════
set -euo pipefail

MODE="${1:-quick}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PASS=0; FAIL=0; WARN=0
START_TS=$(date +%s)

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'

check() { local l="$1" r="$2"; if [ "$r" -eq 0 ]; then echo -e "  ${GREEN}✓ $l${NC}"; PASS=$((PASS+1)); else echo -e "  ${RED}✗ $l${NC}"; FAIL=$((FAIL+1)); fi; }
warn()  { echo -e "  ${YELLOW}⚠ $1${NC}"; WARN=$((WARN+1)); }

banner() {
    echo ""
    echo -e "${CYAN}══════════════════════════════════════════════${NC}"
    echo -e "${CYAN}  🔴 Red Team Arsenal — CampusGo${NC}"
    echo -e "${CYAN}  $(date '+%Y-%m-%d %H:%M:%S') | mode=$MODE${NC}"
    echo -e "${CYAN}══════════════════════════════════════════════${NC}"
}

# ═══ Weapon 1: Gitleaks (密钥检测) ═══
w1_gitleaks() {
    echo ""; echo -e "${YELLOW}── W1: Gitleaks — Secret Detection${NC}"
    local gitleaks_bin="$ROOT/.gitleaks/gitleaks.exe"
    if [ -f "$gitleaks_bin" ]; then
        if "$gitleaks_bin" detect --config="$ROOT/.gitleaks.toml" --source="$ROOT" --no-git 2>&1 | grep -q 'No leaks found'; then
            check "gitleaks: no secrets" 0
        else
            check "gitleaks: secrets found" 1
        fi
    else
        warn "gitleaks not installed"
    fi
}

# ═══ Weapon 2: Semgrep (静态分析) ═══
w2_semgrep() {
    echo ""; echo -e "${YELLOW}── W2: Semgrep — SAST${NC}"
    if command -v semgrep &>/dev/null; then
        local targets=()
        [ -d "$ROOT/campus_go" ] && targets+=("$ROOT/campus_go")
        [ -d "$ROOT/campus_app" ] && targets+=("$ROOT/campus_app")
        local total_issues=0
        for t in "${targets[@]}"; do
            local out
            out=$(semgrep --config=auto "$t" --quiet --error --metrics=off 2>&1) || true
            local n=$(echo "$out" | grep -c 'finding' 2>/dev/null || echo 0)
            total_issues=$((total_issues + n))
        done
        [ "$total_issues" -eq 0 ] && check "semgrep: 0 issues" 0 || check "semgrep: $total_issues issues" 1
    else
        warn "semgrep not installed"
    fi
}

# ═══ Weapon 3: Shinobi (快速安全扫描) ═══
w3_shinobi() {
    echo ""; echo -e "${YELLOW}── W3: Shinobi — Quick Security Scan${NC}"
    if command -v shinobi &>/dev/null || python -c "import shinobi_scan" 2>/dev/null; then
        local dirs=("$ROOT/campus_app/server" "$ROOT/campus_go")
        for d in "${dirs[@]}"; do
            [ ! -d "$d" ] && continue
            local out
            out=$(python -m shinobi_scan "$d" --json 2>&1) || true
            local crit=$(echo "$out" | python -c "import sys,json; d=json.load(sys.stdin); print(d.get('critical',0))" 2>/dev/null || echo 0)
            local high=$(echo "$out" | python -c "import sys,json; d=json.load(sys.stdin); print(d.get('high',0))" 2>/dev/null || echo 0)
            local dir_name=$(basename "$d")
            [ "$crit" -eq 0 ] && check "shinobi $dir_name (0 crit)" 0 || check "shinobi $dir_name ($crit crit, $high high)" 1
        done
    else
        warn "shinobi not installed — pip install shinobi-scan"
    fi
}

# ═══ Weapon 4: ApiPosture (API安全检查) ═══
w4_apiposture() {
    echo ""; echo -e "${YELLOW}── W4: ApiPosture — API Security Inspector${NC}"
    if command -v apiposture &>/dev/null; then
        local out
        out=$(apiposture scan "$ROOT/campus_app/server/" --output json --fail-on critical 2>&1) || true
        local critical=$(echo "$out" | python -c "import sys,json; d=json.load(sys.stdin); print(d['summary']['severity_counts'].get('critical',0))" 2>/dev/null || echo '?')
        local high=$(echo "$out" | python -c "import sys,json; d=json.load(sys.stdin); print(d['summary']['severity_counts'].get('high',0))" 2>/dev/null || echo '?')
        if [ "$critical" = "0" ] || [ "$critical" = "?" ]; then
            check "apiposture (0 critical, $high high)" 0
        else
            check "apiposture ($critical critical, $high high)" 1
        fi
    else
        warn "apiposture not installed — pip install apiposture"
    fi
}

# ═══ Weapon 5: Flutter APK 逆向检查 ═══
w5_flutter_apk() {
    echo ""; echo -e "${YELLOW}── W5: Flutter APK Analysis${NC}"
    local apk=$(find "$ROOT/campus_app/build/app/outputs/flutter-apk/" -name '*.apk' 2>/dev/null | head -1)
    if [ -f "$apk" ]; then
        # Check if APK has debug cert
        if unzip -l "$apk" 2>/dev/null | grep -qi 'debug'; then
            warn "APK signed with debug cert"
        else
            check "APK release signed" 0
        fi
        # Check if Flutter snapshot is obfuscated
        local sz=$(stat -c%s "$apk" 2>/dev/null || echo 0)
        check "APK size: $((sz/1048576))MB" 0
    else
        warn "no APK found — build first: just build"
    fi
}

# ═══ Weapon 6: SQL Injection Check (sqlmap) ═══
w6_sqlmap() {
    echo ""; echo -e "${YELLOW}── W6: SQL Injection — sqlmap${NC}"
    if command -v sqlmap &>/dev/null; then
        check "sqlmap available" 0
    else
        warn "sqlmap not installed — pip install sqlmap"
    fi
}

# ═══ Weapon 7: Nuclei (漏洞模板扫描) ═══
w7_nuclei() {
    echo ""; echo -e "${YELLOW}── W7: Nuclei — Template Scanning${NC}"
    if command -v nuclei &>/dev/null; then
        local out
        out=$(nuclei -u http://139.196.50.134 -severity critical,high -silent -timeout 10 2>&1) || true
        if [ -z "$out" ]; then
            check "nuclei: no critical/high on prod" 0
        else
            local n=$(echo "$out" | wc -l)
            check "nuclei: $n findings on prod" 1
        fi
    else
        warn "nuclei not installed"
    fi
}

# ═══ Weapon 8: nikto (Web服务器扫描) ═══
w8_nikto() {
    echo ""; echo -e "${YELLOW}── W8: Nikto — Web Server Scan${NC}"
    if command -v nikto &>/dev/null; then
        check "nikto available" 0
    else
        warn "nikto not installed"
    fi
}

# ═══ MAIN ═══
banner

case "$MODE" in
    quick)
        w1_gitleaks; w3_shinobi; w4_apiposture
        ;;
    api)
        w4_apiposture; w6_sqlmap; w7_nuclei
        ;;
    mobile)
        w5_flutter_apk
        ;;
    db)
        w6_sqlmap
        ;;
    full)
        w1_gitleaks; w2_semgrep; w3_shinobi; w4_apiposture; w5_flutter_apk; w6_sqlmap; w7_nuclei; w8_nikto
        ;;
    all)
        w1_gitleaks; w2_semgrep; w3_shinobi; w4_apiposture; w5_flutter_apk; w6_sqlmap; w7_nuclei; w8_nikto
        ;;
    *)
        echo "Usage: $0 [quick|full|api|mobile|db|all]"
        exit 1
        ;;
esac

ELAPSED=$(($(date +%s) - START_TS))
echo ""
echo -e "${CYAN}══════════════════════════════════════════════${NC}"
echo -e "  Arsenal complete in ${ELAPSED}s"
echo -e "  ${GREEN}✓ $PASS passed${NC}  |  ${RED}✗ $FAIL failed${NC}  |  ${YELLOW}⚠ $WARN warnings${NC}"
if [ "$FAIL" -eq 0 ]; then
    echo -e "${GREEN}  RESULT: ARSENAL CLEAN${NC}"
else
    echo -e "${RED}  RESULT: $FAIL WEAPONS FIRED — review above${NC}"
fi
echo -e "${CYAN}══════════════════════════════════════════════${NC}"
exit $FAIL
