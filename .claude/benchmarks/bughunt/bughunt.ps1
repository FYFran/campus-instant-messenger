# BugHuntBench CLI — PowerShell wrapper
# Usage: .\bughunt.ps1 <command> [options]
#
# Commands:
#   run     Run benchmark (generate prompts + score)
#   list    List all available bugs
#   score   Score agent outputs against ground truth
#   gate    Run CI gate check on latest results
#   summary Show latest benchmark summary
#   clean   Clean temp files
#   workflow Run full workflow (requires Claude Code Workflow tool)

param(
    [Parameter(Position=0)]
    [ValidateSet('run', 'list', 'score', 'gate', 'summary', 'clean', 'workflow', 'help')]
    [string]$Command = 'help',

    [Parameter(ValueFromRemainingArguments=$true)]
    [string[]]$Remaining
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonCmd = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $PythonCmd) { $PythonCmd = (Get-Command python3 -ErrorAction SilentlyContinue).Source }
if (-not $PythonCmd) { Write-Error "Python not found"; exit 1 }

function Invoke-Python {
    param([string]$Script, [string]$Args = '')
    $cmd = "cd '$ScriptDir'; & '$PythonCmd' $Script $Args"
    Invoke-Expression $cmd
}

switch ($Command) {
    'run' {
        $bugArg = if ($Remaining) { $Remaining -join ' ' } else { '--bugs all --mode quick' }
        Invoke-Python 'bughunt_run.py' $bugArg
    }

    'list' {
        Invoke-Python 'bughunt_ci.py' '--list'
    }

    'score' {
        $agentFile = if ($Remaining) { $Remaining[0] } else { '.agent_outputs.json' }
        if (-not (Test-Path "$ScriptDir/$agentFile")) {
            Write-Error "Agent outputs file not found: $agentFile"
            Write-Host "First run: .\bughunt.ps1 run --prompts-only"
            Write-Host "Then feed agent outputs back: .\bughunt.ps1 score <outputs.json>"
            exit 1
        }
        Invoke-Python 'bughunt_run.py' "--agent-outputs $agentFile --mode quick"
    }

    'gate' {
        $mode = if ($Remaining) { $Remaining[0] } else { 'quick' }
        Invoke-Python 'bughunt_ci.py' "--gate-only --mode $mode"
    }

    'summary' {
        Invoke-Python 'bughunt_ci.py' '--summary'
    }

    'clean' {
        Remove-Item "$ScriptDir\.temp_*" -Force -ErrorAction SilentlyContinue
        Remove-Item "$ScriptDir\.agent_*" -Force -ErrorAction SilentlyContinue
        Remove-Item "$ScriptDir\.judge_*" -Force -ErrorAction SilentlyContinue
        Write-Host "Cleaned temp files."
    }

    'workflow' {
        Write-Host "BugHuntBench Workflow Mode"
        Write-Host "=========================="
        Write-Host ""
        Write-Host "This mode uses Claude Code's Workflow tool to:"
        Write-Host "  1. Fan out N parallel investigation agents (worktree isolated)"
        Write-Host "  2. Auto-score all reports (L1 rules + L2 LLM judge)"
        Write-Host "  3. L3 cross-model spot-check"
        Write-Host "  4. Generate report + update results.tsv"
        Write-Host ""
        Write-Host "To run, use Claude Code:"
        Write-Host "  /workflow bughunt-benchmark"
        Write-Host ""
        Write-Host "Or directly:"
        Write-Host "  Workflow({scriptPath: '$ScriptDir\bughunt_workflow.js'})"
        Write-Host ""
        Write-Host "For a lighter run (no workflow, just prompts):"
        Write-Host "  .\bughunt.ps1 run"
    }

    'help' {
        Write-Host @"
BugHuntBench CLI v2.0
=====================

Commands:
  run [--bugs B01,B02] [--mode quick|full|verify]
      Generate investigation prompts and/or run benchmark

  list
      List all available bugs

  score <agent_outputs.json>
      Score agent outputs against ground truth

  gate [quick|full|verify]
      Run CI gate check on latest results

  summary
      Show latest benchmark summary

  workflow
      Run full automated workflow (Claude Code Workflow tool)

  clean
      Remove temp files

  help
      Show this help

Examples:
  .\bughunt.ps1 list
  .\bughunt.ps1 run --bugs B01,B02,B03
  .\bughunt.ps1 score agent_outputs.json
  .\bughunt.ps1 gate full
  .\bughunt.ps1 workflow
"@
    }
}
