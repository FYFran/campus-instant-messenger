"""PostToolUse Hook: Auto-run checks after code changes + quality reminders."""
import sys, os, io, subprocess
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

tool_name = os.environ.get("CLAUDE_TOOL_NAME", "")
file_path = os.environ.get("CLAUDE_TOOL_FILE_PATH", "")

CODE_EXTENSIONS = (".py", ".dart", ".go", ".js", ".ts", ".html", ".css", ".sql")

def should_check():
    """Only trigger for actual code edits."""
    if tool_name in ("Edit", "Write"):
        return file_path.endswith(CODE_EXTENSIONS)
    return False

if should_check():
    checks = []

    # Run campus_check for Python/Dart/Go files
    if file_path.endswith((".py", ".dart", ".go")):
        result = subprocess.run(
            ["python", "f:/ClaudeFiles/campus_check.py"],
            capture_output=True, text=True, timeout=60, encoding='utf-8', errors='replace'
        )
        if result.returncode != 0:
            checks.append(f"FAIL campus_check:\n{result.stdout[-300:]}")
        else:
            checks.append("OK campus_check")

    # Run flutter analyze for Dart files
    if file_path.endswith(".dart"):
        result = subprocess.run(
            ["flutter", "analyze"],
            capture_output=True, text=True, timeout=60, encoding='utf-8', errors='replace',
            cwd="f:/ClaudeFiles"
        )
        if result.returncode != 0:
            checks.append(f"❌ flutter analyze 发现问题:\n{result.stdout[-300:]}")
        else:
            checks.append("✅ flutter analyze 通过")

    # Quality reminder: reference the 10-point checklist
    checklist_path = "f:/ClaudeFiles/CODE_REVIEW_CHECKLIST.md"
    if os.path.exists(checklist_path):
        checks.append(f"📋 记得过10点清单: {checklist_path}")
        checks.append("   重点: 无硬编码密钥 | 输入验证 | AuthN/AuthZ | 错误处理 | 无slopsquatting")

    # Auto-write to event log (改完即记 — no reminder, direct execution)
    import subprocess as sp
    import hashlib
    log_script = "f:/ClaudeFiles/.claude/pete-eventlog.py"
    log_domain = "lesson"
    log_tags = "auto-check"
    log_outcome = "pass"
    log_desc = f"Modified {os.path.basename(file_path)} via {tool_name}"
    action_hash = hashlib.sha256(f"{tool_name}:{file_path}".encode()).hexdigest()[:12]

    if any("FAIL" in str(c) or "发现问题" in str(c) for c in checks):
        log_domain = "bug"
        log_tags = "auto-check,failed"
        log_outcome = "fail"
        log_desc = f"FAIL checks after {tool_name} on {os.path.basename(file_path)}"

    try:
        sp.run(
            ["python", log_script, "log", log_domain, log_desc,
             f"--tags={log_tags}", f"--outcome={log_outcome}",
             f"--hash={action_hash}"],
            timeout=10, capture_output=True
        )
    except Exception:
        pass  # Event log is best-effort, never blocks

    if checks:
        print("🔍 自动检查结果:")
        for c in checks:
            print(f"  {c}")
