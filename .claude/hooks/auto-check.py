"""PostToolUse Hook: Auto-run checks after code changes + quality reminders."""
import sys, os, subprocess

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
            capture_output=True, text=True, timeout=60
        )
        if result.returncode != 0:
            checks.append(f"❌ campus_check 失败:\n{result.stdout[-300:]}")
        else:
            checks.append("✅ campus_check 通过")

    # Run flutter analyze for Dart files
    if file_path.endswith(".dart"):
        result = subprocess.run(
            ["flutter", "analyze"],
            capture_output=True, text=True, timeout=60,
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

    if checks:
        print("🔍 自动检查结果:")
        for c in checks:
            print(f"  {c}")
