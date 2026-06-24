"""
BugHuntBench CI Gate — 门禁脚本.

三层管线:
  quick  (每次 commit)  — 规则评分，<1s，零 token
  full   (每晚)         — LLM judge 评分
  verify (每周/PR前)    — cross-model 3-judge consensus + L3 spot-check

用法:
  python bughunt_ci.py --mode quick           # CI fast gate
  python bughunt_ci.py --mode full --bugs all  # Nightly regression
  python bughunt_ci.py --mode verify            # Pre-release gate
  python bughunt_ci.py --list                   # List available bugs
  python bughunt_ci.py --summary                # Show latest results
"""

import sys
from datetime import datetime
from pathlib import Path

# Ensure we can import from this directory
sys.path.insert(0, str(Path(__file__).parent))

from bughunt_harness import (
    load_bugs, parse_agent_report, score_by_rules,
    append_result, load_results, generate_summary,
    AgentReport, ScoreCard, BugSpec, RESULTS_FILE, BENCH_DIR,
    SKILL_PREFIX,
)
from auto_scorer import AutoScorer


# --- CI Gate Thresholds ---

GATE_THRESHOLDS = {
    "quick": {
        "min_classification_rate": 0.6,    # At least 60% T-Type correct
        "min_chain_rate": 0.9,              # At least 90% chain complete
        "min_trace_rate": 0.8,              # At least 80% trace compliant
        "min_avg_score": 4.0,               # Average score >= 4/8
        "max_l3_wrong": 0,                  # Zero L3 WRONG
    },
    "full": {
        "min_classification_rate": 0.7,
        "min_chain_rate": 0.95,
        "min_avg_score": 5.0,
        "min_root_hit_rate": 0.5,           # At least 50% root cause correct
        "max_l3_template": 2,                # Max 2 TEMPLATE verdicts
    },
    "verify": {
        "min_classification_rate": 0.8,
        "min_chain_rate": 1.0,
        "min_avg_score": 6.0,
        "min_root_hit_rate": 0.7,
        "max_l3_template": 0,               # Zero TEMPLATE in verify
        "min_l3_real_rate": 0.7,            # At least 70% REAL or REAL*
    },
}


# --- Gate Checker ---


class CIGate:
    """CI gate that checks benchmark results against thresholds."""

    def __init__(self, mode: str = "quick"):
        self.mode = mode
        self.thresholds = GATE_THRESHOLDS.get(mode, GATE_THRESHOLDS["quick"])
        self.checks: list[dict] = []
        self.passed = True

    def check(self, cards: list[ScoreCard]) -> bool:
        """Run all threshold checks against score cards.

        Returns True if all checks pass.
        """
        n = len(cards)
        if n == 0:
            self.checks.append({"name": "no_results", "passed": False,
                               "detail": "No results to check"})
            self.passed = False
            return False

        avg_score = sum(c.total for c in cards) / n
        class_ok = sum(1 for c in cards if c.score_classification == 1)
        chain_ok = sum(1 for c in cards if c.score_chain == 1)
        trace_ok = sum(1 for c in cards if c.score_trace == 1)
        root_hit = sum(1 for c in cards if c.score_root_cause == 2)
        l3_wrong = sum(1 for c in cards if c.l3_verdict == "WRONG")
        l3_template = sum(1 for c in cards if "TEMPLATE" in c.l3_verdict)
        l3_real = sum(1 for c in cards if "REAL" in c.l3_verdict)

        checks = [
            ("T-Type Rate", class_ok / n, self.thresholds.get("min_classification_rate", 0)),
            ("Chain Rate", chain_ok / n, self.thresholds.get("min_chain_rate", 0)),
            ("Trace Rate", trace_ok / n, self.thresholds.get("min_trace_rate", 0)),
            ("Avg Score", avg_score, self.thresholds.get("min_avg_score", 0)),
            ("L3 WRONG", l3_wrong, self.thresholds.get("max_l3_wrong", 0), True),
            ("Root Hit Rate", root_hit / n, self.thresholds.get("min_root_hit_rate", 0)),
            ("L3 TEMPLATE", l3_template, self.thresholds.get("max_l3_template", 0), True),
            ("L3 REAL Rate", l3_real / n, self.thresholds.get("min_l3_real_rate", 0)),
        ]

        for name, actual, threshold, *opts in checks:
            is_max = opts[0] if opts else False
            if is_max:
                passed = actual <= threshold
            else:
                passed = actual >= threshold

            self.checks.append({
                "name": name,
                "passed": passed,
                "actual": actual,
                "threshold": threshold,
                "detail": f"{name}: {actual:.2f} {'<=' if is_max else '>='} {threshold}",
            })
            if not passed:
                self.passed = False

        return self.passed

    def report(self) -> str:
        """Generate a gate check report."""
        status = "PASS" if self.passed else "FAIL"
        lines = [
            f"=== BugHuntBench CI Gate [{self.mode}] — {status} ===",
            "",
        ]

        for c in self.checks:
            icon = "[OK]" if c["passed"] else "[FAIL]"
            lines.append(f"  {icon} {c['detail']}")

        lines.append("")
        lines.append(f"Gate: {status}")
        return "\n".join(lines)


