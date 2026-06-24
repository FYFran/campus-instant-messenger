"""Physical Gate: blocks destructive Bash commands. No 'if' filter — all logic internal."""
import sys, json, subprocess

try:
    data = json.load(sys.stdin)
except:
    sys.exit(0)

cmd = data.get("tool_input", {}).get("command", "")

# --- Force push guard ---
if "git push" in cmd and ("--force" in cmd or " -f" in cmd):
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": "BLOCKED: git push --force is forbidden by Physical Gate."}}))
    sys.exit(0)

# --- Git checkout guard ---
if "git checkout -- " in cmd:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": "BLOCKED: git checkout -- <file> is forbidden. Use just restore <file> instead."}}))
    sys.exit(0)

# --- Build guard ---
if any(s in cmd for s in ["just build", "pete.py build", "flutter build"]):
    result = subprocess.run(["python", "f:/ClaudeFiles/build_check.py"], capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": f"build_check failed (exit {result.returncode}). Fix issues first."}}))
        sys.exit(0)

# --- RM guard ---
if "rm -rf" in cmd or "rm -r" in cmd:
    PROTECTED = [".claude", "campus_app", "campus_go", "_research", "server", "pete_brain"]
    for p in PROTECTED:
        if p in cmd:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": f"BLOCKED: rm contains protected path '{p}'. Use just nuke <target> instead."}}))
            sys.exit(0)

# All checks passed — allow
sys.exit(0)
