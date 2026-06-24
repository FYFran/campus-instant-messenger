"""
试剑石 SkillAxe 4维诊断器 — $0 自动分析

研究依据:
  SkillAxe (Microsoft, Jun 2026): "4-dimensional diagnosis to identify
    which aspect of a skill needs improvement, eliminating 90% of
    manual GEPA optimization effort."
  GEPA (ICLR 2026 Oral): "Generate→Evaluate→Prune→Apply loop for
    autonomous skill optimization."

4 维度:
  1. Quality impact: bare vs skill delta per bug
  2. Trigger precision: T-Type accuracy rate
  3. Instruction compliance: chain completeness
  4. Solution-path coverage: root_cause hit rate

弱维度 → 候选 F-rule 生成方向

用法:
  python skillaxe_diagnose.py            # 全量诊断
  python skillaxe_diagnose.py --suggest  # 生成改进候选
"""

import sys
from pathlib import Path
from collections import defaultdict

BENCH_DIR = Path(__file__).parent
PER_BUG_FILE = BENCH_DIR / "per_bug_results.tsv"


def load_per_bug():
    if not PER_BUG_FILE.exists():
        return []
    lines = PER_BUG_FILE.read_text(encoding="utf-8").strip().split("\n")
    if len(lines) < 2:
        return []
    headers = lines[0].split("\t")
    return [dict(zip(headers, l.split("\t"))) for l in lines[1:] if l.strip()]


def diagnose():
    rows = load_per_bug()
    if not rows:
        print("No per-bug data.")
        return None

    # Group by bug_id, pick latest run
    latest = {}
    for r in rows:
        bid = r.get("bug_id", "")
        if not bid or not bid.startswith("B"):
            continue
        ts = r.get("timestamp", "0")
        if bid not in latest or ts > latest[bid]["timestamp"]:
            latest[bid] = r

    n = len(latest)
    if n == 0:
        print("No bugs with data.")
        return None

    # Dimension 1: Quality impact — avg score per bug
    scores = []
    for bid, r in latest.items():
        try:
            scores.append(int(r.get("total", 0)))
        except (ValueError, TypeError):
            continue
    dim1_mean = sum(scores) / len(scores) if scores else 0

    # Dimension 2: Trigger precision — T-Type accuracy
    ttype_hits = 0
    for bid, r in latest.items():
        gt = r.get("gt_type", "")
        at = r.get("agent_type", "")
        # Check if agent type starts with same "T"
        if at.startswith("T") and gt.startswith("T"):
            if at[0:2] == gt[0:2]:
                ttype_hits += 1
            elif at == "T_AUTH" or at == "T9":
                pass  # Misclassification
    dim2_rate = ttype_hits / n if n > 0 else 0

    # Dimension 3: Instruction compliance — chain completeness
    chain_ok = 0
    for bid, r in latest.items():
        try:
            if int(r.get("score_chain", 0)) >= 1:
                chain_ok += 1
        except (ValueError, TypeError):
            pass
    dim3_rate = chain_ok / n if n > 0 else 0

    # Dimension 4: Solution-path coverage — root_cause hit rate
    root_hits = 0
    root_partial = 0
    for bid, r in latest.items():
        try:
            rc = int(r.get("score_root", -1))
            if rc >= 2:
                root_hits += 1
            elif rc >= 1:
                root_partial += 1
        except (ValueError, TypeError):
            pass
    dim4_rate = root_hits / n if n > 0 else 0
    dim4_any = (root_hits + root_partial) / n if n > 0 else 0

    # Per-bug root_cause failure analysis
    root_failures = []
    for bid, r in sorted(latest.items()):
        try:
            rc = int(r.get("score_root", -1))
            gt = r.get("gt_type", "?")
            at = r.get("agent_type", "?")
            total = int(r.get("total", 0))
            if rc == 0:
                root_failures.append({
                    "bug_id": bid,
                    "gt_type": gt,
                    "agent_type": at,
                    "total": total,
                    "notes": r.get("notes", ""),
                })
        except (ValueError, TypeError):
            continue

    # Find weakest dimension
    dims = {
        "D1_quality_impact": dim1_mean,
        "D2_trigger_precision": dim2_rate,
        "D3_instruction_compliance": dim3_rate,
        "D4_solution_coverage": dim4_rate,
    }
    weakest = min(dims, key=dims.get)

    return {
        "n": n,
        "dims": dims,
        "weakest": weakest,
        "root_failures": root_failures,
        "dim1_mean": dim1_mean,
        "dim2_rate": dim2_rate,
        "dim3_rate": dim3_rate,
        "dim4_rate": dim4_rate,
        "dim4_any": dim4_any,
    }


