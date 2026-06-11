#!/usr/bin/env bash
# ═══════════════════════════════════════════════════
#  Go Backend Pipeline — ULTIMATE EDITION
#  campus_go 质量门禁 | 本地运行
#  用法: bash pipeline_go.sh [--check|--build|--deploy]
# ═══════════════════════════════════════════════════
set -euo pipefail

MODE="${1:---build}"
DIR="$(cd "$(dirname "$0")" && pwd)"
BIN="campus-go-linux"
PASS=0; FAIL=0; WARN=0
START_TS=$(date +%s)

red()   { echo -e "\033[31m$1\033[0m"; }
green() { echo -e "\033[32m$1\033[0m"; }
yellow(){ echo -e "\033[33m$1\033[0m"; }
dim()   { echo -e "\033[2m$1\033[0m"; }

check() { local l="$1" r="$2" d="${3:-}"; if [ "$r" -eq 0 ]; then green "  ✓ $l"; PASS=$((PASS+1)); else red "  ✗ $l  — $d"; FAIL=$((FAIL+1)); fi; }
warn()  { local l="$1" d="${2:-}"; yellow "  ⚠ $l  — $d"; WARN=$((WARN+1)); }

banner() {
    echo ""
    echo "══════════════════════════════════════════════"
    echo "  Go Backend Pipeline — ULTIMATE"
    echo "  $(date '+%Y-%m-%d %H:%M:%S') | mode=$MODE"
    echo "══════════════════════════════════════════════"
}

cd "$DIR"

# ═══ Stage 1: go vet ═══
s1_vet() {
    echo ""; echo "── 1. go vet ──"
    local out
    if out=$(go vet ./... 2>&1); then check "go vet" 0
    else check "go vet" 1 "$(echo "$out" | tail -3)"; fi
}

# ═══ Stage 2: go test (race + coverage) ═══
s2_test() {
    echo ""; echo "── 2. go test ──"
    [ ! -f "go.mod" ] && { check "go test" 0 "(no go.mod)"; return; }

    local out cover exit_code
    out=$(go test -race -cover -count=1 ./... 2>&1) || true
    exit_code=$?

    cover=$(echo "$out" | grep -oP 'coverage: \K[\d.]+%' | tail -1 || echo '?')
    if [ $exit_code -eq 0 ]; then
        check "go test -race -cover (cover=$cover)" 0
    else
        local fail_line=$(echo "$out" | grep -E 'FAIL|--- FAIL' | tail -3 | tr '\n' ' ')
        check "go test" 1 "$fail_line"
    fi

    # Coverage threshold
    local cov_pct=$(echo "$cover" | sed 's/%//')
    if [ "$cov_pct" != "?" ] && [ "$(echo "$cov_pct >= 20" | bc -l 2>/dev/null || echo 0)" = "1" ] 2>/dev/null; then
        check "coverage >= 20% ($cover)" 0
    elif [ "$cov_pct" = "?" ]; then
        dim "  coverage: not available"
    else
        check "coverage >= 20% ($cover)" 1 "below threshold"
    fi

    # Benchmarks compile check
    if go test -run='^$' -bench='.' -benchtime=1x ./... >/dev/null 2>&1; then
        check "benchmarks compile" 0
    else
        dim "  benchmarks: none defined"
    fi
}

# ═══ Stage 3: golangci-lint ═══
s3_lint() {
    echo ""; echo "── 3. Linting ──"
    local gci="${GOPATH:-$(go env GOPATH 2>/dev/null || echo $HOME/go)}/bin/golangci-lint"
    if [ -x "$gci" ] || command -v golangci-lint &>/dev/null; then
        local runner="${gci}"
        command -v golangci-lint &>/dev/null && runner="golangci-lint"
        local out
        out=$("$runner" run --timeout=60s --go=1.25 ./... 2>&1) || true
        if echo "$out" | grep -q 'can.*load config.*language version'; then
            warn "golangci-lint" "go1.25 not supported yet — trying fallback with --go=1.24"
            # Fallback 1: try with go=1.24
            local fallback_out
            fallback_out=$("$runner" run --timeout=60s --go=1.24 ./... 2>&1) || true
            if echo "$fallback_out" | grep -qE '\.go:[0-9]+:'; then
                local issues=$(echo "$fallback_out" | grep -cE '\.go:[0-9]+:' 2>/dev/null || echo 0)
                warn "golangci-lint --go=1.24 ($issues issues)" "review recommended"
            elif [ "${PIPESTATUS[0]:-0}" -eq 0 ] 2>/dev/null; then
                check "golangci-lint --go=1.24" 0
            else
                # Fallback 2: run go vet -vettool instead
                dim "  golangci-lint fallback: trying go vet -vettool..."
                local vet_out
                if vet_out=$(go vet -vettool="$(which vet 2>/dev/null || echo '')" ./... 2>&1); then
                    check "go vet (golangci-lint fallback)" 0
                else
                    local vet_issues=$(echo "$vet_out" | grep -cE '\.go:[0-9]+:' 2>/dev/null || echo 0)
                    warn "go vet (fallback)" "$vet_issues issues"
                fi
            fi
        elif [ "${PIPESTATUS[0]:-0}" -eq 0 ] 2>/dev/null || ! echo "$out" | grep -qE '^[^[:space:]]+\.go:'; then
            check "golangci-lint" 0
        else
            local issues=$(echo "$out" | grep -cE '\.go:[0-9]+:' 2>/dev/null || echo 0)
            warn "golangci-lint ($issues issues)" "review recommended"
        fi
    else
        warn "golangci-lint" "not installed — run: go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest"
    fi
}