# --- CLI ---


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="BugHuntBench CI Gate — Agent Skill 门禁脚本"
    )
    parser.add_argument("--mode", default="quick",
                       choices=["quick", "full", "verify"],
                       help="CI mode (default: quick)")
    parser.add_argument("--skill", default=None,
                       help="Skill name (铁壁/明镜/布阵/门神/破阵/缉凶). Filters bugs by prefix.")
    parser.add_argument("--baseline", default=None,
                       help="Path to baseline TSV for drift detection")
    parser.add_argument("--max-drift", type=float, default=5.0,
                       help="Max allowed score drift percentage (default: 5%%)")
    parser.add_argument("--bugs", default="all",
                       help="Bug IDs or 'all'")
    parser.add_argument("--output", default=str(RESULTS_FILE),
                       help="Results file path")
    parser.add_argument("--list", action="store_true",
                       help="List bugs")
    parser.add_argument("--summary", action="store_true",
                       help="Show summary of latest run")
    parser.add_argument("--gate-only", action="store_true",
                       help="Only check gate against existing results")

    args = parser.parse_args()

    # List mode
    if args.list:
        bugs = load_bugs()
        print(f"{len(bugs)} bugs available:")
        for b in bugs:
            print(f"  {b.id} {b.type_gt} ({b.language}, {b.difficulty})")
        return

    # Summary mode
    if args.summary:
        results = load_results(Path(args.output))
        if not results:
            print("No results found.")
            return

        # Group by timestamp
        runs = {}
        for r in results:
            ts = r.get("timestamp", "unknown")[:10]  # Group by date
            if ts not in runs:
                runs[ts] = []
            runs[ts].append(r)

        print(f"Total results: {len(results)} across {len(runs)} runs\n")
        for ts, run_results in sorted(runs.items()):
            total = sum(int(r.get("total", 0)) for r in run_results)
            max_s = len(run_results) * 8
            pct = total / max_s * 100 if max_s > 0 else 0
            print(f"  {ts}: {total}/{max_s} = {pct:.1f}% ({len(run_results)} bugs)")
        return

    # Gate-only mode: check existing results
    if args.gate_only:
        results = load_results(Path(args.output))
        if not results:
            print("FAIL: No results found.")
            sys.exit(1)

        # Get latest run
        timestamps = sorted(set(r.get("timestamp", "") for r in results), reverse=True)
        latest = timestamps[0]
        latest_results = [r for r in results if r.get("timestamp") == latest]

        cards = []
        for r in latest_results:
            card = ScoreCard(
                bug_id=r.get("bug_id", ""),
                score_classification=int(r.get("classification", 0)),
                score_chain=int(r.get("chain_complete", 0)),
                score_evidence=int(r.get("evidence", 0)),
                score_root_cause=int(r.get("root_cause", 0)),
                score_cf=int(r.get("cf", 0)),
                score_fix=int(r.get("fix", 0)),
                score_trace=int(r.get("trace", 0)),
                l3_verdict=r.get("l3_verdict", "NOT_RUN"),
            )
            cards.append(card)

        gate = CIGate(args.mode)
        passed = gate.check(cards)
        print(gate.report())
        sys.exit(0 if passed else 1)

    # Run mode: execute benchmark
    bug_ids = None if args.bugs == "all" else [b.strip() for b in args.bugs.split(",")]
    bugs = load_bugs(bug_ids)

    # Filter by skill if --skill specified
    if args.skill:
        prefix = SKILL_PREFIX.get(args.skill)
        if prefix:
            bugs = [b for b in bugs if b.id.startswith(prefix)]
            print(f"Skill filter: {args.skill} ({prefix}##) → {len(bugs)} bugs")
        else:
            print(f"Unknown skill: {args.skill}. Known: {list(SKILL_PREFIX.keys())}")
            sys.exit(1)

    if not bugs:
        print(f"No bugs found: {args.bugs} (skill={args.skill})")
        sys.exit(1)

    print(f"BugHuntBench CI [{args.mode}] — {len(bugs)} bugs\n")

    cards = []
    for bug in bugs:
        print(f"  Processing {bug.id} ({bug.type_gt})...")

        # NOTE: In production, this is where we spawn an agent and collect output.
        # For now, this is a placeholder showing the integration point.
        # The actual agent execution is done by Claude Code's Agent tool.
        # See DESIGN_v2.md Section 6 for the full Harness architecture.

        # Placeholder: create empty report
        report = AgentReport(
            bug_id=bug.id,
            raw_output=f"[PLACEHOLDER] Run agent for {bug.id}",
        )

        scorer = AutoScorer(mode=args.mode)
        card = scorer.score(report, bug)
        cards.append(card)
        append_result(card, bug, filepath=Path(args.output))

        print(f"    Score: {card.total}/{card.max_score} — {card.notes}")

    # Gate check
    gate = CIGate(args.mode)
    passed = gate.check(cards)

    print()
    print(gate.report())

    # Baseline drift detection
    if args.baseline:
        baseline_path = Path(args.baseline)
        if baseline_path.exists():
            baseline_results = load_results(baseline_path)
            if baseline_results:
                # Compute average scores
                curr_avg = sum(c.total for c in cards) / len(cards)
                base_scores = {}
                for r in baseline_results:
                    bid = r.get("bug_id", "")
                    base_scores[bid] = int(r.get("total", 0))

                # Per-bug drift
                drifts = []
                for c in cards:
                    if c.bug_id in base_scores:
                        drift = c.total - base_scores[c.bug_id]
                        drifts.append((c.bug_id, base_scores[c.bug_id], c.total, drift))

                base_avg = sum(base_scores.values()) / len(base_scores) if base_scores else 0
                avg_drift_pct = ((curr_avg - base_avg) / base_avg * 100) if base_avg > 0 else 0

                print(f"\n=== Baseline Drift [{baseline_path.name}] ===")
                print(f"  Baseline avg: {base_avg:.1f}  Current avg: {curr_avg:.1f}  Drift: {avg_drift_pct:+.1f}%")
                for bid, base, curr, drift in drifts:
                    icon = "++" if drift > 0 else ("--" if drift < 0 else "~~")
                    print(f"  {icon} {bid}: {base}→{curr} ({drift:+d})")

                if avg_drift_pct < -args.max_drift:
                    print(f"\n  DRIFT FAIL: Score dropped {abs(avg_drift_pct):.1f}% > {args.max_drift}% threshold")
                    passed = False
                else:
                    print(f"  DRIFT OK: within {args.max_drift}% threshold")
        else:
            print(f"\nBaseline file not found: {args.baseline}")

    # Summary
    summary = generate_summary(cards)
    summary_path = BENCH_DIR / f"SUMMARY_{datetime.now().strftime('%Y%m%d_%H%M')}.md"

    print(f"\nSummary written to: {summary_path}")
    print(f"Results appended to: {args.output}")

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
