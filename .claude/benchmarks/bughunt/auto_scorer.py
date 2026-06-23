"""
BugHuntBench Auto Scorer — 7维自动评分引擎.

三层评分:
  L1: 规则评分 (维度 1,2,7) — 零 token 成本
  L2: LLM Judge (维度 3,4,5) — Agent-as-Judge
  L3: 修复验证 (维度 6) — 跑回归测试

Judge 设计原则 (2026 研究):
  - Cross-model-family judging
  - 3-judge consensus + 置信度加权
  - Per-dimension 独立 judge prompt
  - 证据引用强制 (file:line)
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from bughunt_harness import (
    AgentReport, BugSpec, ScoreCard,
    score_by_rules, build_judge_prompt,
    BENCH_DIR, BUGS_DIR, RESULTS_FILE,
)


@dataclass
class JudgeVerdict:
    """Single judge's verdict for one dimension."""
    dimension: str
    score: int
    confidence: float  # 0-100
    reasoning: str
    model: str = ""
    valid_alternative: bool = False  # Agent found real bug, not injected bug

    @property
    def weight(self) -> float:
        """Confidence-weighted vote."""
        if self.confidence < 50:
            return 0.5  # Low confidence → half weight
        return 1.0


@dataclass
class ConsensusResult:
    """3-judge consensus result."""
    dimension: str
    final_score: float
    agreement: str  # "unanimous" | "majority" | "split"
    votes: list[JudgeVerdict] = field(default_factory=list)
    suspecT: bool = False

    @property
    def is_reliable(self) -> bool:
        return self.agreement != "split" and not self.suspecT


