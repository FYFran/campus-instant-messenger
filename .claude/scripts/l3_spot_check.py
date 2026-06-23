"""
L3 Adversarial Spot-Check — Cross-model verification on random bugs.

Phase 3 of the flywheel: periodically sample benchmark results
and verify with a different model (Sonnet vs DeepSeek), flagging
REAL / REAL* / TEMPLATE / WRONG verdicts.

Usage:
  python l3_spot_check.py                    # Spot-check 3 random bugs
  python l3_spot_check.py --bugs 5           # Spot-check 5 bugs
  python l3_spot_check.py --skill 缉凶       # Spot-check specific skill
  python l3_spot_check.py --mode dry-run     # Show what would be checked

Architecture:
  1. Load recent benchmark results (per_bug_results.tsv)
  2. Pick N random bugs (weighted toward low scores)
  3. Generate cross-model verification prompt
  4. Agent reviews with adversarial lens ("try to refute the finding")
  5. Classify as REAL/REAL*/TEMPLATE/WRONG
  6. Update results with L3 verdict
"""

import json
import random
import sys
from datetime import datetime
from pathlib import Path
from collections import Counter

BENCH_DIR = Path(__file__).parent.parent / "benchmarks" / "bughunt"
RESULTS_FILE = BENCH_DIR / "per_bug_results.tsv"
L3_LOG = BENCH_DIR / "l3_verdicts.jsonl"

SKILL_BUG_PREFIX = {
    "缉凶": "B", "铁壁": "S", "明镜": "C", "布阵": "D",
    "门神": "Q", "破阵": "R", "火眼": "G", "试金石": "M",
}


def load_results() -> list[dict]:
    """Load recent benchmark results."""
    if not RESULTS_FILE.exists():
        print("No results file found.")
        return []

    lines = RESULTS_FILE.read_text(encoding="utf-8").strip().split("\n")
    if len(lines) < 2:
        return []

    headers = lines[0].split("\t")
    results = []
    for line in lines[1:]:
        if not line.strip():
            continue
        values = line.split("\t")
        result = dict(zip(headers, values))
        results.append(result)

    return results


def select_bugs(results: list[dict], n: int = 3,
                skill: str | None = None) -> list[dict]:
    """Select N bugs for L3 spot-check. Weight toward low scores."""
    if skill:
        prefix = SKILL_BUG_PREFIX.get(skill, "B")
        results = [r for r in results if r.get("bug_id", "").startswith(prefix)]

    if not results:
        return []

    # Weight: lower score = higher chance of being selected
    weighted = []
    for r in results:
        try:
            score = float(r.get("total", 8))
            weight = max(1, int((8 - score) * 3))  # Score 2→weight 18, Score 8→weight 1
        except (ValueError, TypeError):
            weight = 5
        weighted.extend([r] * weight)

    selected = random.sample(weighted, min(n, len(weighted)))
    return selected


def build_verification_prompt(bug: dict) -> str:
    """Build the cross-model verification prompt."""
    return f"""你是独立验证 agent — L3对抗审查。用批判性思维审查以下 bug report。
目标：找出误判。如果证据不足，标记 TEMPLATE。如果根因错误，标记 WRONG。

Bug ID: {bug.get('bug_id', 'N/A')}
Agent Type: {bug.get('agent_type', 'N/A')}
Agent Classification: {bug.get('gt_type', 'N/A')}
Total Score: {bug.get('total', 'N/A')}/8

审查问题:
1. 分类是否正确？有没有被 agent 的描述误导？
2. 证据是否具体可复现？还是模板化描述？
3. 根因定位是否准确？file:line 引用了确实存在的代码吗？
4. CF 是否有真实的 pre/post 数据对比？

返回 JSON:
{{"verdict": "REAL|REAL*|TEMPLATE|WRONG", "confidence": 0-100, "reason": "具体理由"}}

REAL = 完全正确。REAL* = 方向对细节偏差。TEMPLATE = 模板化输出无实质内容。WRONG = 根因错误。"""


def log_verdict(bug_id: str, verdict: str, confidence: int,
                reason: str = ""):
    """Append L3 verdict to log."""
    entry = {
        "bug_id": bug_id,
        "verdict": verdict,
        "confidence": confidence,
        "reason": reason,
        "timestamp": datetime.now().isoformat(),
    }
    L3_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(L3_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="L3 Adversarial Spot-Check")
    parser.add_argument("--bugs", type=int, default=3,
                        help="Number of bugs to spot-check (default: 3)")
    parser.add_argument("--skill", default=None,
                        help="Filter by skill name")
    parser.add_argument("--mode", default="prompt",
                        choices=["prompt", "dry-run"],
                        help="prompt=generate verification prompts, dry-run=show selection")
    args = parser.parse_args()

    results = load_results()
    if not results:
        print("No benchmark results to verify. Run L2 benchmark first.")
        return

    print(f"Loaded {len(results)} results.")

    selected = select_bugs(results, args.bugs, args.skill)
    if not selected:
        print("No bugs selected.")
        return

    print(f"\n{'='*50}")
    print(f"L3 Spot-Check: {len(selected)} bugs selected for verification")
    print(f"{'='*50}\n")

    if args.mode == "dry-run":
        for bug in selected:
            score = bug.get("total", "?")
            print(f"  {bug.get('bug_id', 'N/A')}: score={score}/8 "
                  f"type={bug.get('gt_type', '?')}")
        print(f"\nReady for L3 verification. Run without --dry-run to generate prompts.")
        return

    # Generate verification prompts
    prompts_file = BENCH_DIR / ".l3_prompts.json"
    prompts = {}
    for bug in selected:
        prompts[bug.get("bug_id", "N/A")] = build_verification_prompt(bug)

    prompts_file.write_text(
        json.dumps(prompts, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"Verification prompts written to: {prompts_file}")
    print(f"\nNext: spawn verification agents with these prompts.")
    print(f"Cross-model agents (Sonnet for DeepSeek, DeepSeek for Sonnet)")
    print(f"Then update results with L3 verdicts.")

    # Summary stats
    low_score = [r for r in selected
                 if float(r.get("total", 0)) < 5]
    if low_score:
        print(f"\n⚠️  {len(low_score)} bug(s) with score < 5 selected for priority review.")


if __name__ == "__main__":
    main()
