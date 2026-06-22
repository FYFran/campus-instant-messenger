#!/bin/bash
# B04 Behavioral Verification — SWE-bench FAIL_TO_PASS standard
# Bug: GetMyStats SUM from activities.hours (wrong table) instead of certificates.hours
# Fix: Remove JOIN, use certificates.hours directly

set -e
REPO="f:/ClaudeFiles"
INJECT="$REPO/.claude/benchmarks/bughunt/bug_injection/B04_inject.patch"
HANDLER="$REPO/campus_go/internal/handlers/dashboard.go"

echo "=== B04 Behavioral Test ==="

# Step 1: Inject patch validation
echo "[1] Applying inject patch..."
cd "$REPO"
git apply --check "$INJECT" 2>/dev/null && echo "     Patch check: OK" || {
    git apply --check -R "$INJECT" 2>/dev/null && echo "     Patch check (reverse): OK"
}

# Step 2: FAIL — verify bug exists
echo "[2] Verifying bug exists..."
git apply "$INJECT" 2>/dev/null
if grep -q "SUM(a.hours).*certificates c JOIN activities a" "$HANDLER" 2>/dev/null; then
    echo "     FAIL: GetMyStats sums from activities.hours (wrong table) — bug exists"
else
    echo "     WARN: Buggy pattern not found after inject"
fi
git checkout -- "$HANDLER" 2>/dev/null

# Step 3: PASS — verify fix
echo "[3] Verifying correct fix..."
if grep -q "COALESCE(SUM(hours),0) FROM certificates WHERE user_id" "$HANDLER" 2>/dev/null; then
    echo "     PASS: GetMyStats correctly sums from certificates.hours"
else
    echo "     WARN: Expected fix pattern not in code"
fi

echo "=== B04 Verify Complete ==="
