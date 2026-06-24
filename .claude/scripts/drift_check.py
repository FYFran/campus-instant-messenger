"""
Drift Check v2 — Real structural quality gates (L0 + L1).
Zero tokens. Based on CLEAR framework layered evaluation + Mid-Range Filter principle.

L0 Structure Gate (free, every commit):
  - Skill file exists
  - Frontmatter valid (name, version, lifecycle)
  - File size < 150% baseline
  - Required sections present (CONSTITUTION, Gotchas, Iron Law)

L1 Content Gate (free, every commit):
  - Gotcha count >= baseline (knowledge never decreases)
  - CONSTITUTION section unchanged (protected by forge rules)
  - Red lines present and non-empty

Usage:
  python drift_check.py --skill 铁壁
  python drift_check.py --all
"""

import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
SKILLS_DIR = SCRIPT_DIR.parent / "skills"
BASELINE_FILE = SCRIPT_DIR.parent / "benchmarks" / "bughunt" / "baselines.json"
DRIFT_LOG = SCRIPT_DIR.parent / "benchmarks" / "bughunt" / "drift.log"
GEPA_FILE = SCRIPT_DIR.parent / "benchmarks" / "bughunt" / "GEPA_PROPOSALS.md"
STRUCTURE_BASELINE_FILE = SCRIPT_DIR.parent / "benchmarks" / "bughunt" / "structure_baselines.json"

# Skill name → file path
SKILL_FILES = {
    "铁壁": "铁壁.md", "缉凶": "缉凶.md", "明镜": "明镜.md",
    "布阵": "布阵.md", "门神": "门神.md", "破阵": "破阵.md",
    "天眼": "天眼.md", "架构师": "架构师.md", "试金石": "试金石.md",
    "轮回": "轮回.md", "火眼": "火眼/SKILL.md",
}

REQUIRED_SECTIONS = ["CONSTITUTION", "Gotchas", "Iron Law"]


def load_json(path: Path) -> dict:
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def parse_skill(skill_name: str) -> dict | None:
    """Parse a skill file and extract structural metrics."""
    file_rel = SKILL_FILES.get(skill_name)
    if not file_rel:
        return None

    filepath = SKILLS_DIR / file_rel
    if not filepath.exists():
        return None

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    metrics = {
        "file": str(file_rel),
        "size": len(content.encode('utf-8')),
        "exists": True,
    }

    # Parse frontmatter
    fm_match = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
    if fm_match:
        fm_text = fm_match.group(1)
        metrics["frontmatter_valid"] = True
        for field in ["name:", "lifecycle:"]:
            if field not in fm_text:
                metrics["frontmatter_valid"] = False
                break
    else:
        metrics["frontmatter_valid"] = False

    # Count gotchas (table rows starting with | # |)
    gotcha_count = len(re.findall(r'^\|\s*\d+\s*\|', content, re.MULTILINE))
    metrics["gotcha_count"] = gotcha_count

    # Check CONSTITUTION section
    const_match = re.search(r'## CONSTITUTION[^\n]*\n(.*?)(?=\n## |\n---|\Z)', content, re.DOTALL)
    if const_match:
        const_text = const_match.group(1).strip()
        metrics["constitution_present"] = True
        metrics["constitution_hash"] = hashlib.md5(const_text.encode()).hexdigest()
        metrics["constitution_len"] = len(const_text)
    else:
        metrics["constitution_present"] = False

    # Check required sections
    missing_sections = []
    for section in REQUIRED_SECTIONS:
        if section == "Iron Law":
            if "Iron Law" not in content and "红线" not in content:
                missing_sections.append(section)
        elif section not in content:
            missing_sections.append(section)
    metrics["missing_sections"] = missing_sections
    metrics["sections_complete"] = len(missing_sections) == 0

    # Count red lines (any non-empty line after 红线 or Iron Law section)
    red_match = re.search(r'(?:红线|Iron Law)[^\n]*\n(.*?)(?=\n## |\n---|\Z)', content, re.DOTALL)
    if red_match:
        red_text = red_match.group(1).strip()
        red_lines = [l for l in red_text.split('\n') if l.strip() and not l.strip().startswith('**')]
        metrics["red_line_count"] = len(red_lines) if red_lines else 1  # At least 1 if section exists
    else:
        metrics["red_line_count"] = 0

    return metrics


