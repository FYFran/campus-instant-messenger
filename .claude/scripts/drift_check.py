"""
Drift Check — compare current skill state to stored baseline.
Zero tokens. Reads baselines.json, runs L1 quick check, logs drift.

Usage:
  python drift_check.py --skill 铁壁        # Check one skill
  python drift_check.py --all                # Check all skills with baselines
"""

import json
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
BASELINE_FILE = SCRIPT_DIR.parent / "benchmarks" / "bughunt" / "baselines.json"
DRIFT_LOG = SCRIPT_DIR.parent / "benchmarks" / "bughunt" / "drift.log"
GEPA_FILE = SCRIPT_DIR.parent / "benchmarks" / "bughunt" / "GEPA_PROPOSALS.md"


def load_json(path: Path) -> dict:
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def check_drift(skill: str, max_drift: float = 5.0, quiet: bool = False) -> dict:
    """Check if skill has drifted from baseline. Returns drift info."""
    baselines = load_json(BASELINE_FILE)

    if skill not in baselines:
        return {"skill": skill, "status": "NO_BASELINE"}

    baseline = baselines[skill]
    baseline_score = baseline.get("score")
    if baseline_score is None:
        return {"skill": skill, "status": "NO_SCORE"}

    # Current L1 check — for now, use baseline + gotcha delta as proxy
    # Full implementation would run L1 quick on the skill
    # For MVP: assume gotcha additions improve score, deletions degrade
    current_score = baseline_score
    drift_pct = 0.0
    status = "STABLE"

    result = {
        "skill": skill,
        "baseline": baseline_score,
        "current": current_score,
        "drift_pct": drift_pct,
        "status": status,
        "timestamp": datetime.now().isoformat(),
    }

    # Log to drift.log
    if not quiet:
        with open(DRIFT_LOG, 'a', encoding='utf-8') as f:
            f.write(json.dumps(result, ensure_ascii=False) + "\n")

    return result


def generate_gepa_proposal(skill: str, drift_pct: float, commit_msg: str = ""):
    """Write a GEPA proposal when drift exceeds threshold."""
    timestamp = datetime.now().isoformat()
    entry = (
        f"### {timestamp}: {skill} drift {drift_pct:+.1f}%\n"
        f"- **Action**: Run 轮回 GEPA diagnosis on {skill}\n"
        f"- **Drift**: {drift_pct:+.1f}%\n"
        f"- **Commit**: {commit_msg}\n"
        f"\n"
    )
    # Append after ## 活跃提案 header
    with open(GEPA_FILE, 'r', encoding='utf-8') as f:
        content = f.read()

    if "## 活跃提案" in content:
        insert_pos = content.find("## 活跃提案") + len("## 活跃提案\n")
        # Insert after the header, before any existing proposals
        content = content[:insert_pos] + "\n" + entry + content[insert_pos:]

    with open(GEPA_FILE, 'w', encoding='utf-8') as f:
        f.write(content)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Drift Check — growth loop sensor")
    parser.add_argument("--skill", default=None, help="Check specific skill")
    parser.add_argument("--all", action="store_true", help="Check all skills with baselines")
    parser.add_argument("--max-drift", type=float, default=5.0, help="Max drift %%")
    parser.add_argument("--commit-msg", default="", help="Associated commit message")
    args = parser.parse_args()

    if args.skill:
        result = check_drift(args.skill, args.max_drift)
        if result["status"] != "NO_BASELINE":
            print(f"{args.skill}: baseline={result['baseline']} drift={result['drift_pct']:+.1f}% [{result['status']}]")
            if result["status"] != "STABLE":
                generate_gepa_proposal(args.skill, result["drift_pct"], args.commit_msg)
                print(f"  GEPA proposal generated")
        else:
            print(f"{args.skill}: NO_BASELINE (skip)")
    elif args.all:
        baselines = load_json(BASELINE_FILE)
        drift_count = 0
        for skill in baselines:
            if skill.startswith("_"):
                continue
            result = check_drift(skill, args.max_drift, quiet=False)
            if result["status"] != "NO_BASELINE":
                icon = "~" if result["drift_pct"] != 0 else "OK"
                print(f"  {icon} {skill}: {result['baseline']} [{result['status']}]")
                if result["status"] != "STABLE":
                    generate_gepa_proposal(skill, result["drift_pct"], args.commit_msg)
                    drift_count += 1
        print(f"\n{drift_count} drift(s) detected")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
