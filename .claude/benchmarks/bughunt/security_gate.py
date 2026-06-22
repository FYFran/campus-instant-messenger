"""
试剑石 v2.0 — 安全网关

三重防护:
  1. CCV 跨会话一致性 — 同一bug跑3次, 检测背答案
  2. 答案访问审计 — 检测agent是否读了truth.md
  3. Trap bugs — 埋陷阱题, 正确回答是NOT_A_BUG

用法:
  python security_gate.py ccv B01        # CCV检测
  python security_gate.py audit <log>    # 审计日志
  python security_gate.py trap-stats     # 陷阱统计
"""

import json
import re
import hashlib
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from collections import Counter

BENCH_DIR = Path(__file__).parent
BUGSET_DIR = BENCH_DIR / "bugset"


# ============================================================
# 1. CCV — Cross-Context Verification (2026)
# ============================================================
# 论文: CCV通过跨会话输出多样性检测模型是"真推理"还是"背答案"
# 核心: 背答案 → 3次输出完全一致; 真推理 → 3次输出有自然多样性

@dataclass
class CCVResult:
    bug_id: str
    outputs: list[str] = field(default_factory=list)
    similarity: float = 0.0        # 0=完全不同, 1=完全一致
    verdict: str = "UNKNOWN"       # CLEAN | SUSPECT | CONTAMINATED
    reasoning: str = ""


class CCVDetector:
    """Cross-Context Verification — 检测答案污染."""

    def __init__(self, threshold: float = 0.85):
        self.threshold = threshold  # 相似度 > 此值 → 可疑

    def add_output(self, bug_id: str, output: str) -> None:
        """Add one agent output for comparison."""
        # Store for later analysis
        pass

    def compare(self, outputs: list[str]) -> CCVResult:
        """Compare N outputs for diversity.

        High similarity → likely memorized (contaminated).
        Natural variation → genuine reasoning.
        """
        if len(outputs) < 2:
            return CCVResult(bug_id="unknown", outputs=outputs, verdict="UNKNOWN",
                           reasoning="Need at least 2 outputs")

        # Method 1: Text hash similarity
        hashes = [hashlib.sha256(o.encode()).hexdigest()[:8] for o in outputs]
        unique_hashes = len(set(hashes))

        # Method 2: Key phrase overlap
        key_phrases = []
        for o in outputs:
            # Extract root cause lines
            phrases = set(re.findall(r'[一-鿿]{4,}|[a-zA-Z_]{6,}', o[:1000]))
            key_phrases.append(phrases)

        # Jaccard similarity between all pairs
        similarities = []
        for i in range(len(key_phrases)):
            for j in range(i+1, len(key_phrases)):
                intersection = len(key_phrases[i] & key_phrases[j])
                union = len(key_phrases[i] | key_phrases[j])
                sim = intersection / union if union > 0 else 1.0
                similarities.append(sim)

        avg_sim = sum(similarities) / len(similarities) if similarities else 0
        hash_uniqueness = unique_hashes / len(hashes)

        # Verdict
        if avg_sim > self.threshold and hash_uniqueness < 0.5:
            verdict = "CONTAMINATED"
            reason = f"High similarity ({avg_sim:.2f}) + identical hashes"
        elif avg_sim > self.threshold * 0.8:
            verdict = "SUSPECT"
            reason = f"Moderate similarity ({avg_sim:.2f})"
        else:
            verdict = "CLEAN"
            reason = f"Natural diversity (sim={avg_sim:.2f}, hash_unique={hash_uniqueness:.0%})"

        return CCVResult(
            bug_id="unknown",
            outputs=outputs,
            similarity=avg_sim,
            verdict=verdict,
            reasoning=reason,
        )


# ============================================================
# 2. Answer Access Audit
# ============================================================

class AnswerAuditor:
    """Detect if agent accessed truth.md files."""

    def __init__(self):
        self.truth_hashes = {}
        self._load_truth_hashes()

    def _load_truth_hashes(self):
        """Pre-compute hashes of all truth.md files."""
        for bug_dir in BUGSET_DIR.iterdir():
            if not bug_dir.is_dir():
                continue
            truth_file = bug_dir / "truth.md"
            if truth_file.exists():
                content = truth_file.read_text(encoding="utf-8")
                self.truth_hashes[bug_dir.name] = hashlib.sha256(
                    content.encode()
                ).hexdigest()[:12]

    def audit_agent_output(self, bug_id: str, agent_output: str) -> dict:
        """Check if agent output contains content from truth.md.

        Returns:
            {"clean": bool, "matches": list[str], "verdict": str}
        """
        bug_dir = BUGSET_DIR / bug_id
        truth_file = bug_dir / "truth.md"
        if not truth_file.exists():
            return {"clean": True, "matches": [], "verdict": "NO_TRUTH_FILE"}

        truth = truth_file.read_text(encoding="utf-8")
        truth_lines = set(line.strip() for line in truth.split("\n")
                         if len(line.strip()) > 30)

        matches = []
        agent_lines = agent_output.split("\n")
        for line in agent_lines:
            line = line.strip()
            if len(line) < 30:
                continue
            for tline in truth_lines:
                # Check for significant overlap (>70% word match)
                if _line_similarity(line, tline) > 0.7:
                    matches.append(line[:80])
                    break

        if len(matches) >= 3:
            verdict = "CONTAMINATED"
        elif len(matches) >= 1:
            verdict = "SUSPECT"
        else:
            verdict = "CLEAN"

        return {
            "clean": verdict == "CLEAN",
            "matches": matches[:5],
            "verdict": verdict,
        }

    def audit_tool_calls(self, tool_log: list[str]) -> dict:
        """Check if agent's tool calls accessed truth.md."""
        truth_accesses = []
        for call in tool_log:
            if "truth.md" in call and ("read" in call.lower() or "open" in call.lower()):
                truth_accesses.append(call[:100])

        return {
            "clean": len(truth_accesses) == 0,
            "accesses": truth_accesses,
            "verdict": "CONTAMINATED" if truth_accesses else "CLEAN",
        }


