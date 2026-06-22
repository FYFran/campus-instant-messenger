"""Peter Event Log — Append-only immutable event store.

Design: ActiveGraph + PROJECTMEM architecture principles.
  - Events are forever (append-only JSONL)
  - State is a projection (MEMORY.md regenerated from log)
  - Pre-action gate (deterministic, not LLM)

Usage:
  python pete-eventlog.py log <domain> "<description>" [--tags tag1,tag2] [--outcome pass|fail]
  python pete-eventlog.py query <domain> [--limit 20] [--search keyword]
  python pete-eventlog.py gate-check <action_hash> [--verbose]
  python pete-eventlog.py snapshot
"""

import sys, os, json, hashlib, uuid, io
from datetime import datetime, timezone
from pathlib import Path

if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

EVENT_LOG = Path("f:/ClaudeFiles/.claude/eventstore/events.jsonl")
MEMORY_DIR = Path(os.path.expanduser("~/.claude/projects/f--ClaudeFiles/memory"))
DOMAINS = ["bug", "lesson", "tool_use", "rule_violation", "workflow", "decision"]

EVENT_LOG.parent.mkdir(parents=True, exist_ok=True)


def _append(event: dict) -> dict:
    """Append immutable event to JSONL log."""
    with open(EVENT_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
    return event


def _read_all() -> list[dict]:
    """Read all events from log."""
    if not EVENT_LOG.exists():
        return []
    events = []
    with open(EVENT_LOG, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events


def log_event(domain: str, desc: str, tags: list[str] | None = None,
              outcome: str | None = None, explicit_hash: str | None = None) -> dict:
    """Append a single immutable event to the log."""
    assert domain in DOMAINS, f"Unknown domain: {domain}"

    event_id = uuid.uuid4().hex[:12]
    action_hash = explicit_hash or hashlib.sha256(f"{domain}:{desc}".encode()).hexdigest()[:12]
    ts = datetime.now(timezone.utc)

    event = {
        "id": event_id,
        "seq": _next_seq(),
        "domain": domain,
        "action_hash": action_hash,
        "description": desc,
        "tags": tags or [],
        "outcome": outcome,
        "timestamp": ts.isoformat(),
    }
    _append(event)
    return event


def _next_seq() -> int:
    """Get next sequence number by counting existing events."""
    if not EVENT_LOG.exists():
        return 1
    count = 0
    with open(EVENT_LOG, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                count += 1
    return count + 1


def query_events(domain: str | None = None, limit: int = 20,
                 search: str | None = None) -> list[dict]:
    """Query events, optionally filtered."""
    all_events = _read_all()
    if domain:
        all_events = [e for e in all_events if e.get("domain") == domain]
    if search:
        all_events = [e for e in all_events
                      if search.lower() in e.get("description", "").lower()
                      or search.lower() in ",".join(e.get("tags", [])).lower()]
    return all_events[-limit:]


def gate_check(action_hash: str) -> tuple[bool, str | None]:
    """PROJECTMEM pre-action gate: check if action failed before.

    Deterministic lookup — no LLM involved.
    Returns (blocked, reason).
    """
    all_events = _read_all()
    failures = []
    for e in all_events:
        if e.get("action_hash") != action_hash:
            continue
        outcome = e.get("outcome", "")
        tags = e.get("tags", [])
        if outcome == "fail" or any(t in ["failed", "regression", "reverted"] for t in tags):
            failures.append(e)

    if failures:
        latest = failures[-1]
        return True, f"FAIL {latest['timestamp'][:19]}: {latest['description'][:200]}"
    return False, None


def rebuild_memory_index():
    """Project event log into regenerated MEMORY.md index."""
    all_events = _read_all()
    if not all_events:
        return

    recent = all_events[-50:]
    domain_counts = {}
    for e in all_events:
        d = e.get("domain", "unknown")
        domain_counts[d] = domain_counts.get(d, 0) + 1

    lines = [
        "# Agent Memory Index",
        f"Generated: {datetime.now(timezone.utc).isoformat()[:19]}Z",
        f"Total events: {len(all_events)} | Domains: {dict(domain_counts)}",
        "",
        "## Recent Events",
        "",
    ]

    for e in reversed(recent):
        ts = e["timestamp"][:19]
        domain = e["domain"]
        desc = e["description"][:120]
        tags = e.get("tags", [])
        outcome = e.get("outcome", "")
        tag_str = f" [{', '.join(tags)}]" if tags else ""
        out_str = f" [{outcome}]" if outcome else ""
        lines.append(f"- [{domain}]{out_str} {ts}: {desc}{tag_str}")

    out_path = MEMORY_DIR / "MEMORY_EVENTS.md"  # NEVER overwrite MEMORY.md
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def cmd():
    if len(sys.argv) < 2:
        print("Usage: pete-eventlog.py <log|query|gate-check|snapshot> ...")
        sys.exit(1)

    cmd_name = sys.argv[1]
    args = sys.argv[2:]

    if cmd_name == "log":
        domain = args[0]
        desc = args[1]
        tags = None
        outcome = None
        explicit_hash = None
        rest = args[2:]
        i = 0
        while i < len(rest):
            a = rest[i]
            if a.startswith("--tags="):
                tags = a[7:].split(",")
            elif a == "--tags" and i + 1 < len(rest):
                tags = rest[i + 1].split(",")
                i += 1
            elif a.startswith("--outcome="):
                outcome = a[10:]
            elif a == "--outcome" and i + 1 < len(rest):
                outcome = rest[i + 1]
                i += 1
            elif a.startswith("--hash="):
                explicit_hash = a[7:]
            elif a == "--hash" and i + 1 < len(rest):
                explicit_hash = rest[i + 1]
                i += 1
            i += 1
        event = log_event(domain, desc, tags, outcome, explicit_hash)
        print(f"OK Event {event['id']} [{domain}] seq={event['seq']}: {desc[:80]}")

    elif cmd_name == "query":
        domain = args[0] if args else None
        limit = 20
        search = None
        for a in args[1:]:
            if a.startswith("--limit="):
                limit = int(a[8:])
            elif a.startswith("--search="):
                search = a[9:]
        events = query_events(domain, limit, search)
        for e in events:
            ts = e["timestamp"][:19]
            desc = e.get("description", str(e))[:150]
            outcome = e.get("outcome", "")
            out_str = f" [{outcome}]" if outcome else ""
            print(f"[{e['id']}]{out_str} {ts} [{e['domain']}] {desc}")
            if e.get("tags"):
                print(f"   Tags: {', '.join(e['tags'])}")

    elif cmd_name == "gate-check":
        action_hash = args[0]
        verbose = "--verbose" in args
        blocked, reason = gate_check(action_hash)
        if blocked:
            print(f"BLOCKED: {reason[:200]}")
            sys.exit(1)
        else:
            if verbose:
                print("OK: no known failure for this action")
            sys.exit(0)

    elif cmd_name == "snapshot":
        rebuild_memory_index()
        print("OK MEMORY.md rebuilt from event log")

    else:
        print(f"Unknown command: {cmd_name}")


if __name__ == "__main__":
    cmd()
