"""
试剑石 v2.0 — 成长引擎 (Growth Engine)

6 条触发 → 自动进化:
  T1 退役: 同bug 3+ agent满分 → 退役 → 生成更难变体
  T2 盲区: 同类型评分方差=0 → scoring blindspot
  T3 新类: 连续新failure pattern → 候选新bug类型
  T4 污染: 检测答案泄露 → 告警+隔离
  T5 过拟合: skill优化后分数反降 → overfit warning
  T6 挖矿: 生产新bug → 自动脱敏→入基准库

用法:
  python growth_engine.py check    # 检查所有触发条件
  python growth_engine.py evolve   # 执行自动进化
  python growth_engine.py mine     # 从git history挖新bug
"""

import json
import re
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict

BENCH_DIR = Path(__file__).parent
BUGSET_DIR = BENCH_DIR / "bugset"
RESULTS_FILE = BENCH_DIR / "results.tsv"
REPO_ROOT = Path("f:/ClaudeFiles")


# ============================================================
# Data Structures
# ============================================================

@dataclass
class TriggerEvent:
    trigger: str  # T1-T6
    bug_id: str = ""
    detail: str = ""
    action: str = ""
    auto: bool = False  # Can be auto-executed?


@dataclass
class BugStats:
    bug_id: str
    total_runs: int = 0
    avg_score: float = 0.0
    max_score: float = 0.0
    perfect_runs: int = 0  # Runs with 8/8
    score_variance: float = 0.0
    last_run: str = ""
    difficulty: str = "medium"


# ============================================================
# Growth Engine
# ============================================================

class GrowthEngine:
    """试剑石成长引擎 — 6条触发自动进化."""

    def __init__(self):
        self.events: list[TriggerEvent] = []
        self.stats: dict[str, BugStats] = {}

    def load_results(self) -> list[dict]:
        """Load historical results."""
        if not RESULTS_FILE.exists():
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
            results.append(dict(zip(headers, values)))
        return results

    def compute_stats(self) -> dict[str, BugStats]:
        """Compute per-bug statistics from results."""
        results = self.load_results()
        bug_data = defaultdict(list)

        for r in results:
            bid = r.get("bug_id", "")
            if not bid or not bid.startswith("B"):
                continue
            try:
                score = int(r.get("total", 0))
            except (ValueError, TypeError):
                continue
            bug_data[bid].append(score)

        stats = {}
        for bid, scores in bug_data.items():
            n = len(scores)
            avg = sum(scores) / n
            max_s = max(scores)
            perfect = sum(1 for s in scores if s >= 8)
            variance = sum((s - avg) ** 2 for s in scores) / n if n > 1 else 0
            last = results[-1].get("timestamp", "") if results else ""

            stats[bid] = BugStats(
                bug_id=bid, total_runs=n, avg_score=avg,
                max_score=max_s, perfect_runs=perfect,
                score_variance=variance, last_run=last,
            )

        self.stats = stats
        return stats

    def check_triggers(self) -> list[TriggerEvent]:
        """Check all 6 triggers and return triggered events."""
        self.compute_stats()
        self.events = []

        # T1: 同bug 3+满分 → AUTORETIRE
        for bid, stat in self.stats.items():
            if stat.perfect_runs >= 3 and stat.avg_score >= 7.5:
                self.events.append(TriggerEvent(
                    trigger="T1_AUTORETIRE", bug_id=bid,
                    detail=f"{bid}: {stat.perfect_runs} perfect runs, avg={stat.avg_score:.1f}",
                    action=f"Retire {bid}, generate 2 harder variants",
                    auto=False,  # Needs human review for variant quality
                ))

        # T2: 同类型评分方差=0 → SCORING_BLINDSPOT
        # Group by type (extracted from ground truth)
        type_scores = defaultdict(list)
        for bid, stat in self.stats.items():
            # Simplified: use bug ID prefix as proxy
            t = getattr(stat, 'bug_type', 'unknown')
            type_scores[t].append(stat.avg_score)

        for btype, scores in type_scores.items():
            if len(scores) >= 3:
                variance = sum((s - sum(scores)/len(scores))**2 for s in scores) / len(scores)
                if variance < 0.1:
                    self.events.append(TriggerEvent(
                        trigger="T2_BLINDSPOT", bug_id=btype,
                        detail=f"Type {btype}: variance={variance:.3f}, all scores within narrow band",
                        action="Add new scoring dimension or adjust weights for this type",
                        auto=False,
                    ))

        # T3: 新failure pattern → 候选T8/T9
        # Detected when multiple bugs of same "root cause category" emerge
        # For now: heuristic based on results notes
        notes_patterns = defaultdict(int)
        for r in self.load_results():
            notes = r.get("notes", "")
            if "发现真bug" in notes:
                notes_patterns["found_real_but_wrong_bug"] += 1
            if "分类错误" in notes:
                notes_patterns["classification_error"] += 1
            if "根因错" in notes:
                notes_patterns["root_cause_mismatch"] += 1

        for pattern, count in notes_patterns.items():
            if count >= 5:
                self.events.append(TriggerEvent(
                    trigger="T3_NEW_PATTERN", bug_id=pattern,
                    detail=f"Pattern '{pattern}' occurred {count} times",
                    action="Extract pattern → candidate new bug type or gotcha",
                    auto=False,
                ))

        # T4: 污染检测 — triggered from CCV or audit results
        # This would be populated by security_gate.py
        # Placeholder: check if truth.md was accessed in recent runs

        # T5: 过拟合检测 — skill优化后分数降了
        # Compare consecutive runs: if score drops after skill change
        results = self.load_results()
        if len(results) >= 20:
            recent = results[-10:]
            older = results[-20:-10]
            recent_avg = sum(int(r.get("total", 0)) for r in recent) / len(recent)
            older_avg = sum(int(r.get("total", 0)) for r in older) / len(older)
            if recent_avg < older_avg - 5:
                self.events.append(TriggerEvent(
                    trigger="T5_OVERFIT", bug_id="ALL",
                    detail=f"Recent avg={recent_avg:.1f} < older avg={older_avg:.1f}",
                    action="Skill may be overfitting to old benchmark. Add new bugs to test.",
                    auto=False,
                ))

        # T6: 挖矿 — check git history for new bugs
        self._check_git_for_new_bugs()

        return self.events

    def _check_git_for_new_bugs(self):
        """Check git log for recent bug fixes that could become new benchmark bugs."""
        try:
            # Recent commits with fix/bug keywords
            result = subprocess.run(
                ["git", "log", "--oneline", "--since=30.days", "--grep=fix\\|bug\\|修复"],
                cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace"
            )
            fix_commits = [l for l in result.stdout.split("\n") if l.strip()]
            if len(fix_commits) >= 3:
                self.events.append(TriggerEvent(
                    trigger="T6_MINE", bug_id="git-history",
                    detail=f"Found {len(fix_commits)} potential fix commits in last 30 days",
                    action=f"Review {min(5, len(fix_commits))} commits for bug extraction",
                    auto=False,
                ))
        except Exception:
            pass

    def evolve(self, auto_apply: bool = False) -> list[str]:
        """Execute automatic evolution steps.

        Only T1 (retire) and T4 (contamination flag) can be fully automated.
        Others need human review.
        """
        events = self.check_triggers()
        actions = []

        for evt in events:
            if not evt.auto:
                actions.append(f"[REVIEW] {evt.trigger}: {evt.detail} → {evt.action}")
                continue

            if evt.trigger == "T1_AUTORETIRE":
                actions.append(f"[AUTO] Retiring {evt.bug_id}...")
                # Move to retired/
                # Generate variants

            if evt.trigger == "T4_CONTAMINATION":
                actions.append(f"[AUTO] Flagging {evt.bug_id} as contaminated")

        return actions

    def mine_git_history(self, max_bugs: int = 10) -> list[dict]:
        """Mine campus_go git history for real bug fixes.

        Returns list of candidate bugs ready for human review.
        """
        try:
            result = subprocess.run(
                ["git", "log", "--oneline", "--diff-filter=M",
                 "--", "campus_go/internal/handlers/"],
                cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace"
            )
            commits = result.stdout.strip().split("\n")[:max_bugs * 3]
        except Exception:
            commits = []

        candidates = []
        for commit_line in commits[:max_bugs]:
            if not commit_line.strip():
                continue
            commit_hash = commit_line.split()[0]
            # Get commit message
            try:
                msg_result = subprocess.run(
                    ["git", "log", "-1", "--format=%s", commit_hash],
                    cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace"
                )
                msg = msg_result.stdout.strip()
            except Exception:
                msg = commit_line

            candidates.append({
                "commit": commit_hash,
                "message": msg,
                "status": "candidate",
                "needs_review": True,
            })

        return candidates


