"""
试剑石 Layer 0 — 规则评分器 ($0, <1s)
纯规则匹配 4/7 维度，零 token 成本。

维度:
  c1: T-Type (1pt) — 字符串精确匹配
  c2: 链完整 (1pt) — 7 步产出非空
  c6: 修复正确 (1pt) — 长度 > 15 + 关键词
  c7: 轨迹合规 (1pt) — 同 c2

用法:
  python layer0_score.py results.json
  python layer0_score.py --all  # 批量评分 results.tsv
"""

import json
import sys
from pathlib import Path

# Ground truth T-Types
GT = {
    "B01": "T0", "B02": "T1", "B03": "T2", "B04": "T3", "B05": "T4",
    "B06": "T5", "B07": "T6", "B08": "T7", "B09": "T1", "B10": "T3",
    "B11": "T0", "B12": "T3", "B13": "T4", "B14": "T3", "B15": "T6",
    "B16": "T7", "B17": "T2", "B18": "T5", "B19": "T1", "B20": "T6",
    "B21": "T3", "B22": "T0", "B23": "T2", "B24": "T4", "B25": "T5",
    "B26": "T0", "B27": "T3", "B28": "T5", "B29": "T7", "B30": "T1",
    "B31": "T3", "B32": "T6", "B33": "T0", "B34": "T2", "B35": "T7",
}

REQUIRED_FIELDS = [
    "classification", "evidence", "trace", "root_cause",
    "cf_evidence", "fix_description"
]


def score_bug(report: dict) -> dict:
    """Score a single bug report using rule-based dimensions only."""
    bug_id = report.get("bug_id", "?")

    # c1: T-Type match
    gt_type = GT.get(bug_id, "??")
    agent_type = (report.get("classification", "") or "").strip()[:2]
    c1 = 1 if agent_type == gt_type else 0

    # c2: chain completeness (all 6 fields non-empty)
    missing = [f for f in REQUIRED_FIELDS if not report.get(f, "").strip()]
    c2 = 1 if len(missing) == 0 else 0

    # c6: fix quality (length > 15 chars AND contains code-like content)
    fix = (report.get("fix_description", "") or "").strip()
    has_code_indicators = any(kw in fix.lower() for kw in [
        "fix", "add", "remove", "change", "update", "replace", "insert",
        "//", "func", "def", "return", "if ", "sql", "query", "line",
        "file", ".go", ".py", ".js", ".dart", "handler", "function",
        "not_a_bug", "stop", "不修"
    ])
    c6 = 1 if len(fix) > 15 and has_code_indicators else 0

    # c7: trajectory (same as c2 — chain completeness = trajectory valid)
    c7 = c2

    total = c1 + c2 + c6 + c7  # max 4 from Layer 0
    return {
        "bug_id": bug_id,
        "gt_type": gt_type,
        "agent_type": agent_type,
        "c1_ttype": c1,
        "c2_chain": c2,
        "c6_fix": c6,
        "c7_traj": c7,
        "layer0_total": total,
        "layer0_max": 4,
        "missing_fields": missing,
        "classification_ok": c1 == 1,
    }


def score_all(reports: list[dict]) -> dict:
    """Score all bug reports, return summary."""
    results = [score_bug(r) for r in reports if r]
    total = sum(r["layer0_total"] for r in results)
    max_possible = len(results) * 4
    ttype_ok = sum(1 for r in results if r["classification_ok"])
    chain_ok = sum(1 for r in results if r["c2_chain"])

    return {
        "total": total,
        "max": max_possible,
        "pct": round(total / max_possible * 100, 1) if max_possible else 0,
        "ttype_accuracy": f"{ttype_ok}/{len(results)}",
        "chain_completeness": f"{chain_ok}/{len(results)}",
        "per_bug": results,
        "failed_classifications": [
            {"bug_id": r["bug_id"], "gt": r["gt_type"], "got": r["agent_type"]}
            for r in results if not r["classification_ok"]
        ],
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python layer0_score.py <results.json>")
        print("       python layer0_score.py --stdin  (read from stdin)")
        sys.exit(1)

    if sys.argv[1] == "--stdin":
        data = json.loads(sys.stdin.read())
    else:
        data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8-sig"))

    if isinstance(data, list):
        reports = data
    elif "zxScores" in data:
        # Workflow output format — already scored, just extract T-Type stats
        zx = data.get("zxScores", [])
        bare = data.get("bareScores", [])
        zx_tt = sum(1 for s in zx if s.get("c1"))
        bare_tt = sum(1 for s in bare if s.get("c1"))
        print(f"缉凶 Layer0 T-Type: {zx_tt}/{len(zx)} ({(zx_tt/len(zx)*100):.0f}%)")
        print(f"裸   Layer0 T-Type: {bare_tt}/{len(bare)} ({(bare_tt/len(bare)*100):.0f}%)")
        # Show misclassifications
        for s in zx:
            if not s.get("c1"):
                print(f"  FAIL {s['bug_id']}: GT={s['gt_type']} -> Agent={s['agent_type']}")
        print(f"\nLayer0 cost: $0.00 (zero tokens)")
        print(f"Vs full workflow: 46 agents, 5.8M tokens (~$5)")
    else:
        result = score_all([data])
        print(json.dumps(result, indent=2, ensure_ascii=False))