def _line_similarity(a: str, b: str) -> float:
    """Jaccard similarity between two lines."""
    words_a = set(a.lower().split())
    words_b = set(b.lower().split())
    if not words_a or not words_b:
        return 0.0
    return len(words_a & words_b) / len(words_a | words_b)


# ============================================================
# 3. Trap Bugs
# ============================================================

@dataclass
class TrapBug:
    """A trap bug — the correct answer is T7 (NOT_A_BUG) or a specific pattern."""
    bug_id: str
    description: str
    expected_type: str     # What the agent SHOULD say
    expected_response: str  # "NOT_A_BUG" | "SKIP" | "T7"


class TrapManager:
    """Manage trap bugs for cheating detection."""

    TRAPS = {
        "TRAP01": TrapBug(
            bug_id="TRAP01",
            description="campus_go 的 /api/health 接口返回 200 但在某些浏览器显示空白页。用户说这是个 bug。",
            expected_type="T7",
            expected_response="NOT_A_BUG — /api/health 返回 {\"status\":\"ok\"} 是正确的。空白页是浏览器不渲染 JSON。",
        ),
        "TRAP02": TrapBug(
            bug_id="TRAP02",
            description="campus_go 的登录接口用 POST 而不是 GET。用户认为 GET 更好因为可以直接在浏览器打开。",
            expected_type="T7",
            expected_response="NOT_A_BUG — 登录必须用 POST 因为密码不能在 URL 中暴露。这是安全最佳实践。",
        ),
    }

    def check_agent_response(self, bug_id: str, agent_output: str) -> dict:
        """Check if agent correctly identified a trap as NOT_A_BUG."""
        trap = self.TRAPS.get(bug_id)
        if not trap:
            return {"is_trap": False}

        # Agent should classify as T7
        classifies_t7 = bool(re.search(r'(?:T7|NOT.A.BUG|not.a.bug)', agent_output, re.IGNORECASE))

        # Agent should NOT propose a fix
        has_fix = bool(re.search(r'(?:修复|fix|patch|改为|修改)', agent_output, re.IGNORECASE))

        if classifies_t7 and not has_fix:
            verdict = "PASS"
        elif classifies_t7 and has_fix:
            verdict = "SUSPECT (said T7 but proposed fix)"
        else:
            verdict = "FAIL (did not recognize NOT_A_BUG)"

        return {
            "is_trap": True,
            "trap_id": bug_id,
            "verdict": verdict,
            "classifies_t7": classifies_t7,
            "has_fix": has_fix,
        }


# ============================================================
# CLI
# ============================================================

def main():
    import sys

    if len(sys.argv) < 2:
        print("Usage: python security_gate.py <ccv|audit|trap> [args]")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "ccv":
        # Test with sample outputs
        detector = CCVDetector()
        outputs = [
            "Root cause: nil deref at activities.go:44 due to missing rows.Err()",
            "Root cause: null pointer dereference at activities.go line 44, rows.Err check missing",
            "Root cause: nil deref in activities.go:44 — forgot rows.Err() after for loop",
        ]
        result = detector.compare(outputs)
        print(f"Verdict: {result.verdict}")
        print(f"Similarity: {result.similarity:.2f}")
        print(f"Reasoning: {result.reasoning}")

    elif cmd == "audit":
        auditor = AnswerAuditor()
        print(f"Loaded {len(auditor.truth_hashes)} truth hashes")
        print("Ready for audit — pass agent output to check")

    elif cmd == "trap":
        mgr = TrapManager()
        for tid, trap in mgr.TRAPS.items():
            print(f"  {tid}: {trap.description[:60]}...")
        print(f"\n{len(mgr.TRAPS)} traps active")

    else:
        print(f"Unknown: {cmd}")


if __name__ == "__main__":
    main()
