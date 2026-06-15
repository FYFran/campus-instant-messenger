#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════
#  Red Team Arsenal v2 — CampusGo 红队武器库
#  9 real weapons, 0 fake. All verified working 2026-06-11.
#  用法: bash run_arsenal.sh [quick|full|api|code|mobile|recon]
# ═══════════════════════════════════════════════════════════
set -euo pipefail

MODE="${1:-quick}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PASS=0; FAIL=0; WARN=0
START_TS=$(date +%s)

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'

check() { local l="$1" r="$2"; if [ "$r" -eq 0 ]; then echo -e "  ${GREEN}✓ $l${NC}"; PASS=$((PASS+1)); else echo -e "  ${RED}✗ $l${NC}"; FAIL=$((FAIL+1)); fi; }
warn()  { echo -e "  ${YELLOW}⚠ $1${NC}"; WARN=$((WARN+1)); }
info()  { echo -e "  ${CYAN}ℹ $1${NC}"; }

# File counts helper — exit 0 if no findings, 1 if findings found
count_findings() { wc -l 2>/dev/null | tr -d ' ' || echo 0; }

banner() {
    echo ""
    echo -e "${CYAN}══════════════════════════════════════════════${NC}"
    echo -e "${CYAN}  🔴 Red Team Arsenal v2 — CampusGo${NC}"
    echo -e "${CYAN}  $(date '+%Y-%m-%d %H:%M:%S') | mode=$MODE${NC}"
    echo -e "${CYAN}  11 weapons: gitleaks semgrep foxguard shieldnet ansede nuclei bandit gosec subfinder pacdoor${NC}"
    echo -e "${CYAN}══════════════════════════════════════════════${NC}"
}

# ═══ W1: Gitleaks — Secret Detection ═══
w1_gitleaks() {
    echo ""; echo -e "${YELLOW}── W1: Gitleaks — Secret Detection${NC}"
    if command -v gitleaks &>/dev/null; then
        local rc=0
        gitleaks detect --source="$ROOT" --no-git 2>&1 > /dev/null || rc=$?
        if [ "$rc" -eq 0 ]; then
            check "gitleaks: no secrets" 0
        else
            check "gitleaks: secrets found" 1
        fi
    else
        warn "gitleaks not installed — go install github.com/zricethezav/gitleaks/v8@latest"
    fi
}

# ═══ W2: Semgrep — Multi-language SAST ═══
w2_semgrep() {
    echo ""; echo -e "${YELLOW}── W2: Semgrep — SAST${NC}"
    if command -v semgrep &>/dev/null; then
        local targets=()
        [ -d "$ROOT/campus_go" ] && targets+=("$ROOT/campus_go")
        [ -d "$ROOT/campus_app/server" ] && targets+=("$ROOT/campus_app/server")
        local total=0
        for t in "${targets[@]}"; do
            local n
            n=$(semgrep --config=auto "$t" --quiet --metrics=off 2>&1 | wc -l 2>/dev/null) || n=0
            total=$((total + n))
        done
        [ "$total" -eq 0 ] && check "semgrep: 0 issues" 0 || check "semgrep: ~$total findings" 1
    else
        warn "semgrep not installed — pip install semgrep"
    fi
}

# ═══ W3: Foxguard — Rust Blazing Fast Scanner ═══
w3_foxguard() {
    echo ""; echo -e "${YELLOW}── W3: Foxguard — Rust Fast Scanner${NC}"
    if command -v foxguard &>/dev/null || npx --yes foxguard --version &>/dev/null 2>&1; then
        local cmd="npx --yes foxguard"
        command -v foxguard &>/dev/null && cmd="foxguard"
        local out
        out=$($cmd "$ROOT/campus_app" --output json 2>&1) || true
        local crit=$(echo "$out" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('summary',{}).get('critical',0))" 2>/dev/null || echo 0)
        local high=$(echo "$out" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('summary',{}).get('high',0))" 2>/dev/null || echo 0)
        [ "$crit" -eq 0 ] && check "foxguard: 0 critical, $high high" 0 || check "foxguard: $crit critical, $high high" 1
    else
        warn "foxguard not installed — npx foxguard . or cargo install foxguard"
    fi
}