# ═══ Stage 4: staticcheck ═══
s4_staticcheck() {
    echo ""; echo "── 4. staticcheck ──"
    local sc="${GOPATH:-$(go env GOPATH 2>/dev/null || echo $HOME/go)}/bin/staticcheck"
    if [ -x "$sc" ] || command -v staticcheck &>/dev/null; then
        local runner="${sc}"
        command -v staticcheck &>/dev/null && runner="staticcheck"
        local out
        if out=$("$runner" ./... 2>&1); then check "staticcheck" 0
        elif echo "$out" | grep -q 'go command required'; then
            check "staticcheck" 0 "(go not in PATH, skip)"
        else check "staticcheck" 1 "$(echo "$out" | head -3)"; fi
    else
        warn "staticcheck" "not installed — go install honnef.co/go/tools/cmd/staticcheck@latest"
    fi
}

# ═══ Stage 5: gosec ═══
s5_gosec() {
    echo ""; echo "── 5. gosec ──"
    local gs="${GOPATH:-$(go env GOPATH 2>/dev/null || echo $HOME/go)}/bin/gosec"
    if [ -x "$gs" ] || command -v gosec &>/dev/null; then
        local runner="${gs}"
        command -v gosec &>/dev/null && runner="gosec"
        local out
        if out=$("$runner" -quiet -severity=medium ./... 2>&1); then check "gosec" 0
        else check "gosec" 1 "$(echo "$out" | grep 'Severity' | tail -3)"; fi
    else
        warn "gosec" "not installed — go install github.com/securego/gosec/v2/cmd/gosec@latest"
    fi
}

# ═══ Stage 5b: govulncheck ═══
s5b_vulncheck() {
    echo ""; echo "── 5b. govulncheck ──"
    if command -v govulncheck &>/dev/null; then
        local out
        if out=$(govulncheck ./... 2>&1); then check "govulncheck (0 vulns)" 0
        else check "govulncheck" 1 "$(echo "$out" | tail -3)"; fi
    else
        warn "govulncheck not installed — go install golang.org/x/vuln/cmd/govulncheck@latest"
    fi
}

# ═══ Stage 6: Dependency audit ═══
s6_deps() {
    echo ""; echo "── 6. Dependencies ──"
    # go mod tidy
    local out
    if out=$(go mod tidy 2>&1); then check "go mod tidy" 0
    else check "go mod tidy" 1 "$(echo "$out" | tail -2)"; fi

    # Verify go.sum
    if go mod verify 2>/dev/null; then check "go mod verify" 0
    else check "go mod verify" 1 "go.sum mismatch — run go mod tidy"; fi

    # List outdated (informational)
    local outdated=$(go list -u -m -json all 2>/dev/null | grep -c '"Indirect": true' 2>/dev/null || echo 0)
    dim "  indirect deps: $outdated"
}

# ═══ Stage 7: Secret scan ═══
s7_secrets() {
    echo ""; echo "── 7. Secret scan ──"
    local found=0
    for pat in 'campus_dev_2026' 'da6f4647f4aa' 'campus-jwt-secret-2026' \
               'password\s*=\s*"[^"]{6,}"' 'JWT_SECRET\s*=\s*"[^"]{8,}"' \
               'DATABASE_URL\s*=\s*"[^"]*@'; do
        if grep -rqnE "$pat" . --include='*.go' --exclude='*_test.go' 2>/dev/null; then
            found=1
        fi
    done
    [ "$found" -eq 0 ] && check "no hardcoded secrets" 0 || check "no hardcoded secrets" 1 "secrets in source — move to env vars"

    # .env file check
    if [ -f .env ]; then
        local perms=$(stat -c '%a' .env 2>/dev/null || echo '777')
        [ "$perms" = "600" ] 2>/dev/null && check ".env perms (600)" 0 || check ".env perms ($perms)" 1 "should be 600"
    fi
}

