"""
试剑石 Judge Layer 1 — 自一致校准器 (Self-Consistency Calibrator)

研究依据:
  FINAL_DESIGN.md §2: "同一 report 跑 2 次 Sonnet judge → 分数不同 → DISPUTE"
  Noise-Response Calibration (Mar 2026): 加受控噪声→测量 judge 敏感度→校准
  Conformal Elo (Jun 2026): 概率化 Elo + 共形预测 → 17.9 MAE

原理: LLM judge 有固有随机性。同输入判两次，分数相同=高置信，
      分数不同=该 case 的 judge 评分不可靠，标记 DISPUTE。

用法:
  python judge_calibrate.py check              # 检查现有 judge 结果的一致性
  python judge_calibrate.py calibrate          # 对所有 bug 跑自一致校准
  python judge_calibrate.py stats              # 显示校准统计
"""

import json
import re
import sys
from pathlib import Path
from datetime import datetime
from collections import defaultdict

BENCH_DIR = Path(__file__).parent
PER_BUG_FILE = BENCH_DIR / "per_bug_results.tsv"
CALIBRATION_FILE = BENCH_DIR / "judge_calibration.json"
GROWTH_LOG = BENCH_DIR / "growth.log"


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(GROWTH_LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_per_bug():
    """Load per-bug results."""
    if not PER_BUG_FILE.exists():
        return []
    lines = PER_BUG_FILE.read_text(encoding="utf-8").strip().split("\n")
    if len(lines) < 2:
        return []
    headers = lines[0].split("\t")
    return [dict(zip(headers, l.split("\t"))) for l in lines[1:] if l.strip()]


def load_calibration():
    """Load existing calibration data."""
    if CALIBRATION_FILE.exists():
        return json.loads(CALIBRATION_FILE.read_text(encoding="utf-8"))
    return {"runs": [], "stats": {}}


def save_calibration(data: dict):
    CALIBRATION_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def judge_prompt(bug_data: dict) -> str:
    """Build judge prompt from per-bug result data.

    This simulates what a Sonnet judge would receive during T2 scoring.
    In production, this would call the actual Sonnet model via API.
    For now, it returns the prompt that WOULD be sent.
    """
    return f"""评分 bug {bug_data.get('bug_id','?')}。

GT Type: {bug_data.get('gt_type','?')}
Agent Type: {bug_data.get('agent_type','?')}
Score class: {bug_data.get('score_class','?')}
Score chain: {bug_data.get('score_chain','?')}
Score evidence: {bug_data.get('score_evidence','?')}
Score root: {bug_data.get('score_root','?')}
Score cf: {bug_data.get('score_cf','?')}
Score fix: {bug_data.get('score_fix','?')}
Total: {bug_data.get('total','?')}
Notes: {bug_data.get('notes','?')}

请独立评分 (0-7):
- 分类正确? (0|1)
- 链完整? (0|1)
- 证据充分? (0|1)
- 根因正确? (0|1|2)
- CF 可验证? (0|1)
- 修复正确? (0|1)
- 总评: ___

只返回 JSON: {{"class":0|1, "chain":0|1, "evidence":0|1, "root":0|1|2, "cf":0|1, "fix":0|1, "total":0-7}}"""


def check_consistency():
    """Check if any existing calibration data shows inconsistency.

    Returns list of bugs with disputed scores (judge disagreed with itself).
    """
    data = load_calibration()
    runs = data.get("runs", [])
    if not runs:
        log("No calibration data yet. Run 'calibrate' first.")
        return []

    # Group by bug_id
    by_bug = defaultdict(list)
    for r in runs:
        by_bug[r["bug_id"]].append(r)

    disputes = []
    for bid, entries in by_bug.items():
        if len(entries) >= 2:
            scores = [e["scores"]["total"] for e in entries]
            if len(set(scores)) > 1:
                disputes.append({
                    "bug_id": bid,
                    "scores": scores,
                    "severity": max(scores) - min(scores),
                })

    return disputes


def compute_stats():
    """Compute calibration statistics from existing data."""
    data = load_calibration()
    runs = data.get("runs", [])

    if not runs:
        return {"total_judgments": 0, "dispute_rate": 0, "mean_gap": 0}

    by_bug = defaultdict(list)
    for r in runs:
        by_bug[r["bug_id"]].append(r)

    total = len(by_bug)
    disputes = 0
    gaps = []

    for bid, entries in by_bug.items():
        if len(entries) >= 2:
            scores = [e["scores"]["total"] for e in entries]
            if len(set(scores)) > 1:
                disputes += 1
                gaps.append(max(scores) - min(scores))

    return {
        "total_judgments": total,
        "pairs_with_2plus": sum(1 for v in by_bug.values() if len(v) >= 2),
        "disputes": disputes,
        "dispute_rate": disputes / max(total, 1),
        "mean_gap": sum(gaps) / max(len(gaps), 1) if gaps else 0,
        "calibration_quality": "GOOD" if disputes / max(total, 1) < 0.1 else "NEEDS_WORK",
    }


def print_report():
    """Print calibration report."""
    stats = compute_stats()
    disputes = check_consistency()

    print(f"""
{'='*60}
 Judge Layer 1 — 自一致校准器
 研究: Noise-Response Calibration (Mar 2026)
 原理: 同输入判 2 次 → 分数不同 = DISPUTE
{'='*60}

Calibration Stats:
  Total bugs judged:      {stats['total_judgments']}
  Bugs with 2+ judgments: {stats['pairs_with_2plus']}
  Disputes found:         {stats['disputes']}
  Dispute rate:           {stats['dispute_rate']:.0%}
  Mean score gap:         {stats['mean_gap']:.1f}
  Calibration quality:    {stats['calibration_quality']}
""")

    if disputes:
        print("Disputed bugs (judge self-disagreement):")
        for d in disputes:
            print(f"  {d['bug_id']}: scores={d['scores']}, gap={d['severity']}")
        print()

    # Target: <10% dispute rate (Noise-Response paper standard)
    target = 0.10
    if stats['dispute_rate'] > target:
        print(f"  [!] Dispute rate {stats['dispute_rate']:.0%} > {target:.0%} target.")
        print(f"  → Judge calibration needed. Consider Layer 2 (noise-response)")
        print(f"     or Layer 3 (凡哥 spot-check for disputed cases).")
    else:
        print(f"  [OK] Dispute rate {stats['dispute_rate']:.0%} < {target:.0%} target.")


def record_judgment(bug_id: str, scores: dict, judge_model: str = "sonnet"):
    """Record a single judge scoring for calibration tracking.

    Call this twice per bug to build self-consistency data.
    """
    data = load_calibration()
    data["runs"].append({
        "bug_id": bug_id,
        "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "judge_model": judge_model,
        "scores": scores,
    })
    save_calibration(data)
    return data


def verify_existing():
    """Check per_bug_results for existing score patterns that suggest inconsistency.

    This is a static check — no LLM calls needed. Reads existing data
    and looks for patterns where the scoring seems inconsistent.
    """
    results = load_per_bug()
    if not results:
        print("No per_bug_results data found.")
        return

    # Check: same GT type, same agent type, but very different total scores
    by_type = defaultdict(list)
    for r in results:
        key = (r.get("gt_type", "?"), r.get("agent_type", "?"))
        by_type[key].append(r)

    print(f"\n{'='*60}")
    print(f" Static Consistency Check (existing data, $0 cost)")
    print(f" 同 GT Type + 同 Agent Type → 分数应接近")
    print(f"{'='*60}\n")

    issues = 0
    for (gt, at), entries in sorted(by_type.items()):
        if len(entries) < 2:
            continue
        scores = [int(e.get("total", 0)) for e in entries]
        score_range = max(scores) - min(scores)
        if score_range >= 3:
            print(f"  [!] ({gt}, {at}): scores={scores}, range={score_range}")
            print(f"      → Wide score range for same type pair. Possible judge inconsistency.")
            issues += 1

    if issues == 0:
        print("  [OK] All type-pair scores within 2pt range. Static consistency OK.")
    else:
        print(f"\n  {issues} type-pairs with wide score range. Judge calibration recommended.")

    return issues


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"

    if cmd == "check":
        disputes = check_consistency()
        if not disputes:
            print("No calibration data. Run static check instead:")
        verify_existing()

    elif cmd == "calibrate":
        log("Starting Judge Layer 1 calibration...")
        # NOTE: Full calibration requires Sonnet API calls.
        # For now, runs static consistency check (free).
        verify_existing()
        print("\n  Full LLM calibration: use record_judgment() per T2 run.")
        print("  Each T2 judge call → record_judgment() twice → build calibration DB.")

    elif cmd == "stats":
        print_report()

    elif cmd == "record":
        # Manual recording: python judge_calibrate.py record B01 '{"class":1,"chain":1,"evidence":1,"root":2,"cf":1,"fix":1,"total":7}'
        if len(sys.argv) < 4:
            print("Usage: python judge_calibrate.py record <bug_id> '<json_scores>'")
            sys.exit(1)
        bug_id = sys.argv[2]
        scores = json.loads(sys.argv[3])
        record_judgment(bug_id, scores)
        print(f"Recorded: {bug_id} -> {scores}")

    else:
        print("Usage: python judge_calibrate.py [check|calibrate|stats|record]")
