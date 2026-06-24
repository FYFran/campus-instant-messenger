"""
BugHuntBench Full Runner — 完整自动跑分.

整合三层:
  1. Agent spawn (通过 Claude Code Agent tool)
  2. Auto scoring (规则 + LLM judge)
  3. Report generation + CI gate

用法:
  python bughunt_run.py --bugs B01,B02,B03 --mode quick
  python bughunt_run.py --bugs all --mode full
  python bughunt_run.py --gate-only
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))

from bughunt_harness import (
    load_bugs, parse_agent_report, score_by_rules,
    append_result, load_results, generate_summary,
    AgentReport, ScoreCard, BugSpec, RESULTS_FILE, BENCH_DIR,
    build_agent_prompt, build_judge_prompt,
)
from auto_scorer import AutoScorer, JudgeVerdict, ConsensusResult


class BugHuntRunner:
    """Full benchmark runner — orchestrates investigation + scoring + reporting."""

    def __init__(self, mode: str = "quick", bugs: Optional[list[str]] = None):
        self.mode = mode
        self.bugs = load_bugs(bugs)
        self.scorer = AutoScorer(mode=mode)
        self.results: list[ScoreCard] = []
        self.reports: list[AgentReport] = []
        self.judge_consensus: dict[str, dict] = {}
        self.start_time = None

    @property
    def bug_count(self) -> int:
        return len(self.bugs)

    def run(self) -> dict:
        """Execute the full benchmark.

        Returns dict with:
            total_score, max_score, percentage, bugs_run, gate, scores, report
        """
        self.start_time = datetime.now()
        print(f"BugHuntBench v2.0 [{self.mode}] — {self.bug_count} bugs\n")

        # Phase 1: Agent prompts (for Claude Code to execute)
        prompts = {}
        for bug in self.bugs:
            prompts[bug.id] = build_agent_prompt(bug, "缉凶")

        print(f"Generated {len(prompts)} investigation prompts.")
        print("\n--- AGENT EXECUTION NEEDED ---")
        print("Use the following prompts with Claude Code Agent tool:")
        print("  For each bug: Agent(type='debugger', prompt=prompts[bug_id])")
        print("  Or use: Workflow({scriptPath: 'bughunt_workflow.js'})")
        print("--- END AGENT EXECUTION ---\n")

        # The agent outputs would be fed back in. For demonstration,
        # output the prompts as JSON for integration.
        prompts_file = BENCH_DIR / ".agent_prompts.json"
        prompts_file.write_text(
            json.dumps(prompts, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        print(f"Prompts written to: {prompts_file}")

        return {
            "status": "ready",
            "bugs_loaded": self.bug_count,
            "prompts_file": str(prompts_file),
            "mode": self.mode,
        }

    def process_agent_outputs(self, outputs: dict[str, str]) -> list[ScoreCard]:
        """Process agent outputs: parse → score → record.

        Args:
            outputs: {bug_id: agent_output_text}

        Returns:
            List of ScoreCards
        """
        results = []
        bugs_by_id = {b.id: b for b in self.bugs}

        for bug_id, raw_output in outputs.items():
            bug = bugs_by_id.get(bug_id)
            if not bug:
                print(f"  WARNING: Unknown bug {bug_id}, skipping")
                continue

            # Parse agent report
            report = parse_agent_report(raw_output, bug_id)
            self.reports.append(report)

            # Score
            card = self.scorer.score(report, bug)
            results.append(card)

            # Record
            append_result(card, bug)

            icon = "OK" if card.total >= 5 else ("WARN" if card.total >= 3 else "FAIL")
            print(f"  {bug_id} {icon}: {card.total}/{card.max_score} | {card.notes[:60]}")

        self.results = results
        return results

    def run_judges(self, max_bugs: int = 3) -> dict:
        """Generate judge prompts for LLM judging.

        Returns dict of {bug_id: {dimension: judge_prompt}} for Claude Code to execute.
        """
        judge_prompts = {}
        bugs_by_id = {b.id: b for b in self.bugs}

        for report in self.reports[:max_bugs]:
            bug = bugs_by_id.get(report.bug_id)
            if not bug:
                continue

            bug_judges = {}
            for dim in ["evidence", "root_cause", "cf"]:
                prompt = build_judge_prompt(dim, report, bug)
                bug_judges[dim] = prompt

            judge_prompts[report.bug_id] = bug_judges

        judge_file = BENCH_DIR / ".judge_prompts.json"
        judge_file.write_text(
            json.dumps(judge_prompts, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        print(f"Judge prompts written to: {judge_file}")
        return judge_prompts

    def generate_report(self) -> str:
        """Generate final markdown report."""
        summary = generate_summary(self.results)

        total = sum(r.total for r in self.results)
        max_s = sum(r.max_score for r in self.results)
        pct = total / max_s * 100 if max_s > 0 else 0

        # Gate check
        from bughunt_ci import CIGate
        gate = CIGate(self.mode)
        gate_passed = gate.check(self.results)
        gate_report = gate.report()

        elapsed = (datetime.now() - self.start_time).total_seconds() if self.start_time else 0

        full_report = f"""{summary}