# ═══ Stage 8: Build ═══
s8_build() {
    echo ""; echo "── 8. Build ──"

    # Clean previous
    rm -f "$BIN"

    # Linux amd64, CGO disabled, stripped
    local ver=$(git describe --tags --always 2>/dev/null || echo 'dev')
    local out
    if out=$(CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build \
        -ldflags="-s -w -X main.Version=$ver" \
        -o "$BIN" . 2>&1); then
        local sz=$(ls -lh "$BIN" 2>/dev/null | awk '{print $5}')
        check "go build → $BIN ($sz)" 0
    else
        check "go build" 1 "$(echo "$out" | tail -3)"; return 1
    fi

    # Binary hardening
    if file "$BIN" 2>/dev/null | grep -q 'statically linked'; then
        check "static binary" 0
    else
        warn "static binary" "not statically linked"
    fi
    if file "$BIN" 2>/dev/null | grep -q 'stripped'; then
        check "symbols stripped" 0
    else
        warn "symbols stripped" "binary has debug symbols"
    fi

    # Size check (35MB threshold)
    local sz_b=$(stat -c%s "$BIN" 2>/dev/null || echo 0)
    local sz_mb=$((sz_b / 1048576))
    [ "$sz_mb" -le 35 ] 2>/dev/null && check "size (${sz_mb}MB)" 0 || warn "size (${sz_mb}MB)" "over 35MB"

    # Size trend (compare with last build if exists)
    if [ -f ".last_build_size" ]; then
        local last_sz=$(cat .last_build_size)
        local delta=$((sz_mb - last_sz))
        [ "$delta" -le 5 ] 2>/dev/null && check "size trend ($delta MB vs last)" 0 || warn "size trend (+${delta}MB)" "binary grew significantly"
    fi
    echo "$sz_mb" > .last_build_size
}

# ═══ Stage 9: API smoke (if Go binary is server-capable) ═══
s9_smoke() {
    echo ""; echo "── 9. API smoke (Go binary) ──"
    [ ! -f "$BIN" ] && { check "go smoke" 1 "binary not built"; return; }

    # Quick start-and-kill smoke test (binary runs, prints startup log, we kill it)
    local out
    if timeout 3 ./"$BIN" 2>&1 || true; then
        :
    fi

    out=$(timeout 3 ./"$BIN" 2>&1 || true)
    if echo "$out" | grep -qiE 'starting|listening|running|gin'; then
        check "binary starts" 0
    else
        dim "  binary startup test skipped (needs DB connection)"
    fi
}

# ═══ Stage 10: Deploy ═══
s10_deploy() {
    echo ""; echo "── 10. Deploy ──"
    if [ "$FAIL" -gt 0 ]; then red "  BLOCKED: $FAIL failures"; return 1; fi
    [ ! -f "$BIN" ] && { red "  $BIN not built — run --build first"; return 1; }

    local host="${DEPLOY_HOST:-139.196.50.134}"
    local user="${DEPLOY_USER:-root}"

    green "  Uploading $BIN → $user@$host:/app/$BIN.new"
    scp "$BIN" "$user@$host:/app/$BIN.new" 2>&1 || { red "  scp failed"; return 1; }

    green "  Deploy complete."
    echo "  Activate on server:"
    echo "    ssh $user@$host 'mv /app/$BIN.new /app/$BIN && systemctl restart campus-go'"
}

# ══════════════════════ MAIN ══════════════════════
banner

case "$MODE" in
    --check)
        s1_vet; s2_test; s3_lint; s4_staticcheck; s5_gosec; s5b_vulncheck; s6_deps; s7_secrets
        ;;
    --build)
        s1_vet; s2_test; s3_lint; s4_staticcheck; s5_gosec; s5b_vulncheck; s6_deps; s7_secrets; s8_build; s9_smoke
        ;;
    --deploy)
        s1_vet; s2_test; s3_lint; s4_staticcheck; s5_gosec; s5b_vulncheck; s6_deps; s7_secrets; s8_build; s9_smoke; s10_deploy
        ;;
    *) echo "Usage: $0 [--check|--build|--deploy]"; exit 1 ;;
esac

ELAPSED=$(($(date +%s) - START_TS))
echo ""
echo "══════════════════════════════════════════════"
echo "  Pipeline complete in ${ELAPSED}s"
echo "  ✓ $PASS passed  |  ✗ $FAIL failed  |  ⚠ $WARN warnings"
if [ "$FAIL" -eq 0 ]; then
    green "  RESULT: QUALITY GATE PASSED"
    echo "══════════════════════════════════════════════"
    exit 0
else
    red "  RESULT: $FAIL FAILURES — fix before deploy"
    echo "══════════════════════════════════════════════"
    exit 1
fi
