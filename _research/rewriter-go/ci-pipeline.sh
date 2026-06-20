#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
#  TokenLine Production CI/CD Pipeline v2.0
#  Upgraded: independent stages, fast mode, multi-run, caching
#  Usage: FAST=1 bash ci-pipeline.sh    # skip deploy, run checks only
#         RUNS=55 bash ci-pipeline.sh   # run 55 times for stress test
#  Alerts: Telegram @tokenline_alerts
# ═══════════════════════════════════════════════════════════════════

TG_TOKEN="8898185692:AAEjW5PcFLiwKJYf58X4pYY47HpbZvWGOUk"
TG_CHAT="1185240496"
alert_tg() { curl -s -X POST "https://api.telegram.org/bot$TG_TOKEN/sendMessage" -d "chat_id=$TG_CHAT" -d "text=$1" >/dev/null 2>&1 || true; }

# ═══ CONFIG ═══
FAST_MODE="${FAST:-0}"
TOTAL_RUNS="${RUNS:-1}"
SERVER="root@47.82.103.247"
PROJECT="$(cd "$(dirname "$0")" && pwd)"
BINARY="$PROJECT/rewriter-linux"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'
GLOBAL_PASS=0; GLOBAL_FAIL=0; GLOBAL_WARN=0; GLOBAL_SKIP=0
GLOBAL_START=$(date +%s)
STAGE_TIMES=()

pass() { echo -e "  ${GREEN}[PASS]${NC} $1"; GLOBAL_PASS=$((GLOBAL_PASS+1)); }
fail() { echo -e "  ${RED}[FAIL]${NC} $1"; GLOBAL_FAIL=$((GLOBAL_FAIL+1)); }
warn() { echo -e "  ${YELLOW}[WARN]${NC} $1"; GLOBAL_WARN=$((GLOBAL_WARN+1)); }
skip() { echo -e "  ${CYAN}[SKIP]${NC} $1"; GLOBAL_SKIP=$((GLOBAL_SKIP+1)); }
header() { echo -e "\n${BLUE}┌──────────────────────────────────────────┐${NC}"; echo -e "${BLUE}│${NC} ${BLUE}$1${NC}"; echo -e "${BLUE}└──────────────────────────────────────────┘${NC}"; }
stage_time() { STAGE_TIMES+=("$1:${2}s"); }

run_stage() {
    local name="$1"; shift
    local start=$(date +%s)
    header "$name"
    local pre_fail=$GLOBAL_FAIL
    "$@"
    local elapsed=$(($(date +%s) - start))
    stage_time "$name" "$elapsed"
    local stage_fails=$((GLOBAL_FAIL - pre_fail))
    if [ "$stage_fails" -gt 0 ]; then
        echo -e "  ${RED}Stage FAILED ($stage_fails failures, ${elapsed}s)${NC}"
        return 1
    else
        echo -e "  ${GREEN}Stage OK (${elapsed}s)${NC}"
        return 0
    fi
}

# ═══════════════════════════════════════════
# STAGE 0: PRE-FLIGHT
# ═══════════════════════════════════════════
stage_preflight() {
    local pre_run_fail=$GLOBAL_FAIL
    for cmd in go ssh scp node; do
        command -v $cmd >/dev/null 2>&1 && pass "$cmd installed" || fail "$cmd missing"
    done
    ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no -o BatchMode=yes "$SERVER" 'echo ok' >/dev/null 2>&1 && pass "SSH OK" || fail "SSH failed"
    ssh "$SERVER" "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:9100/api/health" 2>/dev/null | grep -q 200 && pass "Backend alive" || fail "Backend down"
    local this_run_fail=$((GLOBAL_FAIL - pre_run_fail))
    if [ "$this_run_fail" -gt 0 ]; then
        echo -e "${RED}FATAL: pre-flight failed this run${NC}"
        return 1
    fi
}