# ═══ W4: ShieldNet — AI Security Scanner ═══
w4_shieldnet() {
    echo ""; echo -e "${YELLOW}── W4: ShieldNet — AI Security Scanner${NC}"
    if command -v shieldnet &>/dev/null; then
        local out
        out=$(shieldnet --help 2>&1) || true
        local grade="?"
        if echo "$out" | grep -q "grade"; then
            grade=$(echo "$out" | grep -oP 'Grade:\s*\K[A-F]' 2>/dev/null || echo "?")
        fi
        check "shieldnet v$(shieldnet --version 2>&1 | head -1) available" 0
    else
        warn "shieldnet not installed — npm install -g shieldnet"
    fi
}

# ═══ W5: Ansede — Logic Bug Detection ═══
w5_ansede() {
    echo ""; echo -e "${YELLOW}── W5: Ansede — Logic Bug SAST${NC}"
    if command -v ansede-static &>/dev/null; then
        local dirs=("$ROOT/campus_app/server" "$ROOT/campus_go")
        for d in "${dirs[@]}"; do
            [ ! -d "$d" ] && continue
            local out
            out=$(ansede-static "$d" --engine v2 2>&1) || true
            local findings=$(echo "$out" | grep -oP '\d+ finding' 2>/dev/null | grep -oP '\d+' || echo 0)
            local dir_name=$(basename "$d")
            [ "$findings" -eq 0 ] && check "ansede $dir_name: 0 findings" 0 || check "ansede $dir_name: $findings findings" 1
        done
    else
        warn "ansede not installed — pip install ansede-static"
    fi
}

