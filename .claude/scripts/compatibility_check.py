"""
Cross-Skill Compatibility Checker.

Validates that skill changes don't break downstream dependencies.
Runs in <1s, zero tokens.

Usage:
  python compatibility_check.py           # Full check
  python compatibility_check.py --skill 铁壁  # Check impact of changing one skill
"""

import json
import os
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
SKILLS_DIR = SCRIPT_DIR.parent / "skills"
REGISTRY_FILE = SKILLS_DIR / "references" / "skill_registry.json"
DAG_FILE = SKILLS_DIR / "references" / "skill_dag.json"

# Map of old→new skill names for migration checking
NAME_MIGRATION = {
    "code-review": "明镜", "deploy": "布阵", "forge": "轮回",
    "quality-gate": "门神", "red-team": "破阵",
}


def load_json(path: Path) -> dict:
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def check_boundary_references(skill_id: str, filepath: Path) -> list[str]:
    """Check that a skill's boundary section references correct downstream skills."""
    issues = []
    if not filepath.exists():
        return [f"File not found: {filepath}"]

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Extract boundary line
    boundary_match = re.search(r'\*\*边界[：:]\*\*\s*(.+?)(?:\n|$)', content)
    if boundary_match:
        boundary_text = boundary_match.group(1)
        # Check for old English names
        for old_name, new_name in NAME_MIGRATION.items():
            if old_name in boundary_text and old_name != skill_id:
                issues.append(f"Boundary uses old name '{old_name}' — should be '{new_name}'")

    # Check growth section references
    if "forge采集" in content or "forge自身" in content:
        issues.append("Growth section still uses 'forge' — should be '轮回'")

    # Check title matches frontmatter name
    name_match = re.search(r'^name:\s*(.+)$', content, re.MULTILINE)
    title_match = re.search(r'^#\s+(.+?)(?:\s+v\d|$)', content, re.MULTILINE)
    if name_match and title_match:
        fm_name = name_match.group(1).strip()
        title_name = title_match.group(1).strip()
        # Title often has English name still
        for old_name, new_name in NAME_MIGRATION.items():
            if old_name in title_name.lower() and new_name == fm_name:
                issues.append(f"Title still uses old name '{title_name}' — consider updating to '{new_name}'")

    return issues


def check_dag_consistency(registry: dict, dag: dict) -> list[str]:
    """Check DAG edges are consistent with registry dependencies."""
    issues = []
    skills = registry.get("skills", {})
    edges = dag.get("edges", [])

    for edge in edges:
        from_s = edge["from"]
        to_s = edge["to"]

        if from_s not in skills:
            issues.append(f"DAG edge {from_s}->{to_s}: '{from_s}' not in registry")
            continue
        if to_s not in skills:
            issues.append(f"DAG edge {from_s}->{to_s}: '{to_s}' not in registry")
            continue

        # Check: does the registry say from_s is depended_by to_s?
        if to_s not in skills[from_s].get("depended_by", []):
            issues.append(f"DAG says {from_s}->{to_s} but registry doesn't list {to_s} in {from_s}.depended_by")

        # Check: does to_s list from_s as dependency?
        if from_s not in skills[to_s].get("depends_on", []):
            issues.append(f"DAG says {from_s}->{to_s} but registry doesn't list {from_s} in {to_s}.depends_on")

    return issues


def check_output_schema_compat(registry: dict) -> list[str]:
    """Check that downstream skills can consume upstream output schemas."""
    issues = []
    skills = registry.get("skills", {})

    for sid, info in skills.items():
        upstream_of = info.get("depended_by", [])
        if not upstream_of:
            continue

        my_schema = info.get("output_schema")
        if not my_schema:
            issues.append(f"{sid}: has depended_by={upstream_of} but no output_schema defined")
            continue

        # Check that shared_signals in DAG knows about this schema
        dag = load_json(DAG_FILE)
        signals = dag.get("shared_signals", {})
        if my_schema not in signals:
            issues.append(f"{sid}: output_schema '{my_schema}' not defined in DAG shared_signals")

    return issues


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Cross-Skill Compatibility Checker")
    parser.add_argument("--skill", default=None, help="Check impact of changing a specific skill")
    parser.add_argument("--verbose", action="store_true", help="Show all checks including OK")
    args = parser.parse_args()

    registry = load_json(REGISTRY_FILE)
    dag = load_json(DAG_FILE)
    skills = registry.get("skills", {})
    all_issues = []

    # 1. Boundary references check
    print("=== 1. Skill Boundary References ===")
    for sid, info in skills.items():
        if args.skill and sid != args.skill:
            continue
        filepath = SKILLS_DIR / info.get("file", f"{sid}.md")
        boundary_issues = check_boundary_references(sid, filepath)
        if boundary_issues:
            for issue in boundary_issues:
                all_issues.append(f"[{sid}] {issue}")
                print(f"  ERR [{sid}] {issue}")
        elif args.verbose:
            print(f"  OK  [{sid}] boundary references correct")
    if not [i for i in all_issues if "boundary" in i.lower() or "title" in i.lower() or "growth" in i.lower() or "forge" in i.lower()]:
        print("  OK All boundary references correct")

    # 2. DAG consistency
    print("\n=== 2. DAG-Registry Consistency ===")
    dag_issues = check_dag_consistency(registry, dag)
    if dag_issues:
        for issue in dag_issues:
            all_issues.append(issue)
            print(f"  ERR {issue}")
    else:
        print("  OK All {len(dag.get('edges', []))} edges consistent with registry")

    # 3. Output schema compatibility
    print("\n=== 3. Output Schema Compatibility ===")
    schema_issues = check_output_schema_compat(registry)
    if schema_issues:
        for issue in schema_issues:
            all_issues.append(issue)
            print(f"  ERR {issue}")
    else:
        print("  OK All output schemas registered in DAG shared_signals")

    # 4. Impact analysis (if --skill specified)
    if args.skill and args.skill in skills:
        info = skills[args.skill]
        upstream_of = info.get("depended_by", [])
        print(f"\n=== Impact: changing {args.skill} ===")
        print(f"  Version: {info.get('version')}")
        print(f"  Downstream skills affected: {upstream_of}")
        if upstream_of:
            print(f"  Action: re-run baseline for {', '.join(upstream_of)} after change")
        print(f"  Output schema: {info.get('output_schema')}")
        print(f"  Bug prefix: {info.get('bug_prefix')}")

    # Summary
    print(f"\n=== Summary ===")
    if all_issues:
        print(f"  {len(all_issues)} issue(s) found")
        sys.exit(1)
    else:
        print("  All compatibility checks passed")


if __name__ == "__main__":
    main()
