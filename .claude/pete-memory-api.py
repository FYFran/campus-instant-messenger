"""Peter Memory API — MemMachine-inspired three-layer memory.

Layer mapping (MemMachine → Peter):
  Working Memory   → Claude Code conversation context (handled by runtime)
  Episodic Memory  → events.jsonl (append-only event log)
  Semantic Memory  → memory MCP knowledge graph + memory/*.md files

Usage:
  python pete-memory-api.py store episodic "<event>" [--tags t1,t2]
  python pete-memory-api.py store semantic "<fact>" [--entity entity_name]
  python pete-memory-api.py query episodic [--search keyword] [--limit 20]
  python pete-memory-api.py query semantic [--search keyword]
  python pete-memory-api.py recall "<task_description>"  → hybrid search
  python pete-memory-api.py stats
"""

import sys, os, json, hashlib, uuid, io
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

EVENT_LOG = Path("f:/ClaudeFiles/.claude/eventstore/events.jsonl")
MEMORY_DIR = Path(os.path.expanduser("~/.claude/projects/f--ClaudeFiles/memory"))
STATE_FILE = Path("f:/ClaudeFiles/.claude/eventstore/memory_state.json")

EVENT_LOG.parent.mkdir(parents=True, exist_ok=True)


# ============================================================
# Episodic Memory (events.jsonl — what happened)
# ============================================================

def episodic_store(desc: str, tags: Optional[list[str]] = None,
                   outcome: Optional[str] = None) -> dict:
    """Store an episodic event (append-only)."""
    event_id = uuid.uuid4().hex[:12]
    action_hash = hashlib.sha256(f"episodic:{desc}".encode()).hexdigest()[:12]
    ts = datetime.now(timezone.utc)

    event = {
        "id": event_id,
        "layer": "episodic",
        "action_hash": action_hash,
        "description": desc,
        "tags": tags or [],
        "outcome": outcome,
        "timestamp": ts.isoformat(),
    }

    seq = 1
    if EVENT_LOG.exists():
        with open(EVENT_LOG, encoding="utf-8") as f:
            seq = sum(1 for _ in f) + 1
    event["seq"] = seq

    with open(EVENT_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")

    return event


def episodic_query(search: Optional[str] = None, limit: int = 20) -> list[dict]:
    """Query episodic memory."""
    if not EVENT_LOG.exists():
        return []
    events = []
    with open(EVENT_LOG, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            e = json.loads(line)
            if e.get("layer") == "episodic" or "domain" in e:  # include legacy events
                events.append(e)

    if search:
        events = [e for e in events
                  if search.lower() in e.get("description", "").lower()
                  or search.lower() in ",".join(e.get("tags", [])).lower()]

    return events[-limit:]


# ============================================================
# Semantic Memory (memory MCP knowledge graph — what we know)
# ============================================================

def semantic_store(fact: str, entity_name: Optional[str] = None,
                   tags: Optional[list[str]] = None) -> dict:
    """Store a semantic fact (knowledge, not event)."""
    entity_id = entity_name or f"fact_{uuid.uuid4().hex[:8]}"

    entry = {
        "entity": entity_id,
        "fact": fact,
        "tags": tags or [],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "layer": "semantic",
    }

    # Store in semantic index
    state = _load_state()
    state.setdefault("semantic_facts", []).append(entry)
    _save_state(state)

    return entry


def semantic_query(search: Optional[str] = None) -> list[dict]:
    """Query semantic memory (facts + patterns)."""
    state = _load_state()
    facts = state.get("semantic_facts", [])

    if search:
        facts = [f for f in facts
                 if search.lower() in f.get("fact", "").lower()
                 or search.lower() in f.get("entity", "").lower()
                 or search.lower() in ",".join(f.get("tags", [])).lower()]

    return list(reversed(facts[-30:]))


# ============================================================
# Hybrid Recall (MemMachine's adaptive retrieval)
# ============================================================

def hybrid_recall(task_desc: str) -> dict:
    """Recall relevant memories from all layers for a given task.

    Mimics MemMachine's adaptive routing:
    - Direct match → return
    - Decompose → search sub-queries
    - Iterative chain → follow relationships
    """
    keywords = task_desc.lower().split()

    # Search episodic
    episodes = episodic_query(limit=50)
    relevant_episodes = []
    for e in episodes:
        desc = e.get("description", "").lower()
        tags = ",".join(e.get("tags", [])).lower()
        score = sum(1 for kw in keywords
                    if kw in desc or kw in tags)
        if score > 0:
            e["_relevance"] = score
            relevant_episodes.append(e)
    relevant_episodes.sort(key=lambda e: e.get("_relevance", 0), reverse=True)

    # Search semantic
    semantics = semantic_query()
    relevant_semantics = []
    for s in semantics:
        fact = s.get("fact", "").lower()
        tags = ",".join(s.get("tags", [])).lower()
        score = sum(1 for kw in keywords
                    if kw in fact or kw in tags)
        if score > 0:
            s["_relevance"] = score
            relevant_semantics.append(s)
    relevant_semantics.sort(key=lambda e: e.get("_relevance", 0), reverse=True)

    return {
        "task": task_desc,
        "episodic": relevant_episodes[:5],
        "semantic": relevant_semantics[:5],
        "total_matches": len(relevant_episodes) + len(relevant_semantics),
    }


# ============================================================
# State management
# ============================================================

def _load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"semantic_facts": [], "profile": {}}


def _save_state(state: dict):
    tmp = str(STATE_FILE) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, str(STATE_FILE))


