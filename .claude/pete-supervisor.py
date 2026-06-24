"""Peter Supervisor — ZeptoPM-inspired process supervision for AI agents.

Design: Koi/Civitas + ZeptoPM + Erlang/OTP patterns.
  - Process isolation (agents as independent runs)
  - Agent channels (TurnBased/Stream inter-agent messaging)
  - Semantic health checks (beyond "is alive")
  - Budget per agent (token limits, error budgets)
  - Exponential backoff + escalation

Usage:
  python pete-supervisor.py status
  python pete-supervisor.py check <agent_id> <agent_type>
  python pete-supervisor.py channel send <from> <to> "<message>"
  python pete-supervisor.py channel read <agent_id>
  - semantic_health: checks beyond "is alive" — loops, budget, progress

Usage:
  python pete-supervisor.py check <agent_id>
  python pete-supervisor.py status
  python pete-supervisor.py restart <agent_id>
"""

import sys, os, json, io
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dataclasses import dataclass, field

if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

EVENT_LOG = Path("f:/ClaudeFiles/.claude/eventstore/events.jsonl")
SUPERVISOR_STATE = Path("f:/ClaudeFiles/.claude/eventstore/supervisor.json")
CHANNELS_DIR = Path("f:/ClaudeFiles/.claude/eventstore/channels")

SUPERVISOR_STATE.parent.mkdir(parents=True, exist_ok=True)

# --- Config ---
DEFAULT_CONFIG = {
    "strategies": {
        "debugger": "one_for_one",
        "code-reviewer": "one_for_one",
        "security-auditor": "one_for_one",
        "refactor-master": "one_for_one",
        "caveman:builder": "one_for_one",
        "deploy-captain": "one_for_one",
        "test-generator": "one_for_one",
        "pantheon": "rest_for_one",  # pipeline: plan -> build -> verify -> synthesize
    },
    "restart_policy": {
        "max_restarts": 3,
        "window_seconds": 300,  # 5 minutes
        "backoff_base": 2,
        "max_backoff": 60,
    },
    "health_checks": {
        "max_consecutive_errors": 3,
        "max_idle_seconds": 180,
        "max_turns": 50,
        "budget_warning_tokens": 100000,
    },
}


@dataclass
class AgentRun:
    agent_id: str
    agent_type: str
    start_time: str
    status: str = "running"  # running, success, failed, stalled
    turns: int = 0
    tokens: int = 0
    errors: int = 0
    last_activity: str = ""

    def is_stalled(self) -> bool:
        if not self.last_activity:
            return False
        last = datetime.fromisoformat(self.last_activity)
        return (datetime.now(timezone.utc) - last).total_seconds() > 180

    def has_too_many_errors(self) -> bool:
        return self.errors >= 3


def load_state() -> dict:
    """Load supervisor state from disk."""
    if SUPERVISOR_STATE.exists():
        return json.loads(SUPERVISOR_STATE.read_text(encoding="utf-8"))
    return {"agents": {}, "restart_counts": {}, "config": DEFAULT_CONFIG}


def save_state(state: dict):
    """Persist supervisor state atomically."""
    tmp = str(SUPERVISOR_STATE) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dumps(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, str(SUPERVISOR_STATE))


def get_restart_count(agent_type: str) -> int:
    """How many times has this agent type restarted recently?"""
    state = load_state()
    counts = state.get("restart_counts", {})
    key = agent_type
    entries = counts.get(key, [])
    window = state["config"]["restart_policy"]["window_seconds"]
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=window)
    # Clean old entries
    fresh = [t for t in entries if datetime.fromisoformat(t) > cutoff]
    return len(fresh)


def record_restart(agent_type: str, agent_id: str):
    """Record a restart event."""
    state = load_state()
    counts = state.setdefault("restart_counts", {})
    counts.setdefault(agent_type, []).append(datetime.now(timezone.utc).isoformat())
    save_state(state)


