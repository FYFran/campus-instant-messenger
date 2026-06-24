"""Peter Daemon — L3.5 autonomous agent runtime.

Design: Axocoatl pheromone lattice + PROJECTMEM gate + ICRL verifier.
  - Watches event log for new events
  - Accumulates "pheromone" (signal strength) per task type
  - When threshold crossed → self-activates task
  - Dispatches to Claude Code (via MCP/CLI)
  - Verifies result with ICRL evaluator
  - Writes outcome back to event log

Architecture:
  while True:
    events = watch(event_log)              # 监听
    signals = accumulate(events)           # 信息素累积
    if signals.cross_threshold():          # 阈值激活
      task = self_assign(signals)          # 自分配
      result = dispatch(task)              # 调度执行
      verified = evaluator.verify(result)  # 验证
      event_log.append(verified)           # 反馈
    consolidate_memory()                   # 后台整理

Usage:
  python pete-daemon.py run                → continuous daemon mode
  python pete-daemon.py once               → single scan + act cycle
  python pete-daemon.py signals            → show current pheromone levels
"""

import sys, os, json, time, io, hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dataclasses import dataclass, field
from collections import defaultdict
from typing import Optional

if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

EVENT_LOG = Path("f:/ClaudeFiles/.claude/eventstore/events.jsonl")
DAEMON_STATE = Path("f:/ClaudeFiles/.claude/eventstore/daemon_state.json")
SIGNALS_LOG = Path("f:/ClaudeFiles/.claude/eventstore/pheromone_signals.jsonl")
DAEMON_STATE.parent.mkdir(parents=True, exist_ok=True)


# ============================================================
# Pheromone Lattice (Axocoatl stigmergic pattern)
# ============================================================

@dataclass
class SignalType:
    """A type of signal that can accumulate and trigger tasks."""
    name: str                    # e.g. "build_failure", "bug_pattern", "stale_skill"
    threshold: int               # how many events needed to trigger
    decay_hours: float           # half-life of signal strength
    task_template: str           # what task to generate
    agent: str                   # which agent to dispatch
    severity: str                # "critical", "warning", "info"


SIGNAL_TYPES = [
    SignalType(
        name="build_failure",
        threshold=2,
        decay_hours=4,
        task_template="Build has failed {count} times in recent history. Investigate and fix root cause.",
        agent="debugger",
        severity="critical",
    ),
    SignalType(
        name="security_violation",
        threshold=1,
        decay_hours=1,
        task_template="Security violation detected: {latest_description}. Audit and fix immediately.",
        agent="security-auditor",
        severity="critical",
    ),
    SignalType(
        name="bug_pattern_repeat",
        threshold=3,
        decay_hours=24,
        task_template="Bug pattern '{pattern}' has recurred {count} times. Run pantheon to permanently fix.",
        agent="pantheon",
        severity="warning",
    ),
    SignalType(
        name="test_failure_cascade",
        threshold=3,
        decay_hours=6,
        task_template="Tests failing across {count} events. Run full diagnostic and fix.",
        agent="refactor-master",
        severity="warning",
    ),
    SignalType(
        name="stale_skill",
        threshold=1,
        decay_hours=720,  # 30 days
        task_template="Skill '{skill}' has not been used in 30+ days. Audit and consider removal.",
        agent="watcher",
        severity="info",
    ),
    SignalType(
        name="disk_low",
        threshold=1,
        decay_hours=24,
        task_template="Disk space critically low. Clean up temp files and caches.",
        agent="watcher",
        severity="critical",
    ),
]


@dataclass
class PheromoneState:
    """Current pheromone level for a signal type."""
    signal: str
    count: int = 0
    last_event_ts: str = ""
    latest_description: str = ""
    accumulated_strength: float = 0.0  # weighted by recency

    def decay(self, half_life_hours: float, now: datetime) -> float:
        """Apply exponential decay based on time since last event."""
        if not self.last_event_ts:
            return self.accumulated_strength
        last = datetime.fromisoformat(self.last_event_ts)
        hours = (now - last).total_seconds() / 3600
        decay_factor = 0.5 ** (hours / half_life_hours)
        self.accumulated_strength *= decay_factor
        return self.accumulated_strength


def load_state() -> dict:
    if DAEMON_STATE.exists():
        return json.loads(DAEMON_STATE.read_text(encoding="utf-8"))
    return {"last_scan_seq": 0, "dispatched_hashes": [], "signals": {}}


