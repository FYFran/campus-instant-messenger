"""
Auto-Benchmark Hook — Growth Loop Automation.

Detects skill file changes via git diff → runs BugHuntBench CI → alerts on drift.

Usage:
  python auto_benchmark.py                    # Check all changed skills
  python auto_benchmark.py --skill 铁壁       # Check specific skill
  python auto_benchmark.py --watch            # Monitor for changes (future)

Growth Loop:
  skill change → benchmark → score vs baseline → drift? → trigger 轮回 GEPA
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# __file__ = .claude/scripts/auto_benchmark.py → parent.parent = .claude/
BENCH_DIR = Path(__file__).parent.parent / "benchmarks" / "bughunt"
SKILLS_DIR = Path(__file__).parent.parent / "skills"
RESULTS_FILE = BENCH_DIR / "results.tsv"
BASELINE_FILE = BENCH_DIR / "baselines.json"

# Skill file → skill name mapping
SKILL_FILE_MAP = {
    "铁壁.md": "铁壁", "缉凶.md": "缉凶", "明镜.md": "明镜",
    "布阵.md": "布阵", "门神.md": "门神", "破阵.md": "破阵",
    "天眼.md": "天眼", "架构师.md": "架构师", "试金石.md": "试金石",
    "轮回.md": "轮回", "火眼/SKILL.md": "火眼",
}

def get_changed_skills() -> list[str]:
    """Find which skills have changed files (git diff vs HEAD)."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            capture_output=True, text=True, cwd=SKILLS_DIR.parent.parent,
            timeout=10
        )
        changed = set()
        for line in result.stdout.splitlines():
            for pattern, skill in SKILL_FILE_MAP.items():
                if pattern in line:
                    changed.add(skill)
        return sorted(changed)
    except Exception as e:
        print(f"git diff failed: {e}")
        return []


def load_baselines() -> dict:
    """Load stored baseline scores per skill."""
    if BASELINE_FILE.exists():
        with open(BASELINE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_baselines(baselines: dict):
    """Save baseline scores."""
    BASELINE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(BASELINE_FILE, 'w', encoding='utf-8') as f:
        json.dump(baselines, f, indent=2, ensure_ascii=False)


def run_benchmark(skill: str, mode: str = "quick") -> dict | None:
    """Run BugHuntBench CI for a specific skill."""
    ci_script = BENCH_DIR / "bughunt_ci.py"
    if not ci_script.exists():
        print(f"  CI script not found: {ci_script}")
        return None

    try:
        result = subprocess.run(
            [sys.executable, str(ci_script),
             "--skill", skill, "--mode", mode, "--gate-only"],
            capture_output=True, text=True,
            cwd=BENCH_DIR, timeout=30
        )
        # Parse score from output
        output = result.stdout + result.stderr
        score = None
        status = "UNKNOWN"
        for line in output.splitlines():
            if "Gate: PASS" in line:
                status = "PASS"
            elif "Gate: FAIL" in line:
                status = "FAIL"
            if "Avg Score" in line:
                try:
                    score = float(line.split(":")[-1].strip().split()[0])
                except ValueError:
                    pass
        return {"skill": skill, "status": status, "score": score,
                "output": output[:500], "timestamp": datetime.now().isoformat()}
    except subprocess.TimeoutExpired:
        return {"skill": skill, "status": "TIMEOUT", "score": None,
                "output": "", "timestamp": datetime.now().isoformat()}
    except Exception as e:
        return {"skill": skill, "status": "ERROR", "score": None,
                "output": str(e), "timestamp": datetime.now().isoformat()}


def check_drift(skill: str, current_score: float | None,
                baselines: dict, max_drift: float = 5.0) -> str:
    """Compare current score to baseline. Return status."""
    if current_score is None:
        return "NO_DATA"
    if skill not in baselines:
        return "NO_BASELINE"

    baseline = baselines[skill].get("score", 0)
    if baseline == 0:
        return "NO_BASELINE"

    drift_pct = (current_score - baseline) / baseline * 100
    if drift_pct < -max_drift:
        return f"DRIFT_DOWN ({drift_pct:+.1f}%)"
    elif drift_pct > max_drift:
        return f"IMPROVED ({drift_pct:+.1f}%)"
    else:
        return f"STABLE ({drift_pct:+.1f}%)"


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Auto-Benchmark — Growth Loop Hook")
    parser.add_argument("--skill", default=None, help="Check specific skill")
    parser.add_argument("--watch", action="store_true", help="Monitor mode (future)")
    parser.add_argument("--set-baseline", action="store_true",
                        help="Store current scores as baseline")
    parser.add_argument("--max-drift", type=float, default=5.0,
                        help="Max allowed drift percent (default: 5)")
    args = parser.parse_args()

    # Determine which skills to check
    if args.skill:
        skills = [args.skill]
    else:
        skills = get_changed_skills()

    if not skills:
        print("No skill changes detected.")
        return

    print(f"Auto-Benchmark: {len(skills)} skill(s) changed")
    baselines = load_baselines()

    results = []
    for skill in skills:
        print(f"\n--- {skill} ---")
        result = run_benchmark(skill)
        if result:
            drift_status = check_drift(skill, result["score"], baselines, args.max_drift)
            print(f"  Score: {result['score']}  Status: {result['status']}  Drift: {drift_status}")
            result["drift"] = drift_status
            results.append(result)

            # Alert on significant drift
            if "DRIFT_DOWN" in drift_status:
                print(f"  *** ACTION: Score dropped! Run 轮回 GEPA on {skill} ***")
            elif "IMPROVED" in drift_status:
                print(f"  *** Score improved! Consider updating baseline ***")
        else:
            print(f"  Benchmark failed")

    # Set baseline if requested
    if args.set_baseline:
        for r in results:
            if r["score"] is not None:
                baselines[r["skill"]] = {
                    "score": r["score"],
                    "timestamp": r["timestamp"],
                    "mode": "quick"
                }
        save_baselines(baselines)
        print(f"\nBaselines updated for {len(results)} skill(s)")

    # Summary
    print(f"\n=== Growth Loop Summary ===")
    drift_downs = [r for r in results if "DRIFT_DOWN" in r.get("drift", "")]
    improvements = [r for r in results if "IMPROVED" in r.get("drift", "")]
    no_baseline = [r for r in results if r.get("drift") == "NO_BASELINE"]

    print(f"  Checked: {len(results)}")
    print(f"  Drift down: {len(drift_downs)} (needs GEPA)")
    print(f"  Improved: {len(improvements)} (update baseline?)")
    print(f"  No baseline: {len(no_baseline)} (first run)")

    if drift_downs:
        print(f"\n  Next: 轮回 diagnose {[r['skill'] for r in drift_downs]}")


if __name__ == "__main__":
    main()