def stats():
    """Memory system statistics."""
    episodic_count = 0
    if EVENT_LOG.exists():
        with open(EVENT_LOG, encoding="utf-8") as f:
            episodic_count = sum(1 for _ in f)

    state = _load_state()
    semantic_count = len(state.get("semantic_facts", []))

    return {
        "episodic_events": episodic_count,
        "semantic_facts": semantic_count,
        "event_log_size_kb": round(EVENT_LOG.stat().st_size / 1024, 1) if EVENT_LOG.exists() else 0,
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }


# ============================================================
# CLI
# ============================================================

def cmd():
    if len(sys.argv) < 2:
        print("Usage: pete-memory-api.py <store|query|recall|stats> ...")
        sys.exit(1)

    cmd_name = sys.argv[1]
    args = sys.argv[2:]

    if cmd_name == "store":
        layer = args[0]  # episodic | semantic
        content = args[1]
        tags = None
        entity = None
        i = 2
        while i < len(args):
            if args[i].startswith("--tags="):
                tags = args[i][7:].split(",")
            elif args[i] == "--tags" and i + 1 < len(args):
                tags = args[i + 1].split(",")
                i += 1
            elif args[i].startswith("--entity="):
                entity = args[i][9:]
            elif args[i] == "--entity" and i + 1 < len(args):
                entity = args[i + 1]
                i += 1
            i += 1

        if layer == "episodic":
            result = episodic_store(content, tags)
            print(f"OK episodic event {result['id']}: {content[:80]}")
        elif layer == "semantic":
            result = semantic_store(content, entity, tags)
            print(f"OK semantic fact [{result['entity']}]: {content[:80]}")
        else:
            print(f"Unknown layer: {layer}")
            sys.exit(1)

    elif cmd_name == "query":
        layer = args[0] if args else "episodic"
        search = None
        limit = 20
        i = 1
        while i < len(args):
            if args[i].startswith("--search="):
                search = args[i][9:]
            elif args[i] == "--search" and i + 1 < len(args):
                search = args[i + 1]
                i += 1
            elif args[i].startswith("--limit="):
                limit = int(args[i][8:])
            i += 1

        if layer == "episodic":
            results = episodic_query(search, limit)
        elif layer == "semantic":
            results = semantic_query(search)
        else:
            results = []

        for r in results:
            desc = r.get("description") or r.get("fact", "")
            ts = r.get("timestamp", "")[:19]
            layer_tag = r.get("layer", "?")
            print(f"[{layer_tag}] {ts}: {desc[:120]}")

    elif cmd_name == "recall":
        task = " ".join(args)
        result = hybrid_recall(task)
        print(f"Recall for: {task}")
        print(f"  Episodic matches: {len(result['episodic'])}")
        print(f"  Semantic matches: {len(result['semantic'])}")
        for e in result["episodic"]:
            print(f"  [E] {e.get('timestamp','')[:19]}: {e.get('description','')[:100]}")
        for s in result["semantic"]:
            print(f"  [S] {s.get('entity','')}: {s.get('fact','')[:100]}")

    elif cmd_name == "stats":
        s = stats()
        print(f"Episodic events: {s['episodic_events']}")
        print(f"Semantic facts:  {s['semantic_facts']}")
        print(f"Event log size:  {s['event_log_size_kb']} KB")

    else:
        print(f"Unknown: {cmd_name}")


if __name__ == "__main__":
    cmd()
