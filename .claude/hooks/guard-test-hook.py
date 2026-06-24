"""Diagnostic PreToolUse Hook: Blocks 'echo testblock' to verify hook engine."""
import sys, json

print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": "HOOK WORKS: echo testblock blocked by PreToolUse guard."
    }
}))
