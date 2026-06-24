"""Physical Gate: Block rm -rf on project directories."""
import sys
import os

PROTECTED = [".claude", "campus_app", "campus_go", "_research", "server", "pete_brain"]

cmd = os.environ.get("CLAUDE_TOOL_COMMAND", "")
for p in PROTECTED:
    if p in cmd:
        print(f"⛔ 被拦截: rm -rf 含受保护路径 '{p}'。命令: {cmd}")
        print("此操作不可逆。需手动确认后绕过。")
        sys.exit(1)
sys.exit(0)