# ============================================================
# CLI
# ============================================================

def main():
    import sys

    if len(sys.argv) < 2:
        print("Usage: python growth_engine.py <check|evolve|mine|stats>")
        sys.exit(1)

    cmd = sys.argv[1]
    engine = GrowthEngine()

    if cmd == "check":
        events = engine.check_triggers()
        print(f"\n{len(events)} triggers fired:\n")
        for evt in events:
            icon = "[AUTO]" if evt.auto else "[REVIEW]"
            print(f"  {icon} {evt.trigger}: {evt.detail}")
            print(f"         → {evt.action}")
            print()

    elif cmd == "evolve":
        actions = engine.evolve(auto_apply=False)
        for a in actions:
            print(f"  {a}")

    elif cmd == "mine":
        candidates = engine.mine_git_history()
        print(f"Found {len(candidates)} candidate bugs from git history:\n")
        for c in candidates:
            print(f"  {c['commit'][:8]}: {c['message'][:80]}")

    elif cmd == "stats":
        stats = engine.compute_stats()
        print(f"{'Bug':<6} {'Runs':<6} {'Avg':<6} {'Max':<6} {'Perfect':<8} {'Var':<8}")
        print("-" * 50)
        for bid in sorted(stats.keys()):
            s = stats[bid]
            print(f"{bid:<6} {s.total_runs:<6} {s.avg_score:<6.1f} {s.max_score:<6.0f} "
                  f"{s.perfect_runs:<8} {s.score_variance:<8.2f}")

    else:
        print(f"Unknown: {cmd}")


if __name__ == "__main__":
    main()