## CI Gate [{self.mode}]

```
{gate_report}
```

**Gate: {'PASS' if gate_passed else 'FAIL'}**
**Time: {elapsed:.1f}s**
**Mode: {self.mode}**
"""

        report_file = BENCH_DIR / f"REPORT_{datetime.now().strftime('%Y%m%d_%H%M')}.md"
        report_file.write_text(full_report, encoding="utf-8")
        print(f"\nReport: {report_file}")

        return full_report


# --- CLI ---


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="BugHuntBench Full Runner"
    )
    parser.add_argument("--bugs", default="all",
                       help="Bug IDs or 'all'")
    parser.add_argument("--mode", default="quick",
                       choices=["quick", "full", "verify"])
    parser.add_argument("--agent-outputs", type=str,
                       help="JSON file with agent outputs {bug_id: text}")
    parser.add_argument("--judges", action="store_true",
                       help="Generate judge prompts after scoring")
    parser.add_argument("--gate-only", action="store_true",
                       help="Only run gate check on existing results")
    parser.add_argument("--prompts-only", action="store_true",
                       help="Only generate agent prompts, don't score")

    args = parser.parse_args()

    # Gate-only mode
    if args.gate_only:
        results = load_results()
        if not results:
            print("No results found.")
            sys.exit(1)

        timestamps = sorted(set(r.get("timestamp", "") for r in results), reverse=True)
        latest = timestamps[0]
        latest_results = [r for r in results if r.get("timestamp") == latest]

        cards = [
            ScoreCard(
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
            for r in latest_results
        ]

        from bughunt_ci import CIGate
        gate = CIGate(args.mode)
        passed = gate.check(cards)
        print(gate.report())
        sys.exit(0 if passed else 1)

    # Load bugs
    bug_ids = None if args.bugs == "all" else [b.strip() for b in args.bugs.split(",")]
    runner = BugHuntRunner(mode=args.mode, bugs=bug_ids)

    if runner.bug_count == 0:
        print("No bugs found.")
        sys.exit(1)

    # Prompts-only mode
    if args.prompts_only:
        runner.run()
        return

    # Agent outputs mode
    if args.agent_outputs:
        outputs = json.loads(Path(args.agent_outputs).read_text(encoding="utf-8"))
        runner.process_agent_outputs(outputs)

        if args.judges:
            runner.run_judges()

        runner.generate_report()
        return

    # Default: generate prompts and wait for agent execution
    result = runner.run()
    print(f"\nReady. Bugs: {result['bugs_loaded']}, Mode: {result['mode']}")
    print(f"Prompts: {result['prompts_file']}")
    print("\nNext step: feed agent outputs back with --agent-outputs <file>")


if __name__ == "__main__":
    main()
