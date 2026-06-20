"""PostToolUse Hook: Check for new dependencies in known manifest files.
Warns about potential slopsquatting — verify packages exist on official registry.
"""
import os, sys, subprocess, json

tool_name = os.environ.get("CLAUDE_TOOL_NAME", "")
file_path = os.environ.get("CLAUDE_TOOL_FILE_PATH", "")

# Known Go packages that are commonly hallucinated by LLMs
KNOWN_HALLUCINATED_GO = {
    "github.com/gin-contrib/cors": "Exists (ok)",
    "github.com/go-redis/redis": "Exists but use github.com/redis/go-redis/v9 instead",
}

def should_audit():
    if tool_name not in ("Edit", "Write"):
        return False
    return os.path.basename(file_path) in (
        "go.mod", "go.sum", "package.json", "package-lock.json",
        "requirements.txt", "Pipfile", "pyproject.toml",
        "pubspec.yaml", "pubspec.lock"
    )

def check_go_mod(path):
    """Quick check: count new requires added."""
    try:
        result = subprocess.run(
            ["git", "diff", "--", path],
            capture_output=True, text=True, timeout=10,
            cwd=os.path.dirname(path) if os.path.dirname(path) else "."
        )
        diff = result.stdout
        new_deps = [l for l in diff.split("\n") if l.startswith("+") and "/" in l and "require" not in l]
        if new_deps:
            print("📦 检测到Go依赖变更:")
            for dep in new_deps[:5]:
                name = dep.strip("+ \t")
                if name and "// indirect" not in name:
                    print(f"  ⚠️ 验证: {name}")
            print("  💡 确认: 1) 存在于pkg.go.dev 2) 非hallucinated 3) 有活跃维护")
            print("  常见幻觉包: go-redis/v10, gin-cors/v2, jwt-go/v5 — 都不存在!")
    except Exception as e:
        pass

if should_audit():
    print("🔍 依赖审计触发")
    if file_path.endswith(("go.mod", "go.sum")):
        check_go_mod(file_path)
    elif file_path.endswith(("package.json", "package-lock.json")):
        print("📦 NPM依赖变更 — 验证: npm view <pkg> 存在且非typosquatting")
    elif "requirements" in file_path or "Pipfile" in file_path:
        print("📦 Python依赖变更 — 验证: pip index <pkg> 存在且非typosquatting")
    elif "pubspec" in file_path:
        print("📦 Dart依赖变更 — 验证: pub.dev 存在且非typosquatting")
