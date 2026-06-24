"""Physical Gate: blocks destructive Bash commands. No 'if' filter — all logic internal.

模式19 铁律: Every block MUST have a recovery path.
  GATE_OVERRIDE=1 bypasses ALL gates. Only use in verified emergencies.
  Must be explicitly set PER COMMAND — no persistent override."""
import sys, json, os, subprocess

try:
    data = json.load(sys.stdin)
except:
    sys.exit(0)

cmd = data.get("tool_input", {}).get("command", "")
override = os.environ.get("GATE_OVERRIDE", "") == "1"

if override:
    print("GATE_OVERRIDE=1 — all gates bypassed. Proceed with caution.")
    sys.exit(0)

# --- Force push guard ---
if "git push" in cmd and ("--force" in cmd or " -f" in cmd):
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": "BLOCKED: git push --force. To override: set GATE_OVERRIDE=1 for this command only."}}))
    sys.exit(0)

# --- Git checkout guard ---
if "git checkout -- " in cmd:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": "BLOCKED: git checkout -- <file>. Use 'just restore <file>' (shows diff first) or set GATE_OVERRIDE=1."}}))
    sys.exit(0)

# --- Build guard ---
if any(s in cmd for s in ["just build", "pete.py build", "flutter build"]):
    result = subprocess.run(["python", "f:/ClaudeFiles/build_check.py"], capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": f"build_check failed (exit {result.returncode}). Fix issues or set GATE_OVERRIDE=1 for emergency bypass."}}))
        sys.exit(0)

# --- RM guard ---
if "rm -rf" in cmd or "rm -r" in cmd:
    PROTECTED = [".claude", "campus_app", "campus_go", "_research", "server", "pete_brain"]
    for p in PROTECTED:
        if p in cmd:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": f"BLOCKED: rm contains protected path '{p}'. Use 'just nuke {p}' (requires confirmation) or GATE_OVERRIDE=1."}}))
            sys.exit(0)

# All checks passed — allow
sys.exit(0)