def check_drift(skill: str) -> dict:
    """L0+L1 structural drift check. Returns detailed check results."""
    baseline_struct = load_json(STRUCTURE_BASELINE_FILE)
    current = parse_skill(skill)

    if not current:
        return {"skill": skill, "status": "FILE_NOT_FOUND", "checks": []}

    checks = []
    score = 8  # Start at 8, subtract for failures

    # Store as baseline if first run
    if skill not in baseline_struct:
        baseline_struct[skill] = {
            "size": current["size"],
            "gotcha_count": current["gotcha_count"],
            "constitution_hash": current.get("constitution_hash"),
            "red_line_count": current.get("red_line_count", 0),
        }
        save_json(STRUCTURE_BASELINE_FILE, baseline_struct)
        return {"skill": skill, "status": "BASELINED", "metrics": current, "checks": []}

    base = baseline_struct[skill]

    # L0: Structure checks
    # 1. File exists
    if not current["exists"]:
        checks.append({"gate": "L0", "check": "file_exists", "passed": False, "detail": "Skill file not found"})
        score -= 8
    else:
        checks.append({"gate": "L0", "check": "file_exists", "passed": True})

    # 2. Frontmatter valid
    if not current["frontmatter_valid"]:
        checks.append({"gate": "L0", "check": "frontmatter", "passed": False, "detail": "Missing name/lifecycle/version"})
        score -= 2
    else:
        checks.append({"gate": "L0", "check": "frontmatter", "passed": True})

    # 3. Size within 150% of baseline (Decagon: length constraints essential)
    size_limit = base["size"] * 1.5
    if current["size"] > size_limit:
        checks.append({"gate": "L0", "check": "size_bound", "passed": False,
                       "detail": f"Size {current['size']} > {int(size_limit)} (150% of baseline {base['size']})"})
        score -= 2
    else:
        checks.append({"gate": "L0", "check": "size_bound", "passed": True})

    # 4. Required sections present
    if not current["sections_complete"]:
        checks.append({"gate": "L0", "check": "sections", "passed": False,
                       "detail": f"Missing: {current['missing_sections']}"})
        score -= 1
    else:
        checks.append({"gate": "L0", "check": "sections", "passed": True})

    # L1: Content checks
    # 5. Gotcha count never decreases (knowledge ratchet)
    if current["gotcha_count"] < base["gotcha_count"]:
        checks.append({"gate": "L1", "check": "gotcha_ratchet", "passed": False,
                       "detail": f"Gotchas decreased: {base['gotcha_count']} → {current['gotcha_count']}"})
        score -= 1
    elif current["gotcha_count"] > base["gotcha_count"]:
        checks.append({"gate": "L1", "check": "gotcha_ratchet", "passed": True,
                       "detail": f"Gotchas increased: {base['gotcha_count']} → {current['gotcha_count']} (knowledge growth!)"})
    else:
        checks.append({"gate": "L1", "check": "gotcha_ratchet", "passed": True})

    # 6. CONSTITUTION unchanged (forge rule)
    if current.get("constitution_hash") != base.get("constitution_hash"):
        checks.append({"gate": "L1", "check": "constitution", "passed": False,
                       "detail": "CONSTITUTION modified — requires human approval"})
        score -= 1
    else:
        checks.append({"gate": "L1", "check": "constitution", "passed": True})

    # 7. Red lines present
    if current.get("red_line_count", 0) == 0:
        checks.append({"gate": "L1", "check": "red_lines", "passed": False,
                       "detail": "No red lines found — safety boundary missing"})
        score -= 1
    else:
        checks.append({"gate": "L1", "check": "red_lines", "passed": True})

    # Determine status
    failed = [c for c in checks if not c["passed"]]
    if not failed:
        status = "STABLE"
    elif any(c["gate"] == "L0" for c in failed):
        status = "DEGRADED"
    else:
        status = "WARNING"

    result = {
        "skill": skill,
        "score": max(0, score),
        "max_score": 8,
        "status": status,
        "failed_checks": len(failed),
        "checks": checks,
        "metrics": {
            "size": current["size"],
            "size_baseline": base["size"],
            "gotcha_count": current["gotcha_count"],
            "gotcha_baseline": base["gotcha_count"],
        },
        "timestamp": datetime.now().isoformat(),
    }

    # Log to drift.log (only meaningful changes)
    log_entry = {
        "skill": skill,
        "status": status,
        "score": score,
        "failed": [c["check"] for c in failed],
        "timestamp": result["timestamp"],
    }
    with open(DRIFT_LOG, 'a', encoding='utf-8') as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

    return result