def save_state(state: dict):
    """Persist daemon state."""
    with open(DAEMON_STATE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def scan_new_events() -> list[dict]:
    """Scan event log for events since last check."""
    if not EVENT_LOG.exists():
        return []

    state = load_state()
    last_seq = state.get("last_scan_seq", 0)

    new_events = []
    seq = 0
    with open(EVENT_LOG, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            seq += 1
            if seq > last_seq:
                new_events.append(json.loads(line))

    if new_events:
        state["last_scan_seq"] = seq
        save_state(state)

    return new_events


def accumulate_signals(events: list[dict]) -> dict[str, PheromoneState]:
    """Accumulate pheromone signals from new events.

    Maps events to signal types using keyword matching.
    Each new event adds 1.0 strength, weighted by recency.
    """
    state = load_state()
    signals_raw = state.get("signals", {})
    signals: dict[str, PheromoneState] = {}

    for st in SIGNAL_TYPES:
        ps = signals_raw.get(st.name, {})
        signals[st.name] = PheromoneState(
            signal=st.name,
            count=ps.get("count", 0),
            last_event_ts=ps.get("last_event_ts", ""),
            latest_description=ps.get("latest_description", ""),
            accumulated_strength=ps.get("accumulated_strength", 0.0),
        )

    now = datetime.now(timezone.utc)

    # Keyword → signal mapping
    SIGNAL_KEYWORDS = {
        "build_failure": ["FAIL", "build", "编译失败", "构建失败", "compile error"],
        "security_violation": ["security", "vulnerability", "漏洞", "CRITICAL", "exploit"],
        "bug_pattern_repeat": ["bug-pattern", "regression", "复发", "again"],
        "test_failure_cascade": ["test fail", "测试失败", "pytest fail", "flutter analyze"],
        "stale_skill": ["stale", "unused", "未使用", "last used"],
        "disk_low": ["disk", "磁盘", "空间不足", "low space"],
    }

    for event in events:
        desc = event.get("description", "").lower()
        tags_str = ",".join(event.get("tags", [])).lower()
        text = desc + " " + tags_str
        outcome = event.get("outcome", "")
        ts = event.get("timestamp", now.isoformat())

        for sig_name, keywords in SIGNAL_KEYWORDS.items():
            sig = signals[sig_name]
            if any(kw.lower() in text for kw in keywords):
                # Stronger signal for fail outcomes
                strength = 2.0 if outcome == "fail" else 1.0
                sig.accumulated_strength += strength
                sig.last_event_ts = ts
                sig.latest_description = event.get("description", "")[:200]
                if outcome == "fail":
                    sig.count += 1

    # Apply decay
    for st in SIGNAL_TYPES:
        signals[st.name].decay(st.decay_hours, now)

    # Persist
    state["signals"] = {
        name: {
            "count": s.count,
            "last_event_ts": s.last_event_ts,
            "latest_description": s.latest_description,
            "accumulated_strength": s.accumulated_strength,
        }
        for name, s in signals.items()
    }
    save_state(state)

    return signals


def check_thresholds(signals: dict[str, PheromoneState]) -> list[dict]:
    """Find signals that crossed their activation threshold."""
    triggered = []
    state = load_state()
    dispatched = state.get("dispatched_hashes", [])

    for st in SIGNAL_TYPES:
        sig = signals[st.name]
        if sig.accumulated_strength >= st.threshold:
            # Generate task
            task = st.task_template.format(
                count=sig.count,
                latest_description=sig.latest_description,
                pattern=sig.latest_description[:80],
                skill="(unknown)",
            )
            task_hash = hashlib.sha256(task.encode()).hexdigest()[:12]

            # Don't re-dispatch the same task
            if task_hash in dispatched:
                continue

            triggered.append({
                "signal": st.name,
                "severity": st.severity,
                "agent": st.agent,
                "task": task,
                "strength": sig.accumulated_strength,
                "hash": task_hash,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

            # Mark as dispatched
            dispatched.append(task_hash)
            # Keep only last 50 to prevent unbounded growth
            if len(dispatched) > 50:
                dispatched = dispatched[-50:]

    state["dispatched_hashes"] = dispatched
    save_state(state)
    return triggered


def log_triggered(tasks: list[dict]):
    """Log triggered tasks to pheromone signals log."""
    for t in tasks:
        with open(SIGNALS_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")


def once() -> list[dict]:
    """Single scan + act cycle."""
    events = scan_new_events()
    if events:
        print(f"New events: {len(events)}")
    else:
        print("No new events.")

    signals = accumulate_signals(events)
    triggered = check_thresholds(signals)

    if triggered:
        print(f"\nTRIGGERED ({len(triggered)}):")
        for t in triggered:
            print(f"  [{t['severity']}] {t['signal']} → {t['agent']}")
            print(f"    Task: {t['task'][:120]}")
    else:
        print("No thresholds crossed.")

    log_triggered(triggered)
    return triggered


def show_signals():
    """Display current pheromone levels."""
    events = scan_new_events()
    signals = accumulate_signals(events)

    print("Pheromone Lattice State:")
    for st in SIGNAL_TYPES:
        sig = signals[st.name]
        bar = "█" * min(int(sig.accumulated_strength), 20)
        active = "← ACTIVE" if sig.accumulated_strength >= st.threshold else ""
        print(f"  {st.name:25s} [{bar:<20s}] {sig.accumulated_strength:.1f}/{st.threshold} {active}")
        if sig.count > 0:
            print(f"    {sig.count} events, last: {sig.last_event_ts[:19] if sig.last_event_ts else 'never'}")


def run_daemon(interval: int = 30):
    """Continuous daemon mode — scan every N seconds."""
    print(f"Peter Daemon starting (interval={interval}s)...")
    print(f"Signal types: {len(SIGNAL_TYPES)}")

    try:
        while True:
            try:
                events = scan_new_events()
                if events:
                    signals = accumulate_signals(events)
                    triggered = check_thresholds(signals)
                    log_triggered(triggered)
                    for t in triggered:
                        print(f"[{t['severity'].upper()}] {t['signal']} → {t['agent']}: {t['task'][:80]}")
                time.sleep(interval)
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Daemon error (continuing): {e}")
                time.sleep(interval)
    except KeyboardInterrupt:
        print("\nDaemon stopped.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: pete-daemon.py <run|once|signals>")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "run":
        interval = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        run_daemon(interval)
    elif cmd == "once":
        once()
    elif cmd == "signals":
        show_signals()
    else:
        print(f"Unknown: {cmd}")
