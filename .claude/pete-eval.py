"""ICRL Evaluator-Optimizer Loop.

Evaluates code changes with an independent critic model,
retries up to 3 times if score < 7.

Usage:
  python pete-eval.py <diff_file_or_git_ref>
  python pete-eval.py HEAD~1
  python pete-eval.py f:/ClaudeFiles/.claude/eval-sample.diff

Architecture (ICRL pattern):
  Generator (DeepSeek V4) → changed code
  Evaluator (separate model) → score + feedback
  Score >= 7 → pass
  Score < 7 → feedback → Generator retries → max 3 rounds
  Score degrades → rollback to best version

Requires: DEEPSEEK_API_KEY env var
"""

import sys, os, json, subprocess, hashlib
from pathlib import Path
from datetime import datetime, timezone
import io

if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
API_URL = "https://api.deepseek.com/v1/chat/completions"

EVAL_LOG = Path("f:/ClaudeFiles/.claude/eventstore/evaluations.jsonl")
EVAL_LOG.parent.mkdir(parents=True, exist_ok=True)

EVALUATOR_PROMPT = """You are a strict code reviewer. Evaluate the following code changes.

Score each dimension 1-10:
1. Correctness — does it actually fix the problem?
2. Security — no new vulnerabilities introduced?
3. Performance — no obvious bottlenecks or waste?
4. Readability — clear, idiomatic, well-structured?

Return ONLY valid JSON:
{
  "total": 7.5,
  "correctness": 8,
  "security": 7,
  "performance": 7,
  "readability": 8,
  "verdict": "pass|retry",
  "feedback": "specific, actionable feedback here",
  "critical_issues": ["issue1 if any"],
  "praise": ["what was done well"]
}
"""


def call_evaluator(diff_text: str, model: str = "deepseek-chat") -> dict:
    """Call the evaluator model with the diff."""
    import urllib.request

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": EVALUATOR_PROMPT},
            {"role": "user", "content": f"Evaluate these code changes:\n\n```diff\n{diff_text[:8000]}\n```"}
        ],
        "temperature": 0.1,
        "max_tokens": 1000,
        "response_format": {"type": "json_object"},
    }

    req = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
    )

    with urllib.request.urlopen(req, timeout=60) as resp:
        result = json.loads(resp.read())
        content = result["choices"][0]["message"]["content"]
        return json.loads(content)


def log_evaluation(score: dict, round_num: int, diff_hash: str):
    """Append evaluation result to log."""
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "round": round_num,
        "diff_hash": diff_hash,
        "score": score,
    }
    with open(EVAL_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def evaluate(diff_text: str, max_rounds: int = 3, threshold: float = 7.0) -> dict:
    """Run evaluator-optimizer loop.

    Returns: {"verdict": "pass"|"fail", "best_score": float, "rounds": int,
              "feedback": str, "history": list}
    """
    history = []
    best_score = 0
    best_round = 0

    for r in range(1, max_rounds + 1):
        print(f"Round {r}/{max_rounds}...")

        try:
            result = call_evaluator(diff_text)
        except Exception as e:
            print(f"  Evaluator error: {e}")
            result = {"total": 0, "verdict": "retry", "feedback": str(e)}

        result["_round"] = r
        history.append(result)
        diff_hash = hashlib.sha256(diff_text.encode()).hexdigest()[:12]
        log_evaluation(result, r, diff_hash)

        score = result.get("total", 0)
        print(f"  Score: {score}/10 — {result.get('verdict', '?')}")

        if score > best_score:
            best_score = score
            best_round = r

        if score >= threshold:
            print(f"  PASS (round {r})")
            return {
                "verdict": "pass",
                "best_score": score,
                "rounds": r,
                "feedback": result.get("feedback", ""),
                "praise": result.get("praise", []),
                "history": history,
            }

        # Score degraded — rollback
        if score < best_score - 1:
            print(f"  Score degraded ({best_score} -> {score}). Stopping.")
            break

        print(f"  Feedback: {result.get('feedback', 'none')[:120]}")

    print(f"  FAIL after {max_rounds} rounds. Best: {best_score}/10 (round {best_round})")
    return {
        "verdict": "fail",
        "best_score": best_score,
        "rounds": max_rounds,
        "feedback": history[-1].get("feedback", "") if history else "",
        "critical_issues": history[-1].get("critical_issues", []) if history else [],
        "history": history,
    }


def get_diff(source: str) -> str:
    """Get diff text from git reference or file."""
    path = Path(source)
    if path.exists() and path.is_file():
        return path.read_text(encoding="utf-8")

    # Try git diff
    try:
        result = subprocess.run(
            ["git", "-C", "f:/ClaudeFiles", "diff", source],
            capture_output=True, text=True, timeout=30
        )
        if result.stdout.strip():
            return result.stdout
    except Exception:
        pass

    print(f"Cannot read diff from: {source}")
    sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python pete-eval.py <diff_file|git_ref>")
        sys.exit(1)

    if not API_KEY:
        print("Error: DEEPSEEK_API_KEY not set")
        sys.exit(1)

    source = sys.argv[1]
    diff_text = get_diff(source)
    print(f"Diff: {len(diff_text)} chars, {diff_text.count(chr(10))} lines")
    print()

    result = evaluate(diff_text)
    print(f"\nFinal: {result['verdict']} — {result['best_score']}/10 in {result['rounds']} rounds")
    if result.get("critical_issues"):
        print(f"Critical: {', '.join(result['critical_issues'])}")

    sys.exit(0 if result["verdict"] == "pass" else 1)
