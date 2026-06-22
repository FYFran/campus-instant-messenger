"""Physical Gate: Allow nuke only on whitelisted targets."""
import sys

PROTECTED = [".claude", "campus_app", "campus_go", "_research", "server", "pete_brain", ".git", "memory", "config", "build"]
SAFE_TARGETS = ["__pycache__", ".ruff_cache", "node_modules", "backups", "tmp", "superdesign", ".dart_tool", ".semgrep"]

target = sys.argv[1] if len(sys.argv) > 1 else ""

for p in PROTECTED:
    if p in target:
        print(f"BLOCKED: '{target}' contains protected path '{p}'.", file=sys.stderr)
        print("Nuke denied. Manual review required.", file=sys.stderr)
        sys.exit(1)

for s in SAFE_TARGETS:
    if s in target:
        print(f"SAFE: '{target}'. Proceeding with rm -rf.", file=sys.stderr)
        sys.exit(0)

print(f"UNKNOWN: '{target}' not in safe list. Manual review required.", file=sys.stderr)
sys.exit(1)