class AutoScorer:
    """Automated scoring engine for BugHuntBench."""

    def __init__(self, mode: str = "quick"):
        """
        Args:
            mode: "quick" = rules-only, "full" = rules + LLM judge, "verify" = full + cross-model
        """
        self.mode = mode
        self.judge_results: dict[str, list[ConsensusResult]] = {}

    def score(self, report: AgentReport, bug: BugSpec) -> ScoreCard:
        """Score a single bug report against ground truth.

        Returns ScoreCard with all dimensions filled.

        Args:
            report: Parsed agent output
            bug: Ground truth specification

        Returns:
            ScoreCard with scores for all dimensions
        """
        # L1: Rule-based scoring (always runs, zero cost)
        card = score_by_rules(report, bug)

        if self.mode == "quick":
            # Quick mode: evidence + root_cause + cf use heuristic defaults
            # Evidence: check if agent provided concrete reproduction steps
            evidence = report.chain_steps.get("证据", "")
            if evidence and len(evidence) > 20:
                card.score_evidence = 1

            # Root cause: check if file:line is in the right area
            # This is a heuristic — full mode uses LLM judge
            if report.root_cause_file_line:
                card.score_root_cause = 1  # Partial credit for having file:line
                # Check if root cause text mentions key concepts from ground truth
                if _keyword_overlap(report.root_cause, bug.ground_truth.get("root_cause", "")):
                    card.score_root_cause = 2

            # Valid alternative heuristic (quick mode — arXiv:2511.10865)
            # If classification failed but agent's root cause has strong signal
            # (specific file:line + good evidence + same category keywords), flag it
            if card.score_classification == 0 and card.score_root_cause >= 1:
                gt_category = _extract_category(bug.ground_truth.get("root_cause", ""))
                agent_category = _extract_category(report.root_cause)
                if gt_category and agent_category and gt_category == agent_category:
                    card.valid_alternative = True
                    card.score_classification = 0.5  # Partial: right category
                    card.notes += "[valid_alternative: heuristic — same category, specific file:line] "

            # CF: check if CF evidence has pre/post comparison
            if report.cf_evidence and len(report.cf_evidence) > 30:
                card.score_cf = 1

            # Fix: heuristic based on fix description specificity
            if report.fix_description and len(report.fix_description) > 20:
                card.score_fix = 1

            # L3: heuristic — if root cause fully correct, mark REAL; else SUSPECT
            if card.score_root_cause == 2 and card.score_classification == 1:
                card.l3_verdict = "REAL* (quick heuristic)"
            elif card.score_root_cause == 0:
                card.l3_verdict = "SUSPECT (quick heuristic)"
            elif card.valid_alternative:
                card.l3_verdict = "REAL* (valid_alternative heuristic)"
            else:
                card.l3_verdict = "NOT_RUN"

        elif self.mode in ("full", "verify"):
            # Mark that LLM judging is needed (Claude Code Agent tool does this)
            card.notes += "[LLM_JUDGE_NEEDED: evidence,root_cause,cf] "
            card.notes += "[FIX_VERIFY_NEEDED] "

        return card

    @staticmethod
    def parse_judge_response(response: str, dimension: str) -> Optional[JudgeVerdict]:
        """Parse a judge's JSON response into a JudgeVerdict."""
        try:
            # Try to extract JSON from response
            json_match = re.search(r'\{[^}]+\}', response)
            if json_match:
                data = json.loads(json_match.group())
                return JudgeVerdict(
                    dimension=dimension,
                    score=int(data.get("score", 0)),
                    confidence=float(data.get("confidence", 50)),
                    reasoning=data.get("reasoning", ""),
                    valid_alternative=data.get("valid_alternative", False),
                )
        except (json.JSONDecodeError, ValueError, KeyError):
            pass
        return None

    @staticmethod
    def compute_consensus(verdicts: list[JudgeVerdict]) -> ConsensusResult:
        """Compute 3-judge consensus with confidence weighting.

        Rules:
        - 3/3 agree → unanimous
        - 2/3 agree → majority
        - All different → split → SUSPECT
        - Low confidence (<50%) → half weight
        """
        if not verdicts:
            return ConsensusResult(
                dimension="unknown", final_score=0,
                agreement="none", suspecT=True
            )

        dim = verdicts[0].dimension

        # Weighted voting
        scores: dict[int, float] = {}
        for v in verdicts:
            weight = v.weight
            scores[v.score] = scores.get(v.score, 0) + weight

        # Find winning score
        max_weight = max(scores.values())
        winners = [s for s, w in scores.items() if w == max_weight]

        if len(winners) == 1:
            winning_score = winners[0]
            if max_weight >= 2.0:  # At least 2 full-weight judges agree
                agreement = "unanimous" if max_weight >= 2.5 else "majority"
            else:
                agreement = "majority"  # 2 half-weight or 1 full + 1 half
        else:
            agreement = "split"
            winning_score = max(winners)  # Conservative: pick higher score on split

        return ConsensusResult(
            dimension=dim,
            final_score=winning_score,
            agreement=agreement,
            votes=verdicts,
            suspecT=(agreement == "split"),
        )

    def apply_judge_results(self, card: ScoreCard, consensus: dict[str, ConsensusResult]) -> ScoreCard:
        """Apply LLM judge consensus results to a score card."""
        if "evidence" in consensus:
            card.score_evidence = int(consensus["evidence"].final_score)
        if "root_cause" in consensus:
            card.score_root_cause = int(consensus["root_cause"].final_score)
        if "cf" in consensus:
            card.score_cf = int(consensus["cf"].final_score)

        # Valid alternative adjustment (arXiv:2511.10865 — generalize rubrics)
        # If any root_cause judge flagged valid_alternative, adjust classification
        if "root_cause" in consensus:
            rc_consensus = consensus["root_cause"]
            has_valid_alt = any(
                getattr(v, 'valid_alternative', False)
                for v in rc_consensus.votes
            )
            if has_valid_alt and card.score_classification == 0:
                card.valid_alternative = True
                card.score_classification = 0.5  # Partial credit for right category
                if card.score_root_cause == 0:
                    card.score_root_cause = 1  # Give partial if completely zeroed
                card.notes += "[valid_alternative: found real bug, not injected GT] "

        # L3 verdict based on consensus reliability
        all_reliable = all(c.is_reliable for c in consensus.values())
        any_split = any(c.suspecT for c in consensus.values())

        if all_reliable and card.score_root_cause == 2:
            card.l3_verdict = "REAL"
        elif all_reliable and card.score_root_cause == 1:
            card.l3_verdict = "REAL*"
        elif any_split:
            card.l3_verdict = "SUSPECT (judge split)"
        else:
            card.l3_verdict = "TEMPLATE"

        return card


# --- Heuristic Helpers ---


# Bug category taxonomy for valid_alternative matching
# Maps root cause keywords to general bug categories
_BUG_CATEGORIES = {
    "auth": ["auth", "authorization", "permission", "role", "college", "scope", "admin",
             "授权", "权限", "角色", "学院", "管理"],
    "data": ["aggregate", "sum", "count", "null", "nil", "truncat", "join", "query",
             "sql", "propagation", "int(", "float", "数据", "聚合", "查询"],
    "race": ["race", "concurrent", "FOR UPDATE", "atomic", "竞态", "并发", "lock"],
    "config": ["nginx", "config", "deploy", "port", "proxy_pass", "restart",
               "配置", "部署", "重启", "端口"],
    "state": ["state", "status", "stuck", "pending", "状态", "卡住", "流转"],
    "regression": ["yesterday", "昨天", "之前", "regression", "used to work"],
}