def print_diagnosis(d: dict):
    if not d:
        return

    print(f"""
{'='*60}
 SkillAxe 4-Dim Diagnosis — Microsoft Jun 2026
 Bugs analyzed: {d['n']}
{'='*60}

  D1 Quality Impact:  mean={d['dim1_mean']:.1f}/8
  D2 Trigger Precision: T-Type={d['dim2_rate']:.0%}
  D3 Instruction Compliance: chain={d['dim3_rate']:.0%}
  D4 Solution Coverage: root_hit={d['dim4_rate']:.0%} (any={d['dim4_any']:.0%})

  Weakest dimension: {d['weakest']}
""")

    if d["root_failures"]:
        print(f"  Root cause failures ({len(d['root_failures'])} bugs, score_root=0):")
        for f in d["root_failures"]:
            print(f"    {f['bug_id']} ({f['gt_type']}→{f['agent_type']}): total={f['total']}/8 | {f['notes'][:80]}")


def suggest():
    """Generate improvement candidates from diagnosis."""
    d = diagnose()
    if not d:
        return

    print_diagnosis(d)

    print(f"{'='*60}")
    print(" Improvement Candidates (GEPA-style)")
    print(f"{'='*60}\n")

    candidates = []

    # If D4 is weakest (most common): root cause coverage gap
    if d["weakest"] == "D4_solution_coverage" and d["root_failures"]:
        # Group failures by GT type
        by_type = defaultdict(list)
        for f in d["root_failures"]:
            by_type[f["gt_type"]].append(f["bug_id"])

        for gt, bids in sorted(by_type.items()):
            candidates.append({
                "trigger": f"Root cause blind on {gt} bugs: {', '.join(bids)}",
                "direction": f"Add {gt}-specific root cause tracing to skill. "
                           f"Agent correctly classifies but cannot find root cause.",
                "cost": 0.15,
                "validate_on": bids,
            })

    # If D2 is weakest: trigger precision
    if d["weakest"] == "D2_trigger_precision":
        candidates.append({
            "trigger": f"T-Type accuracy {d['dim2_rate']:.0%}",
            "direction": "Review F1-F7 fatal misclassification patterns. "
                       "May need new F-rule for emerging misclassification.",
            "cost": 0.05,
            "validate_on": ["all"],
        })

    # If D3 is weakest: instruction compliance
    if d["weakest"] == "D3_instruction_compliance":
        candidates.append({
            "trigger": f"Chain incomplete rate {(1-d['dim3_rate']):.0%}",
            "direction": "Tighten contract chain gates. Add auto-verification of step outputs.",
            "cost": 0.05,
        })

    for i, c in enumerate(candidates):
        print(f"  F{i+9}: [{c['trigger']}]")
        print(f"       → {c['direction']}")
        print(f"       Cost: ${c['cost']:.2f} | Validate on: {', '.join(c['validate_on'])}")
        print()

    if not candidates:
        print("  All dimensions at ceiling. No candidates generated.")
        print("  → Switch to maintenance mode or expand bug types.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--suggest":
        suggest()
    else:
        d = diagnose()
        print_diagnosis(d)