def semantic_health(agent_type: str, agent_id: str) -> dict:
    """Check if an agent is semantically healthy.

    Returns: {"healthy": bool, "issues": [str], "recommended_action": str}
    """
    state = load_state()
    config = state["config"]["health_checks"]
    agents = state.get("agents", {})

    run = agents.get(agent_id)
    if not run:
        return {"healthy": True, "issues": [], "recommended_action": "none"}

    issues = []

    if run.get("errors", 0) >= config["max_consecutive_errors"]:
        issues.append(f"Too many errors: {run['errors']}")

    if run.get("turns", 0) >= config["max_turns"]:
        issues.append("Possible infinite loop (>50 turns)")

    if run.get("tokens", 0) >= config["budget_warning_tokens"]:
        issues.append(f"Token budget warning: {run['tokens']} tokens used")

    last_act = run.get("last_activity", "")
    if last_act:
        elapsed = (datetime.now(timezone.utc) - datetime.fromisoformat(last_act)).total_seconds()
        if elapsed > config["max_idle_seconds"]:
            issues.append(f"Stalled: no activity for {int(elapsed)}s")

    if issues:
        strategy = state["config"]["strategies"].get(agent_type, "one_for_one")
        policy = state["config"]["restart_policy"]
        restart_count = get_restart_count(agent_type)
        if restart_count >= policy["max_restarts"]:
            return {
                "healthy": False,
                "issues": issues,
                "recommended_action": "escalate",
                "reason": f"Max restarts ({policy['max_restarts']}) exceeded in {policy['window_seconds']}s window"
            }

        backoff = min(policy["backoff_base"] ** restart_count, policy["max_backoff"])
        return {
            "healthy": False,
            "issues": issues,
            "recommended_action": "restart",
            "strategy": strategy,
            "backoff_seconds": backoff,
            "restart_count": restart_count + 1,
        }

    return {"healthy": True, "issues": [], "recommended_action": "none"}


def status() -> dict:
    """Get full supervisor status."""
    state = load_state()
    agents = state.get("agents", {})
    restart_counts = state.get("restart_counts", {})

    summary = {
        "total_agents": len(agents),
        "healthy": 0,
        "unhealthy": 0,
        "agents": [],
    }

    for agent_id, run in agents.items():
        health = semantic_health(run.get("agent_type", "unknown"), agent_id)
        if health["healthy"]:
            summary["healthy"] += 1
        else:
            summary["unhealthy"] += 1
        summary["agents"].append({
            "agent_id": agent_id,
            "agent_type": run.get("agent_type", "unknown"),
            "status": run.get("status", "unknown"),
            "healthy": health["healthy"],
            "issues": health.get("issues", []),
            "recommended_action": health.get("recommended_action", "none"),
        })

    return summary


def cmd():
    if len(sys.argv) < 2:
        print("Usage: pete-supervisor.py <check|status|restart> [agent_id]")
        sys.exit(1)

    cmd_name = sys.argv[1]

    if cmd_name == "status":
        s = status()
        print(f"Agents: {s['total_agents']} total, {s['healthy']} healthy, {s['unhealthy']} unhealthy")
        for a in s["agents"]:
            icon = "OK" if a["healthy"] else "!!"
            print(f"  [{icon}] {a['agent_type']} ({a['agent_id'][:8]}) — {a['status']}")
            if a["issues"]:
                for issue in a["issues"]:
                    print(f"      {issue}")
                print(f"      Action: {a['recommended_action']}")

    elif cmd_name == "check":
        agent_id = sys.argv[2]
        agent_type = sys.argv[3] if len(sys.argv) > 3 else "unknown"
        health = semantic_health(agent_type, agent_id)
        if health["healthy"]:
            print(f"OK {agent_type} ({agent_id[:8]}) is healthy")
            sys.exit(0)
        else:
            print(f"UNHEALTHY {agent_type} ({agent_id[:8]}):")
            for issue in health["issues"]:
                print(f"  - {issue}")
            print(f"Action: {health['recommended_action']}")
            if "backoff_seconds" in health:
                print(f"Backoff: {health['backoff_seconds']}s")
            sys.exit(1)

    elif cmd_name == "restart":
        agent_id = sys.argv[2]
        agent_type = sys.argv[3] if len(sys.argv) > 3 else "unknown"
        record_restart(agent_type, agent_id)
        print(f"OK restart recorded for {agent_type} ({agent_id[:8]})")

    else:
        print(f"Unknown command: {cmd_name}")


if __name__ == "__main__":
    cmd()
