"""
DAG Orchestrator — Skill chain execution engine.

Reads skill_dag.json + registry → suggests/validates execution order.
Tracks state across phases.

Usage:
  python orchestrator.py --phase 验证       # Check pre-deploy chain readiness
  python orchestrator.py --phase 进化       # Check if any skill needs GEPA
  python orchestrator.py --from 火眼        # Show downstream chain from a skill
  python orchestrator.py --status           # Show execution state for all phases
  python orchestrator.py --execute 验证     # Show what to run (dry-run)
"""

import json
import os
import sys
from datetime import datetime, date
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
SKILLS_DIR = SCRIPT_DIR.parent / "skills"
REGISTRY_FILE = SKILLS_DIR / "references" / "skill_registry.json"
DAG_FILE = SKILLS_DIR / "references" / "skill_dag.json"
BASELINE_FILE = SCRIPT_DIR.parent / "benchmarks" / "bughunt" / "baselines.json"
HEALTH_LOG = SCRIPT_DIR.parent / "benchmarks" / "bughunt" / "orchestrator_log.jsonl"


def load_json(path: Path) -> dict:
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def log_action(phase: str, skill: str, action: str, result: str = "pending"):
    """Append to orchestrator log."""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "phase": phase,
        "skill": skill,
        "action": action,
        "result": result
    }
    HEALTH_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(HEALTH_LOG, 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def check_phase(phase_name: str, dag: dict, registry: dict, baselines: dict) -> dict:
    """Check readiness for a DAG phase. Returns status per skill."""
    lifecycle = dag.get("lifecycle", [])
    phase = next((p for p in lifecycle if p["phase"] == phase_name), None)
    if not phase:
        return {"error": f"Phase '{phase_name}' not found. Available: {[p['phase'] for p in lifecycle]}"}

    skills_in_phase = phase["skills"]
    trigger = phase.get("trigger", "")
    flow = phase.get("flow", "")

    results = {
        "phase": phase_name,
        "trigger": trigger,
        "flow": flow,
        "skills": {},
        "ready": True,
        "blockers": []
    }

    reg_skills = registry.get("skills", {})

    for sid in skills_in_phase:
        info = reg_skills.get(sid, {})
        baseline = baselines.get(sid, {})

        skill_status = {
            "version": info.get("version", "?"),
            "tier": info.get("tier", "?"),
            "maturity": info.get("maturity", "?"),
            "baseline": baseline.get("score"),
            "depends_on": info.get("depends_on", []),
            "status": "ready"
        }

        # Check dependencies
        for dep in info.get("depends_on", []):
            dep_baseline = baselines.get(dep, {}).get("score")
            if dep_baseline is None and reg_skills.get(dep, {}).get("tier") == "core":
                skill_status["status"] = "blocked"
                skill_status["blocked_by"] = f"{dep} (no baseline)"
                results["blockers"].append(f"{sid}: blocked by {dep}")
                results["ready"] = False

        # Check if skill itself is healthy
        if baseline.get("score") is not None and baseline.get("score") < 5:
            skill_status["status"] = "degraded"
            skill_status["note"] = f"Low baseline: {baseline['score']}"

        results["skills"][sid] = skill_status

    return results


def show_downstream(skill_id: str, dag: dict, visited: set = None) -> list:
    """Show all downstream skills from a given skill (DFS)."""
    if visited is None:
        visited = set()
    if skill_id in visited:
        return []
    visited.add(skill_id)

    chain = [skill_id]
    edges = dag.get("edges", [])
    for edge in edges:
        if edge["from"] == skill_id:
            chain.extend(show_downstream(edge["to"], dag, visited))
    return chain


def main():
    import argparse
    parser = argparse.ArgumentParser(description="DAG Orchestrator — Skill Chain Engine")
    parser.add_argument("--phase", default=None,
                       help="Phase to check (规划/开发/验证/发布/运行/进化)")
    parser.add_argument("--from", dest="from_skill", default=None,
                       help="Show downstream chain from a skill")
    parser.add_argument("--status", action="store_true",
                       help="Show execution state for all phases")
    parser.add_argument("--execute", default=None,
                       help="Execute a phase (dry-run: shows what would run)")
    args = parser.parse_args()

    dag = load_json(DAG_FILE)
    registry = load_json(REGISTRY_FILE)
    baselines = load_json(BASELINE_FILE)

    # Show downstream chain
    if args.from_skill:
        chain = show_downstream(args.from_skill, dag)
        print(f"=== Downstream from {args.from_skill} ===")
        for i, sid in enumerate(chain):
            prefix = "  " + "  " * (chain[:i].count(sid) if chain[:i].count(sid) else i)
            info = registry.get("skills", {}).get(sid, {})
            print(f"{'  '*i}{sid} v{info.get('version','?')} →")
        return

    # Show status for all phases
    if args.status:
        print(f"=== DAG Orchestrator Status — {date.today()} ===\n")
        lifecycle = dag.get("lifecycle", [])
        for phase in lifecycle:
            result = check_phase(phase["phase"], dag, registry, baselines)
            icon = "OK" if result.get("ready") else "!!"
            skills_str = " → ".join(result.get("skills", {}).keys())
            print(f"  {icon} [{phase['phase']}] {skills_str}")
            if result.get("blockers"):
                for b in result["blockers"]:
                    print(f"      BLOCKED: {b}")
        return

    # Check/execute specific phase
    if args.phase:
        result = check_phase(args.phase, dag, registry, baselines)
        if "error" in result:
            print(f"Error: {result['error']}")
            sys.exit(1)

        print(f"=== Phase: {args.phase} ===")
        print(f"  Trigger: {result['trigger']}")
        print(f"  Flow: {result['flow']}")
        print(f"  Ready: {result['ready']}")
        print()

        for sid, status in result["skills"].items():
            icon = {"ready": "[OK]", "blocked": "[!!]", "degraded": "[~]"}.get(status["status"], "[?]")
            print(f"  {icon} {sid} v{status['version']} ({status['maturity']})")
            if status.get("blocked_by"):
                print(f"      BLOCKED by: {status['blocked_by']}")
            if status.get("note"):
                print(f"      NOTE: {status['note']}")
            if status["depends_on"]:
                print(f"      Depends: {', '.join(status['depends_on'])}")

        if args.execute:
            print(f"\n  === Dry-run: would execute {args.phase} ===")
            for sid in result["skills"]:
                if result["skills"][sid]["status"] == "ready":
                    print(f"  1. Run {sid} (baseline: {result['skills'][sid]['baseline']})")
                    log_action(args.phase, sid, "dry-run", "pending")
            if result.get("blockers"):
                print(f"  BLOCKERS: {result['blockers']}")
                print(f"  Action: resolve blockers first, then re-run --phase {args.phase}")
        return

    # No args: show help
    parser.print_help()


if __name__ == "__main__":
    main()
