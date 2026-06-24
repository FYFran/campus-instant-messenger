"""Physical Gate: Warn when editing production deployment files."""
import sys, os

file_path = os.environ.get("CLAUDE_TOOL_FILE_PATH", "")
if not file_path:
    sys.exit(0)

if "main.py" in file_path and "ClaudeFiles" not in file_path:
    print(f"⚠️  生产文件警告: {file_path} 是部署目标文件。通过 deploy.py 部署。", file=sys.stderr)
elif "/app/static/" in file_path:
    print(f"⚠️  服务器静态文件: {file_path}。改完立刻用 SCP 部署并验证。", file=sys.stderr)

sys.exit(0)  # Warning only, don't block