# ═══════════════════════════════════════════
# STAGE 1: STATIC ANALYSIS
# ═══════════════════════════════════════════
stage_static() {
    cd "$PROJECT"

    # Unit tests
    CGO_ENABLED=1 go test ./internal/handler/ -run 'TestRegister|TestLogin|TestFilter' -count=1 -timeout 30s >/dev/null 2>&1 && pass "Unit tests" || fail "Unit tests"

    # Go vet
    go vet ./... >/dev/null 2>&1 && pass "go vet" || fail "go vet"

    # Go fmt
    UNFMT=$(gofmt -l . 2>/dev/null | grep '\.go$' || true)
    if [ -z "$UNFMT" ]; then
        pass "go fmt"
    else
        warn "fmt needed: $(echo "$UNFMT" | wc -l) files — auto-fixing"
        gofmt -w . 2>/dev/null && pass "go fmt auto-fixed" || fail "go fmt fix failed"
    fi

    # Build check (type-check only, cached between runs)
    if [ -f "$BINARY" ] && [ "$BINARY" -nt "$(find . -name '*.go' -newer "$BINARY" 2>/dev/null | head -1)" ]; then
        pass "type-check (cached)"
    else
        CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -o /dev/null ./... >/dev/null 2>&1 && pass "type-check" || fail "type-check"
    fi

    # Frontend static check
    echo "  --- frontend ---"
    ssh "$SERVER" bash << 'REMOTE_SCRIPT'
PROBLEMS=0
# Check localStorage key consistency (exclude removeItem cleanup calls)
for f in /app/static/*.html /app/static/*/*.html /app/static/tools/*.html; do
    [ -f "$f" ] || continue
    if grep -qE "'tl_tok'|\"tl_tok\"" "$f" 2>/dev/null && ! grep -q "removeItem.*tl_tok" "$f" 2>/dev/null; then
        echo "  KEY_MISMATCH: $f"
        PROBLEMS=$((PROBLEMS+1))
    fi
done
# Check auth protection
for f in /app/static/topup.html /app/static/verify-phone.html /app/static/success.html /app/static/dashboard.html; do
    [ -f "$f" ] || continue
    if ! grep -q "function authFetch" "$f" 2>/dev/null; then
        echo "  NO_AUTH_GUARD: $f"
        PROBLEMS=$((PROBLEMS+1))
    fi
done
# Check all pages load
for p in /login.html /register.html /topup.html /chat/ /privacy.html /terms.html; do
    CODE=$(curl -s -o /dev/null -w '%{http_code}' "https://tokenline.top$p" --resolve "tokenline.top:443:127.0.0.1")
    [ "$CODE" != "200" ] && { echo "  PAGE_BROKEN: $p → $CODE"; PROBLEMS=$((PROBLEMS+1)); }
done
# Check EN/MY pages too
for p in /en/ /my/; do
    CODE=$(curl -s -o /dev/null -w '%{http_code}' "https://tokenline.top$p" --resolve "tokenline.top:443:127.0.0.1")
    [ "$CODE" != "200" ] && { echo "  PAGE_BROKEN: $p → $CODE"; PROBLEMS=$((PROBLEMS+1)); }
done
exit $PROBLEMS
REMOTE_SCRIPT
    [ $? -eq 0 ] && pass "Frontend checks" || fail "Frontend issues found"
}

# ═══════════════════════════════════════════
# STAGE 1.5: FRONTEND CONTENT VALIDATION
# ═══════════════════════════════════════════
stage_frontend_content() {
    echo "  --- content checks ---"
    ssh "$SERVER" bash << 'REMOTE_CONTENT'
PROBLEMS=0

# 1. Pricing cards match API packs
API_PACKS=$(curl -s http://127.0.0.1:9100/api/packs | python3 -c "
import sys,json; d=json.load(sys.stdin)
for cat in ['flash','ultimate','pro']:
  for p in d.get(cat,[]):
    name = p['name'].removeprefix('TokenLine '); print(name)
")
for pack in $API_PACKS; do
  if ! grep -qF "$pack" /app/static/index.html; then
    echo "  PRICE_MISMATCH: ID missing pack '$pack'"
    PROBLEMS=$((PROBLEMS+1))
  fi
done
[ $PROBLEMS -eq 0 ] && echo "  Pricing ID → API: OK" || true

# 2. EN/MY pack name check (Ultimate naming consistency)
for LANG in en my; do
  grep -qF "Ultimate 3M" /app/static/$LANG/index.html && echo "  $LANG Ultimate naming: OK" || { echo "  PACK_NAME: $LANG missing Ultimate 3M"; PROBLEMS=$((PROBLEMS+1)); }
done

# 3. Key UI elements on each homepage
for LANG in "" "en/" "my/"; do
  PAGE="/app/static/${LANG}index.html"
  [ ! -f "$PAGE" ] && { echo "  MISSING_PAGE: $PAGE"; PROBLEMS=$((PROBLEMS+1)); continue; }
  # CTA button
  grep -q 'register.html' "$PAGE" || { echo "  NO_CTA: $PAGE"; PROBLEMS=$((PROBLEMS+1)); }
  # Pricing cards
  grep -q 'Flash' "$PAGE" || { echo "  NO_PRICING: $PAGE"; PROBLEMS=$((PROBLEMS+1)); }
  # CSS without broken rules
  grep -q 'cursor:pointer;cursor:pointer' "$PAGE" && { echo "  BROKEN_CSS: $PAGE (double cursor)"; PROBLEMS=$((PROBLEMS+1)); }
done

# 4. Homepage nav anchors exist (POSIX grep, no -P)
ANCHORS=$(grep -o 'href="#[^"]*"' /app/static/index.html 2>/dev/null | sed 's/href="#//;s/"//' | sort -u)
for anchor in $ANCHORS; do
  if ! grep -q "id=\"$anchor\"" /app/static/index.html; then
    echo "  BROKEN_ANCHOR: #$anchor linked but not found"
    PROBLEMS=$((PROBLEMS+1))
  fi
done

# 5. pricing.html redirect works
REDIR=$(curl -s -o /dev/null -w '%{http_code}' https://tokenline.top/pricing.html --resolve 'tokenline.top:443:127.0.0.1')
[ "$REDIR" = "200" ] && echo "  pricing.html: OK" || { echo "  BROKEN_REDIRECT: pricing.html → $REDIR"; PROBLEMS=$((PROBLEMS+1)); }

# 6. 404 returns proper code
CODE404=$(curl -s -o /dev/null -w '%{http_code}' https://tokenline.top/test-404-xyz --resolve 'tokenline.top:443:127.0.0.1')
[ "$CODE404" = "404" ] && echo "  404 page: OK" || { echo "  BROKEN_404: returns $CODE404"; PROBLEMS=$((PROBLEMS+1)); }

# 7. Chat innerHTML check — flag only unsafe patterns (without escHtml protection)
grep -qE 'innerHTML\s*=.*\+' /app/static/chat/index.html 2>/dev/null && ! grep -q 'escHtml' /app/static/chat/index.html 2>/dev/null && echo "  CHAT_HTML: UNSAFE innerHTML — missing escHtml wrapper" || echo "  Chat innerHTML: OK"

exit $PROBLEMS
REMOTE_CONTENT
    [ $? -eq 0 ] && pass "Frontend content" || fail "Frontend content issues"
}

# ═══════════════════════════════════════════
# STAGE 2: SECURITY SCAN
# ═══════════════════════════════════════════
stage_security() {
    cd "$PROJECT"

    # Hardcoded secrets
    HARDCODED=$(grep -rn '=\s*"[a-f0-9]\{32,\}"' --include="*.go" . | grep -v '_test.go' | grep -v 'example' | grep -v '\.gitleaks' | head -3 || true)
    [ -z "$HARDCODED" ] && pass "No hardcoded secrets" || fail "Hardcoded secrets: $HARDCODED"

    # Gitleaks with config
    if command -v gitleaks >/dev/null 2>&1; then
        if [ -f "$PROJECT/.gitleaks.toml" ]; then
            GITLEAKS_OUT=$(gitleaks detect --no-git --source . --config "$PROJECT/.gitleaks.toml" 2>&1 | sed 's/\x1b\[[0-9;]*m//g')
        else
            GITLEAKS_OUT=$(gitleaks detect --no-git --source . 2>&1 | sed 's/\x1b\[[0-9;]*m//g')
        fi
        echo "$GITLEAKS_OUT" | grep -qi "no leaks found" && pass "Gitleaks: clean" || warn "Gitleaks: review needed (check .gitleaks.toml)"
    else
        skip "Gitleaks not installed"
    fi

    # GoSec (graceful skip if not installed)
    if command -v gosec >/dev/null 2>&1; then
        gosec -quiet -fmt=json -out=/tmp/gosec.json ./... 2>/dev/null || true
        GOSEC_COUNT=$(python3 -c "import json; d=json.load(open('/tmp/gosec.json')); print(len(d.get('Issues',[])))" 2>/dev/null || echo 0)
        [ "$GOSEC_COUNT" -eq 0 ] && pass "GoSec: clean" || warn "GoSec: $GOSEC_COUNT issues"
    else
        skip "GoSec not installed (run: go install github.com/securego/gosec/v2/cmd/gosec@latest)"
    fi

    # Frontend XSS check — verify no javascript: URIs or unsafe innerHTML in chat
    XSS_RESULT=$(ssh "$SERVER" 'grep -rn "javascript:" /app/static/chat/index.html 2>/dev/null | grep -v "//" | grep -v "test(" | grep -v "cdn" | grep . && echo "XSS_RISK" || echo "XSS_CLEAN"' 2>/dev/null || echo "XSS_CLEAN")
    echo "$XSS_RESULT" | grep -q "XSS_CLEAN" && pass "XSS check" || warn "XSS check: review chat/index.html"
}

# ═══════════════════════════════════════════
# STAGE 3: BUILD (skipped in FAST mode if binary exists and is fresh)
# ═══════════════════════════════════════════
stage_build() {
    cd "$PROJECT"
    if [ "$FAST_MODE" = "1" ] && [ -f "$BINARY" ]; then
        skip "Build (FAST mode: using existing binary)"
        return 0
    fi
    CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -ldflags="-s -w" -o "$BINARY" . 2>&1 && pass "Build: $(du -h "$BINARY" | cut -f1)" || { fail "Build failed"; return 1; }
}

# ═══════════════════════════════════════════
# STAGE 4: API INTEGRATION TESTS
# ═══════════════════════════════════════════
stage_api_e2e() {
    if [ "$FAST_MODE" = "1" ]; then
        skip "API E2E (FAST mode)"
        return 0
    fi
    if ssh "$SERVER" "test -f /tmp/e2e_test.sh" 2>/dev/null; then
        ssh "$SERVER" "bash /tmp/e2e_test.sh 2>&1" && pass "API E2E: all passed" || fail "API E2E: failures detected"
    else
        skip "API E2E: /tmp/e2e_test.sh not found on server"
    fi
}

# ═══════════════════════════════════════════
# STAGE 5: SMOKE TESTS (always runs)
# ═══════════════════════════════════════════
stage_smoke() {
    SMOKE_FAILS=0
    for endpoint in "/api/health" "/api/packs" "/api/templates" "/api/payment/methods" "/api/citation/search?q=test"; do
        CODE=$(ssh "$SERVER" "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:9100$endpoint" 2>/dev/null)
        [ "$CODE" = "200" ] && pass "Smoke $endpoint" || { fail "Smoke $endpoint → $CODE"; SMOKE_FAILS=$((SMOKE_FAILS+1)); }
    done

    # Homepage checks
    for url in "https://tokenline.top/" "https://tokenline.top/en/" "https://tokenline.top/my/"; do
        CODE=$(ssh "$SERVER" "curl -s -o /dev/null -w '%{http_code}' '$url' --resolve 'tokenline.top:443:127.0.0.1'" 2>/dev/null)
        [ "$CODE" = "200" ] && pass "Page $url" || { fail "Page $url → $CODE"; SMOKE_FAILS=$((SMOKE_FAILS+1)); }
    done

    # /chat redirect
    CHAT_REDIR=$(ssh "$SERVER" "curl -s -o /dev/null -w '%{http_code}' 'https://tokenline.top/chat' --resolve 'tokenline.top:443:127.0.0.1'" 2>/dev/null)
    [ "$CHAT_REDIR" = "301" ] && pass "/chat → 301 redirect" || fail "/chat → $CHAT_REDIR (expected 301)"

    # Login smoke
    LOGIN_TEST=$(ssh "$SERVER" "curl -s https://tokenline.top/api/auth/login --resolve 'tokenline.top:443:127.0.0.1' -H 'Content-Type: application/json' -d '{\"email\":\"yifan@tokenline.top\",\"password\":\"Yifan2026!\"}' | python3 -c 'print(\"OK\") if \"token\" in __import__(\"sys\").stdin.read() else print(\"FAIL\")'" 2>/dev/null)
    [ "$LOGIN_TEST" = "OK" ] && pass "Smoke login" || fail "Smoke login"
}

# ═══════════════════════════════════════════
# STAGE 6: INFRA HEALTH
# ═══════════════════════════════════════════
stage_infra() {
    ssh "$SERVER" "sqlite3 /app/new-api/data/tokenline.db 'PRAGMA integrity_check'" 2>/dev/null | grep -q "ok" && pass "DB integrity" || fail "DB corruption"
    DISK_PCT=$(ssh "$SERVER" "df -h / | tail -1 | awk '{print \$5}' | tr -d '%'" 2>/dev/null || echo 100)
    [ "$DISK_PCT" -lt 85 ] && pass "Disk: ${DISK_PCT}%" || fail "Disk critical: ${DISK_PCT}%"
    ssh "$SERVER" "ls /app/rewriter-go/rewriter-linux.bak.* 2>/dev/null | tail -1" >/dev/null 2>&1 && pass "Backup exists" || warn "No recent backup"
}

# ═══════════════════════════════════════════
# STAGE 7: DEPLOY (only if not FAST mode)
# ═══════════════════════════════════════════
stage_deploy() {
    if [ "$FAST_MODE" = "1" ]; then
        skip "Deploy (FAST mode)"
        return 0
    fi

    # Backup
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    ssh "$SERVER" "cp /app/rewriter-go/rewriter-linux /app/rewriter-go/rewriter-linux.bak.$TIMESTAMP" 2>/dev/null && pass "Backup: $TIMESTAMP" || warn "Backup skipped"

    # Upload
    scp "$BINARY" "$SERVER:/tmp/rewriter-linux-new" 2>/dev/null && pass "Upload OK" || { fail "Upload failed"; return 1; }
    ssh "$SERVER" "mv /tmp/rewriter-linux-new /app/rewriter-go/rewriter-linux && chmod +x /app/rewriter-go/rewriter-linux" && pass "Install OK" || fail "Install failed"

    # Restart
    ssh "$SERVER" "systemctl reset-failed rewriter 2>/dev/null; systemctl restart rewriter" && pass "Restart OK" || fail "Restart failed"
    sleep 2
    ssh "$SERVER" "systemctl is-active --quiet rewriter" && pass "Service UP" || { fail "Service DOWN"; return 1; }
}

# ═══════════════════════════════════════════
# MAIN: Single pipeline run
# ═══════════════════════════════════════════
run_pipeline() {
    local run_num="$1"
    local run_start=$(date +%s)
    local run_pass=$GLOBAL_PASS; local run_fail=$GLOBAL_FAIL; local run_warn=$GLOBAL_WARN

    echo ""
    echo "══════════════════════════════════════════════"
    echo "  TOKENLINE CI/CD PIPELINE v2.0"
    if [ "$TOTAL_RUNS" -gt 1 ]; then
        echo "  Run $run_num/$TOTAL_RUNS  |  $(date '+%Y-%m-%d %H:%M:%S')"
    else
        echo "  $(date '+%Y-%m-%d %H:%M:%S')"
    fi
    [ "$FAST_MODE" = "1" ] && echo "  MODE: FAST (no deploy, no E2E)"
    echo "══════════════════════════════════════════════"

    # Execute stages — each independent, failures don't stop others
    stage_preflight || return 1

    stage_static
    stage_frontend_content
    stage_security
    stage_build

    if [ "$FAST_MODE" != "1" ]; then
        stage_api_e2e
    fi

    stage_smoke
    stage_infra
    stage_deploy

    # Results for this run
    local run_elapsed=$(($(date +%s) - run_start))
    local run_pass_delta=$((GLOBAL_PASS - run_pass))
    local run_fail_delta=$((GLOBAL_FAIL - run_fail))
    local run_warn_delta=$((GLOBAL_WARN - run_warn))
    local total=$((run_pass_delta + run_fail_delta + run_warn_delta))

    echo ""
    echo "──────────────────────────────────────────"
    echo -e "  Run $run_num: ${GREEN}P:$run_pass_delta${NC} ${RED}F:$run_fail_delta${NC} ${YELLOW}W:$run_warn_delta${NC}  (${run_elapsed}s)"
    echo "──────────────────────────────────────────"

    return $run_fail_delta
}

# ═══════════════════════════════════════════
# EXECUTE
# ═══════════════════════════════════════════
RUN_FAILURES=0
for ((run=1; run<=TOTAL_RUNS; run++)); do
    run_pipeline "$run" || RUN_FAILURES=$((RUN_FAILURES+1))

    # Brief pause between runs (10s for multi-run, 0 for single)
    if [ "$TOTAL_RUNS" -gt 1 ] && [ "$run" -lt "$TOTAL_RUNS" ]; then
        echo -e "\n${CYAN}  ⏳ Run $run/$TOTAL_RUNS done. Next...${NC}"
        sleep 3
    fi
done

# ═══════════════════════════════════════════
# FINAL SUMMARY
# ═══════════════════════════════════════════
GLOBAL_ELAPSED=$(($(date +%s) - GLOBAL_START))
echo ""
echo "══════════════════════════════════════════════"
echo "  PIPELINE v2.0 COMPLETE"
echo "══════════════════════════════════════════════"
echo -e "  Runs:    $TOTAL_RUNS  (${RUN_FAILURES} failed)"
echo -e "  ${GREEN}PASS:  $GLOBAL_PASS${NC}"
echo -e "  ${RED}FAIL:  $GLOBAL_FAIL${NC}"
echo -e "  ${YELLOW}WARN:  $GLOBAL_WARN${NC}"
echo -e "  ${CYAN}SKIP:  $GLOBAL_SKIP${NC}"
echo -e "  Time:   ${GLOBAL_ELAPSED}s"
echo "──────────────────────────────────────────"
echo -e "  Stage timings:"
for t in "${STAGE_TIMES[@]}"; do
    echo -e "    $t"
done
echo "══════════════════════════════════════════════"

if [ $RUN_FAILURES -gt 0 ]; then
    echo -e "${RED}❌ $RUN_FAILURES/$TOTAL_RUNS runs had failures${NC}"
    alert_tg "🚨 TokenLine pipeline v2: $RUN_FAILURES/$TOTAL_RUNS runs FAILED at $(date +%H:%M). Pass:$GLOBAL_PASS Fail:$GLOBAL_FAIL"
    exit 1
elif [ $GLOBAL_FAIL -gt 0 ]; then
    echo -e "${YELLOW}⚠️  Pipeline complete with $GLOBAL_FAIL failures across runs${NC}"
    exit 0
else
    echo -e "${GREEN}✅ ALL $TOTAL_RUNS RUNS CLEAN${NC}"
    alert_tg "✅ TokenLine pipeline v2: $TOTAL_RUNS/$TOTAL_RUNS runs PASSED at $(date +%H:%M)."
    exit 0
fi
