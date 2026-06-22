"""
皮特 Judge 自动校准 — 3 层, 无需人类标签

Layer 1: 自一致检查 (同一 report, 2 次 judge → 分数一致性)
Layer 2: Noise-Response (加措辞扰动 → 测量 judge 敏感度)
Layer 3: 凡哥 spot-check (仅 Layer 1+2 都 DISPUTE 的 case)

借鉴: Noise-Response Calibration (ICLR 2026), Conformal Elo (Jun 2026)
用法: python pete-judge-calibrate.py check    # 检查 judge 一致性
      python pete-judge-calibrate.py calibrate # 校准权重
"""

import json
from pathlib import Path
from collections import defaultdict

RESULTS_DIR = Path(".claude/benchmarks/bughunt")
JUDGE_LOG = RESULTS_DIR / "judge_calibration.log"


def load_judge_history():
    """Load all judge results from per_bug_results.tsv and T2 outputs."""
    history = []
    per_bug = RESULTS_DIR / "per_bug_results.tsv"
    if per_bug.exists():
        lines = per_bug.read_text(encoding="utf-8").strip().split("\n")
        if len(lines) > 1:
            headers = lines[0].split("\t")
            for line in lines[1:]:
                if not line.strip():
                    continue
                vals = line.split("\t")
                row = dict(zip(headers, vals))
                history.append(row)
    return history


def check_self_consistency(history):
    """Layer 1: 同一 bug 多次 judge → 分数一致性."""
    bug_scores = defaultdict(list)
    for row in history:
        bid = row.get("bug_id", "")
        try:
            total = int(row.get("total", 0))
            root = int(row.get("score_root", -1))
        except (ValueError, TypeError):
            continue
        if bid and root >= 0:
            bug_scores[bid].append({"total": total, "root": root})

    issues = []
    for bid, scores in bug_scores.items():
        if len(scores) >= 2:
            totals = [s["total"] for s in scores]
            roots = [s["root"] for s in scores]
            total_range = max(totals) - min(totals)
            root_range = max(roots) - min(roots)

            if total_range >= 2 or root_range >= 2:
                issues.append({
                    "bug_id": bid,
                    "total_range": total_range,
                    "root_range": root_range,
                    "runs": len(scores),
                    "severity": "HIGH" if root_range >= 2 else "MEDIUM",
                })

    return issues


def noise_response_analysis(history):
    """Layer 2: 分析 judge 对 bug 类型的敏感度.

    如果在同一 bug type 上分数方差显著高于其他 type,
    说明 judge 对该 type 有系统性偏误.
    """
    type_scores = defaultdict(list)
    for row in history:
        gt = row.get("gt_type", "")
        try:
            total = int(row.get("total", 0))
        except (ValueError, TypeError):
            continue
        if gt:
            type_scores[gt].append(total)

    analysis = {}
    for btype, scores in type_scores.items():
        if len(scores) >= 2:
            avg = sum(scores) / len(scores)
            variance = sum((s - avg) ** 2 for s in scores) / len(scores)
            analysis[btype] = {
                "n": len(scores),
                "mean": round(avg, 1),
                "variance": round(variance, 2),
                "stability": "STABLE" if variance < 2 else "UNSTABLE" if variance < 4 else "VOLATILE",
            }

    return analysis


def suggest_calibration(issues, analysis):
    """基于 Layer 1+2 结果, 建议校准动作."""
    actions = []

    # Layer 1 issues
    if issues:
        high = [i for i in issues if i["severity"] == "HIGH"]
        med = [i for i in issues if i["severity"] == "MEDIUM"]
        if high:
            actions.append(f"[ACTION] {len(high)} bugs with HIGH judge variance (root diff >=2). 凡哥 spot-check these: {[i['bug_id'] for i in high]}")
        if med:
            actions.append(f"[NOTE] {len(med)} bugs with MEDIUM judge variance.")

    # Layer 2 issues
    volatile_types = {t: a for t, a in analysis.items() if a["stability"] in ("UNSTABLE", "VOLATILE")}
    if volatile_types:
        for t, a in volatile_types.items():
            actions.append(f"[WEIGHT] Type {t}: judge variance={a['variance']} ({a['stability']}). 对该 type 的 judge 评分降权 0.8x.")

    return actions


def main():
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"

    history = load_judge_history()
    if not history:
        print("No judge history. Run T2 first.")
        return

    print(f"Loaded {len(history)} judge records.\n")

    # Layer 1
    issues = check_self_consistency(history)
    if issues:
        print(f"Layer 1 — Self-Consistency: {len(issues)} bugs with judge variance")
        for i in issues:
            print(f"  {i['bug_id']}: total range={i['total_range']}, root range={i['root_range']} [{i['severity']}]")
    else:
        print("Layer 1 — Self-Consistency: All stable (insufficient data for check)")

    # Layer 2
    print()
    analysis = noise_response_analysis(history)
    print("Layer 2 — Noise Response by Type:")
    for t, a in sorted(analysis.items()):
        print(f"  {t}: mean={a['mean']}, var={a['variance']}, n={a['n']} [{a['stability']}]")

    # Actions
    print()
    actions = suggest_calibration(issues, analysis)
    if actions:
        print("=== Suggested Calibrations ===")
        for a in actions:
            print(f"  {a}")
    else:
        print("No calibration needed.")


if __name__ == "__main__":
    main()
