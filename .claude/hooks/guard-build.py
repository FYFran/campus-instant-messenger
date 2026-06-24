"""PreToolUse Hook: Block build unless build_check passes. Outputs JSON to stdout."""
import sys, json, subprocess

try:
    data = json.load(sys.stdin)
except:
    sys.exit(0)

cmd = data.get("tool_input", {}).get("command", "")
if not any(s in cmd for s in ["just build", "pete.py build", "flutter build"]):
    sys.exit(0)

result = subprocess.run(
    ["python", "f:/ClaudeFiles/build_check.py"],
    capture_output=True, text=True, timeout=120
)
if result.returncode != 0:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": f"build_check.py failed (exit {result.returncode}). Run: python f:/ClaudeFiles/build_check.py first. Output: {result.stdout[-300:]}"
        }
    }))
else:
    sys.exit(0)
