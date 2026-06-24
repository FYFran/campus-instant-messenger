"""PreToolUse Hook: PROJECTMEM pre-action gate.

Before Edit/Write operations, check the event log for known failure
patterns. If the exact same action was tried before and failed,
block it and show the previous failure reason.

Deterministic — no LLM in the loop. Uses hash of (tool + file + operation).
"""

import sys, os, json, hashlib, io
from pathlib import Path

if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

tool_name = os.environ.get("CLAUDE_TOOL_NAME", "")
file_path = os.environ.get("CLAUDE_TOOL_FILE_PATH", "")

EVENT_LOG = Path("f:/ClaudeFiles/.claude/eventstore/events.jsonl")

# Only gate Edit/Write on code files
CODE_EXTS = (".py", ".dart", ".go", ".js", ".ts", ".html", ".css", ".sql")
if tool_name not in ("Edit", "Write"):
    sys.exit(0)
if not file_path.endswith(CODE_EXTS):
    sys.exit(0)


def read_failures() -> list[dict]:
    """Read all events with outcome=fail or failed/regression tags."""
    if not EVENT_LOG.exists():
        return []
    failures = []
    with open(EVENT_LOG, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            e = json.loads(line)
            outcome = e.get("outcome", "")
            tags = e.get("tags", [])
            if outcome == "fail" or any(t in ["failed", "regression", "reverted"] for t in tags):
                failures.append(e)
    return failures


def compute_action_hash(tool: str, fpath: str) -> str:
    """Hash of (tool, file) — what action is being attempted."""
    raw = f"{tool}:{fpath}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


action_hash = compute_action_hash(tool_name, file_path)
failures = read_failures()

matched = [f for f in failures if f.get("action_hash") == action_hash]

if matched:
    latest = matched[-1]
    reason = latest.get("description", "unknown failure")[:200]
    ts = latest.get("timestamp", "unknown")[:19]
    print(f"GATE BLOCKED: action_hash={action_hash}")
    print(f"  Previous failure [{ts}]: {reason}")
    print(f"  To override: set env GATE_OVERRIDE=1")

    override = os.environ.get("GATE_OVERRIDE", "")
    if override == "1":
        print("  GATE_OVERRIDE=1 set — allowing anyway")
        sys.exit(0)
    sys.exit(1)

sys.exit(0)
