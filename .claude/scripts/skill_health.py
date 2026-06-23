"""
Skill Health Dashboard — 11-skill ecosystem health at a glance.

Usage:
  python skill_health.py              # Full dashboard
  python skill_health.py --skill 铁壁  # Single skill detail
  python skill_health.py --tier core   # Filter by tier
  python skill_health.py --issues      # Only show problems
"""

import json
import os
import sys
from datetime import datetime, date
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
SKILLS_DIR = SCRIPT_DIR.parent / "skills"
BENCH_DIR = SCRIPT_DIR.parent / "benchmarks" / "bughunt"
REGISTRY_FILE = SKILLS_DIR / "references" / "skill_registry.json"
BASELINE_FILE = BENCH_DIR / "baselines.json"


def load_json(path: Path) -> dict:
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def check_skill_health(skill_id: str, info: dict, baselines: dict) -> dict:
    """Check health of a single skill. Returns issues found."""
    issues = []
    warnings = []
    ok = []

    # 1. Review overdue?
    review_after = info.get("review_after", "")
    if review_after:
        try:
            review_date = date.fromisoformat(review_after)
            days_left = (review_date - date.today()).days
            if days_left < 0:
                issues.append(f"Review overdue by {-days_left}d (was {review_after})")
            elif days_left < 14:
                warnings.append(f"Review in {days_left}d ({review_after})")
            else:
                ok.append(f"Review due in {days_left}d")
        except ValueError:
            warnings.append(f"Invalid review_after: {review_after}")

    # 2. Baseline exists?
    baseline_score = baselines.get(skill_id, {}).get("score") if baselines else None
    tier = info.get("tier", "core")
    if baseline_score is None:
        if tier == "core" and info.get("bug_prefix"):
            warnings.append(f"No baseline score (core tier, run quick baseline)")
        else:
            ok.append("No baseline (support/meta tier OK)")
    if baseline_score is not None:
        # Tiered baseline thresholds: debugging harder than auditing
        min_score = 5 if skill_id == "缉凶" else 7
        if baseline_score < 4:
            issues.append(f"Baseline critically low: {baseline_score}/{info.get('max_score', 8)}")
        elif baseline_score < min_score:
            warnings.append(f"Baseline below {min_score}: {baseline_score}")
        else:
            ok.append(f"Baseline: {baseline_score}/{info.get('max_score', 8)}")

    # 3. Bug set completeness
    bug_prefix = info.get("bug_prefix")
    if bug_prefix:
        bugset_dir = BENCH_DIR / "bugset"
        bug_count = 0
        # Search in bugset root AND skill-named subdirectories
        for search_dir in [bugset_dir] + [d for d in bugset_dir.iterdir() if d.is_dir()]:
            if search_dir.exists():
                bug_count += len([d for d in search_dir.iterdir()
                                 if d.is_dir() and d.name.startswith(bug_prefix)])
        if bug_count == 0:
            issues.append(f"No bugs found for prefix {bug_prefix} in bugset/")
        elif bug_count < 3:
            warnings.append(f"Only {bug_count} bugs (target: 3+)")
        else:
            ok.append(f"{bug_count} bugs in set")

    # 4. Dependencies health (check depended_by)
    upstream_of = info.get("depended_by", [])
    if upstream_of:
        registry = load_json(REGISTRY_FILE).get("skills", {})
        for ds in upstream_of:
            if ds not in registry:
                warnings.append(f"Downstream '{ds}' not in registry")
            else:
                ds_lifecycle = registry[ds].get("lifecycle", "active")
                if ds_lifecycle not in ("active", None, ""):
                    warnings.append(f"Downstream '{ds}' lifecycle={ds_lifecycle}")

    # 5. Output schema defined?
    if not info.get("output_schema"):
        warnings.append("No output_schema defined")
    else:
        ok.append(f"Output: {info['output_schema']}")

    # 6. Maturity level
    maturity = info.get("maturity", "L1")
    if maturity in ("L1", "L2"):
        warnings.append(f"Maturity {maturity} — needs upgrade to L3+")
    else:
        ok.append(f"Maturity: {maturity}")

    return {"issues": issues, "warnings": warnings, "ok": ok}


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Skill Health Dashboard")
    parser.add_argument("--skill", default=None, help="Check specific skill")
    parser.add_argument("--tier", default=None, choices=["core", "support", "meta"])
    parser.add_argument("--issues", action="store_true", help="Only show problems")
    args = parser.parse_args()

    registry = load_json(REGISTRY_FILE)
    baselines = load_json(BASELINE_FILE)
    skills = registry.get("skills", {})

    if not skills:
        print("No skills found in registry. Run from project root.")
        sys.exit(1)

    # Filter
    if args.skill:
        skills = {args.skill: skills[args.skill]} if args.skill in skills else {}
    if args.tier:
        skills = {k: v for k, v in skills.items() if v.get("tier") == args.tier}

    if not skills:
        print("No skills match filters.")
        return

    # Check each skill
    results = {}
    total_issues = 0
    total_warnings = 0

    for skill_id, info in sorted(skills.items()):
        health = check_skill_health(skill_id, info, baselines)
        results[skill_id] = health
        total_issues += len(health["issues"])
        total_warnings += len(health["warnings"])

    # Print dashboard
    print(f"=== Skill Health Dashboard — {date.today()} ===\n")
    print(f"  Skills: {len(skills)}  Issues: {total_issues}  Warnings: {total_warnings}\n")

    for skill_id, info in sorted(skills.items()):
        health = results[skill_id]
        tier_icon = {"core": "[C]", "support": "[S]", "meta": "[M]"}.get(info.get("tier", ""), "[?]")
        version = info.get("version", "?")

        # Status icon
        if health["issues"]:
            status = "!!"
        elif health["warnings"]:
            status = " ~"
        else:
            status = "OK"

        print(f"  {status} {tier_icon} {skill_id} v{version} ({info.get('maturity', '?')})")

        if not args.issues:
            for ok in health["ok"]:
                print(f"      OK  {ok}")

        for w in health["warnings"]:
            print(f"      WRN {w}")

        for issue in health["issues"]:
            print(f"      ERR {issue}")

        print()

    # DAG health summary
    print("--- DAG Health ---")
    edges = registry.get("edges", []) or load_json(SKILLS_DIR / "references" / "skill_dag.json").get("edges", [])
    broken_edges = 0
    for edge in edges:
        from_s = edge["from"]
        to_s = edge["to"]
        if from_s not in skills:
            print(f"  ERR Edge {from_s}->{to_s}: '{from_s}' not in registry")
            broken_edges += 1
        elif to_s not in skills:
            print(f"  ERR Edge {from_s}->{to_s}: '{to_s}' not in registry")
            broken_edges += 1
    if broken_edges == 0:
        print(f"  OK All {len(edges)} DAG edges valid")

    # Summary
    print(f"\n=== Summary ===")
    print(f"  Total: {len(skills)} skills")
    print(f"  Healthy (no issues): {sum(1 for h in results.values() if not h['issues'])}")
    print(f"  Needs attention:     {sum(1 for h in results.values() if h['issues'])}")
    print(f"  Warnings:            {sum(1 for h in results.values() if h['warnings'])}")
    print(f"  Missing baselines:   {sum(1 for h in results.values() if any('No baseline' in w for w in h['warnings']))}")
    print(f"  Review overdue:      {sum(1 for h in results.values() if any('overdue' in i for i in h['issues']))}")


if __name__ == "__main__":
    main()