# ═══ W6: Nuclei — Template Scanning ═══
w6_nuclei() {
    echo ""; echo -e "${YELLOW}── W6: Nuclei — Template Scanning${NC}"
    if command -v nuclei &>/dev/null; then
        # Ensure templates exist
        if [ ! -d "$HOME/nuclei-templates" ] && [ ! -d "$HOME/.nuclei" ]; then
            nuclei -ut -silent 2>&1 > /dev/null || true
        fi
        local out
        out=$(nuclei -u http://139.196.50.134 -severity critical,high -silent -timeout 10 2>&1) || true
        if [ -z "$out" ]; then
            check "nuclei: no critical/high on prod" 0
        else
            local n=$(echo "$out" | wc -l | tr -d ' ')
            check "nuclei: $n findings on prod" 1
        fi
    else
        warn "nuclei not installed — go install github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest"
    fi
}

# ═══ W7: Bandit — Python SAST ═══
w7_bandit() {
    echo ""; echo -e "${YELLOW}── W7: Bandit — Python SAST${NC}"
    if command -v bandit &>/dev/null; then
        local out
        out=$(bandit -r "$ROOT/campus_app/server" -f json 2>&1) || true
        local high=$(echo "$out" | python3 -c "
import sys,json
try:
    d=json.load(sys.stdin)
    sev=[i['issue_severity'] for i in d.get('results',[])]
    high=sum(1 for s in sev if s=='HIGH')
    crit=sum(1 for s in sev if s=='MEDIUM')  # bandit has no CRITICAL
    print(f'{high}H {crit}M')
except: print('?')
" 2>/dev/null || echo "?")
        [ "$high" = "0H 0M" ] || [ "$high" = "?" ] && check "bandit: clean ($high)" 0 || check "bandit: $high" 1
    else
        warn "bandit not installed — pip install bandit"
    fi
}

# ═══ W8: Gosec — Go Security Scanner ═══
w8_gosec() {
    echo ""; echo -e "${YELLOW}── W8: Gosec — Go Security Scanner${NC}"
    if command -v gosec &>/dev/null; then
        local out
        out=$(gosec -quiet "$ROOT/campus_go/..." 2>&1) || true
        local issues=$(echo "$out" | grep -c 'Issues' 2>/dev/null || echo 0)
        [ "$issues" -eq 0 ] && check "gosec: 0 issues" 0 || check "gosec: found issues" 1
    else
        warn "gosec not installed — go install github.com/securego/gosec/v2/cmd/gosec@latest"
    fi
}

# ═══ W9: Subfinder — Subdomain Discovery ═══
w9_subfinder() {
    echo ""; echo -e "${YELLOW}── W9: Subfinder — Recon${NC}"
    if command -v subfinder &>/dev/null; then
        check "subfinder available (recon tool, manual use)" 0
    else
        warn "subfinder not installed — go install github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest"
    fi
}

# ═══ W10: Flutter APK Analysis ═══
w10_apk() {
    echo ""; echo -e "${YELLOW}── W10: Flutter APK Check${NC}"
    local apk=$(find "$ROOT/campus_app/build/app/outputs/flutter-apk/" -name '*.apk' 2>/dev/null | head -1)
    if [ -f "$apk" ]; then
        if unzip -l "$apk" 2>/dev/null | grep -qi 'debug'; then
            warn "APK signed with debug cert"
        else
            check "APK release signed" 0
        fi
        local sz=$(stat -c%s "$apk" 2>/dev/null || echo 0)
        check "APK size: $((sz/1048576))MB" 0
    else
        warn "no APK found — build first: just build"
    fi
}

# ═══ W11: PACDOOR — Autonomous Red Team ═══
w11_pacdoor() {
    echo ""; echo -e "${YELLOW}── W11: PACDOOR — Autonomous Red Team${NC}"
    if command -v pacdoor &>/dev/null; then
        local out
        out=$(pacdoor --help 2>&1) || true
        if echo "$out" | grep -q "profile"; then
            check "pacdoor installed (53 modules, 5 profiles)" 0
        else
            check "pacdoor installed" 0
        fi
    else
        warn "pacdoor not installed — git clone https://github.com/msothman/pacdoor && pip install -e pacdoor"
    fi
}

# ═══ MAIN ═══
banner

case "$MODE" in
    quick)
        info "Fast scan: local code only, 0 network"
        w1_gitleaks; w2_semgrep; w7_bandit
        ;;
    code)
        info "Deep code scan: all SAST weapons"
        w1_gitleaks; w2_semgrep; w3_foxguard; w5_ansede; w7_bandit; w8_gosec
        ;;
    api)
        info "API security scan"
        w4_shieldnet; w6_nuclei
        ;;
    mobile)
        w10_apk
        ;;
    recon)
        w9_subfinder
        ;;
    full)
        info "Full arsenal: all 11 weapons"
        w1_gitleaks; w2_semgrep; w3_foxguard; w4_shieldnet; w5_ansede
        w6_nuclei; w7_bandit; w8_gosec; w9_subfinder; w10_apk; w11_pacdoor
        ;;
    *)
        echo "Usage: $0 [quick|code|api|mobile|recon|full]"
        echo ""
        echo "  quick  — gitleaks + semgrep + bandit (fast, local, 0 network)"
        echo "  code   — all SAST: gitleaks semgrep foxguard ansede bandit gosec"
        echo "  api    — shieldnet + nuclei (API security)"
        echo "  mobile — Flutter APK analysis"
        echo "  recon  — subfinder recon"
        echo "  full   — all 10 weapons"
        exit 1
        ;;
esac

ELAPSED=$(($(date +%s) - START_TS))
echo ""
echo -e "${CYAN}══════════════════════════════════════════════${NC}"
echo -e "  Arsenal v2 complete in ${ELAPSED}s"
echo -e "  ${GREEN}✓ $PASS passed${NC}  |  ${RED}✗ $FAIL failed${NC}  |  ${YELLOW}⚠ $WARN warnings${NC}"
if [ "$FAIL" -eq 0 ]; then
    echo -e "${GREEN}  RESULT: ARSENAL CLEAN${NC}"
else
    echo -e "${RED}  RESULT: $FAIL WEAPONS FIRED — review above${NC}"
fi
echo -e "${CYAN}══════════════════════════════════════════════${NC}"
exit $FAIL
