"""Peter Replay Test — feed past conversations into the framework.

Extracts user messages from session JSONL files and validates:
  1. Routing accuracy (how many messages match expected routes)
  2. Bug event extraction (how many bugs found)
  3. Daemon activation simulation (bulk feed → verify signals)

Usage:
  python pete-replay-test.py scan                → analyze all sessions
  python pete-replay-test.py extract-bugs        → extract bugs into event log
  python pete-replay-test.py validate-routes     → test router accuracy
"""

import sys, os, json, io, subprocess
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter

if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

SESSIONS_DIR = Path.home() / ".claude/projects/f--ClaudeFiles"
TASK_ROUTER = Path("f:/ClaudeFiles/.claude/hooks/task-router.py")


def find_sessions() -> list[Path]:
    """Find all JSONL session files."""
    sessions = []
    for pattern in ["*.jsonl", "**/*.jsonl"]:
        for f in SESSIONS_DIR.glob(pattern):
            if f.stat().st_size > 1000:  # Skip empty
                sessions.append(f)
    return sorted(set(sessions), key=lambda p: p.stat().st_mtime, reverse=True)


def extract_user_messages(session_path: Path) -> list[str]:
    """Extract all user text messages from a session JSONL."""
    messages = []
    try:
        with open(session_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if data.get("type") != "user":
                    continue
                content_list = data.get("message", {}).get("content", [])
                for c in content_list:
                    if c.get("type") == "text":
                        text = c.get("text", "").strip()
                        if len(text) >= 10:
                            messages.append(text)
    except Exception as e:
        pass
    return messages


def extract_bugs(session_path: Path) -> list[dict]:
    """Extract bug-related events from a session."""
    bugs = []
    try:
        with open(session_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if data.get("type") != "assistant":
                    continue
                content_list = data.get("message", {}).get("content", [])
                text = ""
                for c in content_list:
                    if c.get("type") == "text":
                        text += c.get("text", "")

                # Heuristic: bug-related messages
                bug_keywords = ["bug", "报错", "不工作", "failed", "error", "修", "fix",
                                "broken", "crash", "崩溃", "挂了", "问题", "回滚", "revert"]
                lower = text.lower()
                if any(kw in lower for kw in bug_keywords) and len(text) > 50:
                    bugs.append({
                        "session": session_path.stem[:8],
                        "timestamp": data.get("timestamp", ""),
                        "description": text[:300],
                    })
    except Exception:
        pass
    return bugs


def test_router(user_messages: list[str]) -> dict:
    """Test task-router against user messages and return stats."""
    results = {"total": 0, "routed": 0, "routes": Counter()}

    for msg in user_messages:
        if len(msg.strip()) < 10:
            continue
        results["total"] += 1

        try:
            env = os.environ.copy()
            env["CLAUDE_USER_PROMPT"] = msg
            r = subprocess.run(
                ["python", str(TASK_ROUTER)],
                capture_output=True, text=True, timeout=5,
                env=env, encoding="utf-8", errors="replace"
            )
            output = r.stdout.strip()
            if "@router" in output:
                results["routed"] += 1
                # Extract route name
                route_line = [l for l in output.split("\n") if "@router" in l]
                if route_line:
                    route = route_line[0].split(":")[1].strip()
                    results["routes"][route] += 1
        except Exception:
            pass

    return results


def scan_all():
    """Scan all sessions and report stats."""
    sessions = find_sessions()
    print(f"Found {len(sessions)} session files")

    all_messages = []
    all_bugs = []
    total_size = 0

    for sp in sessions:
        msgs = extract_user_messages(sp)
        all_messages.extend(msgs)
        bugs = extract_bugs(sp)
        all_bugs.extend(bugs)
        total_size += sp.stat().st_size

    print(f"Total size: {total_size / 1024 / 1024:.1f} MB")
    print(f"User messages: {len(all_messages)}")
    print(f"Bug-related messages: {len(all_bugs)}")
    print()

    # Test routing
    print("=== Router Test ===")
    # Sample max 500 messages to avoid timeout
    sample = all_messages[:500]
    results = test_router(sample)
    print(f"Tested: {results['total']}")
    route_rate = results['routed'] / results['total'] * 100 if results['total'] else 0
    print(f"Routed: {results['routed']} ({route_rate:.1f}%)")
    print(f"Not routed: {results['total'] - results['routed']}")
    print()
    print("Top routes:")
    for route, count in results['routes'].most_common(10):
        print(f"  {route}: {count}")


def extract_bugs_to_log():
    """Extract bugs from sessions and feed them into the event log."""
    sessions = find_sessions()
    all_bugs = []

    for sp in sessions[:10]:  # Limit to 10 most recent
        bugs = extract_bugs(sp)
        all_bugs.extend(bugs)

    print(f"Extracted {len(all_bugs)} bug references from {min(10, len(sessions))} sessions")

    # Feed unique bugs into event log (avoid duplicates)
    seen = set()
    count = 0
    for bug in all_bugs[:30]:  # Max 30
        desc = bug["description"][:200]
        import hashlib
        h = hashlib.sha256(desc.encode()).hexdigest()[:12]
        if h not in seen:
            seen.add(h)
            try:
                subprocess.run(
                    ["python", "f:/ClaudeFiles/.claude/pete-eventlog.py",
                     "log", "bug", desc, "--tags=replay-import", "--outcome=unknown"],
                    timeout=10, capture_output=True
                )
                count += 1
            except Exception:
                pass

    print(f"Imported {count} unique bugs into event log")
    print("Run: python pete-daemon.py once  (to test pheromone activation)")


def cmd():
    if len(sys.argv) < 2:
        print("Usage: pete-replay-test.py <scan|extract-bugs|validate-routes>")
        sys.exit(1)

    cmd_name = sys.argv[1]
    if cmd_name == "scan":
        scan_all()
    elif cmd_name == "extract-bugs":
        extract_bugs_to_log()
    elif cmd_name == "validate-routes":
        sessions = find_sessions()
        all_msgs = []
        for sp in sessions:
            all_msgs.extend(extract_user_messages(sp))
        results = test_router(all_msgs[:1000])
        print(f"Total tested: {results['total']}")
        print(f"Routed: {results['routed']} ({results['routed']/max(results['total'],1)*100:.1f}%)")
        print(f"Top routes: {results['routes'].most_common(15)}")
    else:
        print(f"Unknown: {cmd_name}")


if __name__ == "__main__":
    cmd()