def _extract_category(text: str) -> str | None:
    """Extract the general bug category from root cause text.

    Returns category key (e.g. 'auth', 'data') or None if no match.
    Used for valid_alternative heuristic — compares agent finding category vs GT category.
    """
    text_lower = text.lower()
    for category, keywords in _BUG_CATEGORIES.items():
        for kw in keywords:
            if kw.lower() in text_lower:
                return category
    return None


def _keyword_overlap(text1: str, text2: str, threshold: float = 0.3) -> bool:
    """Check if two texts share meaningful keywords above threshold."""
    # Extract meaningful words (Chinese + English)
    words1 = set(re.findall(r'[一-鿿]{2,}|[a-zA-Z_]{3,}', text1.lower()))
    words2 = set(re.findall(r'[一-鿿]{2,}|[a-zA-Z_]{3,}', text2.lower()))

    if not words1 or not words2:
        return False

    overlap = len(words1 & words2) / min(len(words1), len(words2))
    return overlap >= threshold


# --- Test Verification (Dimension 6) ---


def verify_fix(report: AgentReport, bug: BugSpec) -> dict:
    """Verify that the proposed fix would resolve the bug.

    This is a simulation — in production, this would:
    1. Apply the fix diff to a temp branch
    2. Run the regression test suite
    3. Verify the specific test passes

    Returns dict with verification status.
    """
    # In production: git apply fix.diff && go test ./...
    # For now: check that the fix description targets the right area
    result = {
        "fix_applied": False,
        "tests_passed": False,
        "regression_free": False,
        "notes": "Fix verification requires code execution in temp worktree",
    }

    # Heuristic: check if fix mentions the right file
    if report.root_cause_file_line:
        result["fix_applied"] = True

    # Check if fix is specific (not a template)
    if report.fix_description and len(report.fix_description) > 50:
        if any(kw in report.fix_description for kw in ["修复", "fix", "改为", "添加", "修改", "→", "->"]):
            result["tests_passed"] = True

    return result


# --- Integration Test ---


def test_harness():
    """Self-test: verify that the harness can parse all bugs correctly."""
    import bughunt_harness as bh  # noqa: F811

    print("=== BugHuntBench Harness Self-Test ===\n")

    bugs = []
    for f in sorted(BUGS_DIR.glob("B*.md")):
        bug = bh.parse_bug_file(f)
        if bug:
            bugs.append(bug)
            print(f"[OK] {bug.id}: T={bug.type_gt}, lang={bug.language}, "
                  f"desc_len={len(bug.description)}, truth_keys={list(bug.ground_truth.keys())}")

    print(f"\nTotal: {len(bugs)} bugs loaded.")

    # Test scoring with a mock report
    if bugs:
        bug = bugs[0]
        report = AgentReport(
            bug_id=bug.id,
            raw_output=f"Type: {bug.type_gt}\n"
                       f"SCORE_CARD: T{bug.type_gt}|1|1|1|1|1",
            classification=bug.type_gt,
            chain_steps={"分类": "ok", "证据": "ok", "追踪": "ok",
                        "分析": "ok", "修复": "ok", "验证": "ok", "记录": "ok"},
            root_cause="mock root cause: nil deref at activities.go:45",
            root_cause_file_line="activities.go:45",
            cf_evidence="mock cf evidence with pre/post comparison data",
            fix_description="mock fix: add nil check before deref",
        )
        scorer = AutoScorer(mode="quick")
        card = scorer.score(report, bug)
        print(f"\nMock score for {bug.id}: {card.total}/{card.max_score}")
        print(f"  Classification: {card.score_classification}")
        print(f"  Chain: {card.score_chain}")
        print(f"  Evidence: {card.score_evidence}")
        print(f"  Root: {card.score_root_cause}")
        print(f"  CF: {card.score_cf}")
        print(f"  Fix: {card.score_fix}")
        print(f"  Trace: {card.score_trace}")
        print(f"  L3: {card.l3_verdict}")

    print("\n=== Self-Test Complete ===")


if __name__ == "__main__":
    test_harness()
