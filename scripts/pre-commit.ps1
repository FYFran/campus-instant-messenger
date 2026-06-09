# Pre-commit hook for Windows (PowerShell)
# Install: copy scripts\pre-commit.ps1 .git\hooks\pre-commit (as .ps1)
# Or run manually before commit:
#   powershell -File scripts\pre-commit.ps1
# Bypass: $env:SKIP_CHECKS=1; git commit

$ProjectDir = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$GitleaksConfig = Join-Path $ProjectDir ".gitleaks.toml"

if ($env:SKIP_CHECKS -eq "1") {
    Write-Host "SKIP_CHECKS=1 - bypassing all pre-commit checks"
    exit 0
}

$HadError = $false

# --- Gitleaks ---
if ($env:SKIP_GITLEAKS -ne "1") {
    $GitleaksBin = Join-Path $ProjectDir ".gitleaks\gitleaks.exe"
    if (Test-Path $GitleaksBin) {
        Write-Host "[gitleaks] Scanning staged changes for secrets..."
        $result = & $GitleaksBin protect --config="$GitleaksConfig" --staged 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[gitleaks] OK"
        } else {
            Write-Host "[gitleaks] FAIL - secrets detected. Remove them or use `$env:SKIP_GITLEAKS=1"
            $HadError = $true
        }
    } else {
        Write-Host "[gitleaks] WARNING - not found at $GitleaksBin"
        Write-Host "  Download: https://github.com/gitleaks/gitleaks/releases"
    }
} else {
    Write-Host "[gitleaks] skipped (SKIP_GITLEAKS=1)"
}

# --- Semgrep ---
if ($env:SKIP_SEMGREP -ne "1") {
    $semgrepCmd = Get-Command "semgrep" -ErrorAction SilentlyContinue
    if ($semgrepCmd) {
        Write-Host "[semgrep] Scanning staged Python/Go files..."
        $staged = git diff --cached --name-only --diff-filter=ACM | Select-String '\.(py|go)$'
        if ($staged) {
            $files = ($staged.Line -join ' ')
            $result = semgrep --config="$ProjectDir\.semgrep.yml" --error --no-rewrite-rule-ids $files 2>&1
            if ($LASTEXITCODE -eq 0) {
                Write-Host "[semgrep] OK"
            } else {
                Write-Host "[semgrep] FAIL - issues found. Fix or use `$env:SKIP_SEMGREP=1"
                $HadError = $true
            }
        } else {
            Write-Host "[semgrep] No staged Python/Go files to scan."
        }
    } else {
        Write-Host "[semgrep] WARNING - not installed (install: pip install semgrep)"
    }
} else {
    Write-Host "[semgrep] skipped (SKIP_SEMGREP=1)"
}

if ($HadError) {
    Write-Host ""
    Write-Host "COMMIT BLOCKED by pre-commit checks."
    Write-Host "Bypass: `$env:SKIP_CHECKS=1; git commit"
    exit 1
}

Write-Host "[OK] Pre-commit checks passed."
