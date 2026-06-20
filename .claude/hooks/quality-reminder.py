"""UserPromptSubmit Hook: Lightweight code quality reminder for code tasks."""
import os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

prompt = os.environ.get("CLAUDE_USER_PROMPT", "").lower()

# Only trigger for code-related tasks
CODE_KEYWORDS = [
    "改", "修", "fix", "写", "实现", "加", "删", "重构",
    "create", "add", "implement", "refactor", "change", "update",
    "build", "deploy", "migrate", "test"
]

def is_code_task():
    return any(kw in prompt for kw in CODE_KEYWORDS)

if is_code_task():
    checklist_path = "f:/ClaudeFiles/CODE_REVIEW_CHECKLIST.md"
    spec_template = "f:/ClaudeFiles/spec-template.md"

    lines = []
    lines.append("⚡ 代码任务检测")
    lines.append("  规则: Spec先于代码 | AI输出=Draft Zero | 小块迭代 | Commit频繁")

    if "重构" in prompt or "refactor" in prompt or "新" in prompt or "create" in prompt:
        lines.append(f"  📋 多文件改动→先写 spec: {spec_template}")

    lines.append(f"  ✔️ 完成后过10点清单: {checklist_path}")

    print("\n".join(lines))