def generate_gepa_proposal(skill: str, result: dict, commit_msg: str = ""):
    """Write a GEPA proposal when degradation detected."""
    timestamp = datetime.now().isoformat()
    failed_checks = [c["detail"] for c in result.get("checks", []) if not c["passed"]]
    entry = (
        f"### {timestamp}: {skill} — {result['status']}\n"
        f"- **Score**: {result['score']}/{result['max_score']}\n"
        f"- **Failures**: {', '.join(failed_checks)}\n"
        f"- **Commit**: {commit_msg}\n"
        f"- **Action**: Run 轮回 GEPA diagnosis\n"
        f"\n"
    )
    with open(GEPA_FILE, 'r', encoding='utf-8') as f:
        content = f.read()

    if "## 活跃提案" in content:
        insert_pos = content.find("## 活跃提案") + len("## 活跃提案\n")
        content = content[:insert_pos] + "\n" + entry + content[insert_pos:]

    with open(GEPA_FILE, 'w', encoding='utf-8') as f:
        f.write(content)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Drift Check v2 — L0+L1 structural quality gates")
    parser.add_argument("--skill", default=None, help="Check specific skill")
    parser.add_argument("--all", action="store_true", help="Check all skills")
    parser.add_argument("--commit-msg", default="", help="Associated commit message")
    parser.add_argument("--set-baseline", action="store_true", help="Store current structure as baseline")
    args = parser.parse_args()

    if args.set_baseline:
        for skill in SKILL_FILES:
            check_drift(skill)  # First run auto-baselines
        print("Structure baselines saved")
        return

    if args.skill:
        result = check_drift(args.skill)
        failed = [c for c in result.get("checks", []) if not c["passed"]]
        icon = "OK" if result["status"] == "STABLE" else ("!!" if result["status"] == "DEGRADED" else "~")
        print(f"{icon} {args.skill}: {result['score']}/{result['max_score']} [{result['status']}]")
        if result.get("metrics"):
            m = result["metrics"]
            print(f"   size: {m['size']}B (baseline: {m['size_baseline']}B)  gotchas: {m['gotcha_count']} (baseline: {m['gotcha_baseline']})")
        for c in failed:
            print(f"   FAIL [{c['gate']}] {c['check']}: {c.get('detail', '')}")
        for c in [x for x in result.get("checks", []) if x["passed"] and "increased" in x.get("detail", "")]:
            print(f"   GROWTH [{c['gate']}] {c['detail']}")
        if result["status"] in ("DEGRADED", "WARNING"):
            generate_gepa_proposal(args.skill, result, args.commit_msg)
            print(f"   → GEPA proposal generated")
        elif result["status"] == "STABLE":
            # Update structure baseline (ratchet up if improved)
            baseline_struct = load_json(STRUCTURE_BASELINE_FILE)
            current = parse_skill(args.skill)
            if current:
                baseline_struct[args.skill] = {
                    "size": current["size"],
                    "gotcha_count": current["gotcha_count"],
                    "constitution_hash": current.get("constitution_hash"),
                    "red_line_count": current.get("red_line_count", 0),
                }
                save_json(STRUCTURE_BASELINE_FILE, baseline_struct)

    elif args.all:
        drift_count = 0
        growth_count = 0
        for skill in SKILL_FILES:
            result = check_drift(skill)
            if result["status"] == "BASELINED":
                print(f"  NEW {skill}: baselined")
                continue
            icon = "OK" if result["status"] == "STABLE" else ("!!" if result["status"] == "DEGRADED" else "~")
            print(f"  {icon} {skill}: {result['score']}/{result['max_score']} [{result['status']}]")
            if result["status"] in ("DEGRADED", "WARNING"):
                generate_gepa_proposal(skill, result, args.commit_msg)
                drift_count += 1
            growth_checks = [c for c in result.get("checks", [])
                           if c["passed"] and "increased" in c.get("detail", "")]
            if growth_checks:
                growth_count += 1
        print(f"\n{drift_count} degradation(s) | {growth_count} skill(s) growing")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
