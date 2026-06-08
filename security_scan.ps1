# security_scan.ps1 - Full security pipeline (Windows-native PowerShell)
# Runs: Gitleaks + Semgrep
#
# Usage:
#   .\security_scan.ps1          # scan everything
#   .\security_scan.ps1 -Diff    # scan staged changes only

param([switch]$Diff)

$ROOT = "F:\ClaudeFiles"
$GITLEAKS_BIN = "$ROOT\.gitleaks\gitleaks.exe"
$GITLEAKS_CONFIG = "$ROOT\.gitleaks.toml"
$SEMGREP_CONFIG = "$ROOT\.semgrep.yml"
$TIMESTAMP = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$EXIT_CODE = 0
$ERRORS = @()

Write-Host ""
Write-Host "Security Scan - $TIMESTAMP" -ForegroundColor Cyan
Write-Host ""

# Step 1: Gitleaks
Write-Host "[1/3] Gitleaks - Secret Detection" -ForegroundColor Yellow

if (-not (Test-Path $GITLEAKS_BIN)) {
    Write-Host "  MISS  Gitleaks not found at $GITLEAKS_BIN" -ForegroundColor Red
    $ERRORS += "gitleaks_missing"
    $EXIT_CODE = 1
} else {
    if ($Diff) {
        & $GITLEAKS_BIN protect --config=$GITLEAKS_CONFIG --staged 2>&1
    } else {
        & $GITLEAKS_BIN detect --config=$GITLEAKS_CONFIG --source=$ROOT --no-git 2>&1
    }
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  PASS  No secrets found" -ForegroundColor Green
    } else {
        Write-Host "  FAIL  Secrets detected above" -ForegroundColor Red
        $ERRORS += "gitleaks_findings"
        $EXIT_CODE = 1
    }
}
Write-Host ""

# Step 2: Semgrep
Write-Host "[2/3] Semgrep - Static Analysis" -ForegroundColor Yellow

$semgrepCmd = Get-Command semgrep -ErrorAction SilentlyContinue
if (-not $semgrepCmd) {
    Write-Host "  MISS  semgrep not found. Install: pip install semgrep" -ForegroundColor Red
    $ERRORS += "semgrep_missing"
    $EXIT_CODE = 1
} else {
    $TARGETS = @()
    if (Test-Path "$ROOT\campus_go") { $TARGETS += "$ROOT\campus_go" }
    if (Test-Path "$ROOT\campus_app\lib") { $TARGETS += "$ROOT\campus_app\lib" }
    $pyFiles = Get-ChildItem "$ROOT\pete_*.pyw","$ROOT\pete_*.py","$ROOT\campus_app\admin\*.py" -ErrorAction SilentlyContinue
    if ($pyFiles) { $TARGETS += "$ROOT" }

    if ($TARGETS.Count -eq 0) {
        Write-Host "  SKIP  No source targets found" -ForegroundColor Yellow
    } else {
        foreach ($target in $TARGETS) {
            Write-Host "  Scanning: $target"
            semgrep --config=$SEMGREP_CONFIG $target --quiet --error --metrics=off 2>&1
            if ($LASTEXITCODE -eq 1) {
                Write-Host "  FAIL  Findings in $target" -ForegroundColor Red
                $ERRORS += "semgrep_findings"
                $EXIT_CODE = 1
            }
        }
        if ($EXIT_CODE -eq 0) {
            Write-Host "  PASS  No issues found" -ForegroundColor Green
        }
    }
}
Write-Host ""

# Summary
if ($EXIT_CODE -eq 0) {
    Write-Host "ALL CHECKS PASSED" -ForegroundColor Green
} else {
    Write-Host "ISSUES FOUND:" -ForegroundColor Red
    foreach ($err in $ERRORS) { Write-Host "  - $err" -ForegroundColor Red }
}

exit $EXIT_CODE
