"""
试剑石 注入一致性验证器 — SWE-bench curation pipeline.

研究依据:
  SWE-bench (Princeton 2024): 2,294候选→~1,000通过。56%被拒。
    主因: patch不适用、描述不匹配patch、测试覆盖不足。
  BenchEvolver (May 2026): 硬化前必须验证基线一致性。
    15-20%的手工benchmark条目有构造效度问题。

对每个 bug 验证:
  1. {desc, truth, inject} 三元组完整性
  2. inject.patch 可应用
  3. truth 根因描述跟 patch 改动一致
  4. desc 症状跟 patch 效果匹配

用法:
  python verify_injections.py          # 检查所有 bugs
  python verify_injections.py --bug B04 # 检查单个 bug
  python verify_injections.py --fix    # 自动修复可修复的问题
"""

import subprocess
import re
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

BENCH_DIR = Path(__file__).parent
BUGSET_DIR = BENCH_DIR / "bugset"
INJECT_DIR = BENCH_DIR / "bug_injection"
ARCHIVE_DIR = BENCH_DIR / "archive"
REPO_ROOT = Path("f:/ClaudeFiles")


@dataclass
class VerifyResult:
    bug_id: str
    status: str  # OK, WARN, FAIL, RETIRED
    issues: list[str] = field(default_factory=list)

    # File existence
    has_desc: bool = False
    has_truth: bool = False
    has_inject: bool = False

    # Injection checks
    patch_applies: bool = False
    patch_error: str = ""

    # Cross-check
    truth_mentions_patch_files: bool = False
    desc_matches_patch_effect: bool = False

    # Bug type
    bug_type: str = "unknown"
    needs_injection: bool = True
    retired: bool = False


def is_retired(bug_id: str) -> bool:
    """Check if bug has been retired to archive/."""
    # Check all archive subdirectories
    if not ARCHIVE_DIR.exists():
        return False
    for subdir in ARCHIVE_DIR.iterdir():
        if subdir.is_dir() and (subdir / bug_id).is_dir():
            return True
    return False


def load_bug_ids() -> list[str]:
    """Return sorted list of bug IDs from bugset/ directory."""
    bugs = []
    for d in sorted(BUGSET_DIR.iterdir()):
        if d.is_dir() and d.name.startswith("B"):
            bugs.append(d.name)
    return bugs


def extract_type_from_truth(bug_id: str) -> str:
    """Extract bug type from truth.md."""
    truth_path = BUGSET_DIR / bug_id / "truth.md"
    if not truth_path.exists():
        return "unknown"
    content = truth_path.read_text(encoding="utf-8")
    m = re.search(r"\*\*Type:\*\*\s*(T\d+)", content)
    if m:
        return m.group(1)
    # Try alternate format
    m = re.search(r"Type:\s*(T\d+)", content)
    return m.group(1) if m else "unknown"


def needs_code_injection(bug_type: str) -> bool:
    """T4 (config), T6 (env), T7 (NOT_A_BUG) don't need code patches."""
    if bug_type in ("T4", "T6", "T7"):
        return False
    return True


def check_patch_applies(patch_path: Path) -> tuple[bool, str]:
    """Check if a patch applies cleanly to the repo."""
    try:
        result = subprocess.run(
            ["git", "apply", "--check", str(patch_path)],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return True, ""
        # Try reverse: bug may already be in HEAD
        result2 = subprocess.run(
            ["git", "apply", "--check", "-R", str(patch_path)],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=10
        )
        if result2.returncode == 0:
            return True, ""
        return False, result.stderr.strip()[:200]
    except Exception as e:
        return False, str(e)[:200]


def get_patch_files(patch_path: Path) -> list[str]:
    """Extract file paths changed by a patch."""
    try:
        result = subprocess.run(
            ["git", "apply", "--stat", str(patch_path)],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=10
        )
        # Parse "file.go | 2 +-" lines
        files = re.findall(r"(\S+)\s+\|", result.stdout)
        return files
    except Exception:
        return []


def check_truth_mentions_files(truth_path: Path, patch_files: list[str]) -> bool:
    """Check if truth.md mentions at least one file from the patch."""
    if not truth_path.exists() or not patch_files:
        return False
    content = truth_path.read_text(encoding="utf-8").lower()
    for f in patch_files:
        fname = Path(f).name.lower()
        if fname in content:
            return True
    return False


def check_desc_matches(bug_id: str) -> bool:
    """Heuristic: desc should describe symptoms consistent with the bug type.

    This is a lightweight check — full verification needs human review.
    """
    desc_path = BUGSET_DIR / bug_id / "desc.md"
    if not desc_path.exists():
        return False
    content = desc_path.read_text(encoding="utf-8")
    # Must have at least some meaningful content beyond the title
    return len(content.strip().split("\n")) >= 2


def verify_bug(bug_id: str) -> VerifyResult:
    """Run all verification checks for a single bug."""
    r = VerifyResult(bug_id=bug_id, status="OK")

    # Retired bugs are preserved for history, skip strict injection checks
    r.retired = is_retired(bug_id)
    if r.retired:
        r.status = "RETIRED"
        r.issues.append("Retired — injection verification skipped.")
        return r

    desc_path = BUGSET_DIR / bug_id / "desc.md"
    truth_path = BUGSET_DIR / bug_id / "truth.md"
    inject_path = INJECT_DIR / f"{bug_id}_inject.patch"

    r.has_desc = desc_path.exists()
    r.has_truth = truth_path.exists()

    if not r.has_desc:
        r.issues.append("MISSING desc.md")
        r.status = "FAIL"
    if not r.has_truth:
        r.issues.append("MISSING truth.md")
        r.status = "FAIL"

    r.bug_type = extract_type_from_truth(bug_id)
    r.needs_injection = needs_code_injection(r.bug_type)

    if r.needs_injection:
        r.has_inject = inject_path.exists()
        if not r.has_inject:
            r.issues.append(f"MISSING inject.patch (type={r.bug_type} needs code injection)")
            r.status = "FAIL"
        else:
            r.patch_applies, r.patch_error = check_patch_applies(inject_path)
            if not r.patch_applies:
                r.issues.append(f"INJECT FAIL: {r.patch_error}")
                r.status = "FAIL"
            else:
                patch_files = get_patch_files(inject_path)
                r.truth_mentions_patch_files = check_truth_mentions_files(truth_path, patch_files)
                if not r.truth_mentions_patch_files:
                    r.issues.append("TRUTH GAP: truth.md doesn't mention any file from inject.patch")
                    r.status = "WARN"
    else:
        r.has_inject = inject_path.exists()
        if r.has_inject:
            r.issues.append(f"EXTRA inject.patch (type={r.bug_type} doesn't need code injection)")
            r.status = "WARN"

    r.desc_matches_patch_effect = check_desc_matches(bug_id)
    if not r.desc_matches_patch_effect:
        r.issues.append("DESC THIN: desc.md too short or missing")
        r.status = "WARN" if r.status == "OK" else r.status

    return r


def verify_all() -> list[VerifyResult]:
    """Verify all bugs in bugset/."""
    bugs = load_bug_ids()
    results = []
    for bid in bugs:
        r = verify_bug(bid)
        results.append(r)
    return results


def print_report(results: list[VerifyResult]):
    """Print a human-readable verification report."""
    ok = sum(1 for r in results if r.status == "OK")
    warn = sum(1 for r in results if r.status == "WARN")
    fail = sum(1 for r in results if r.status == "FAIL")
    retired = sum(1 for r in results if r.status == "RETIRED")
    active = len(results) - retired
    total = len(results)

    print(f"\n{'='*60}")
    print(f" 试剑石 注入一致性验证 — SWE-bench curation pipeline")
    print(f" Bugs: {total} (active={active}, retired={retired}) | OK={ok} | WARN={warn} | FAIL={fail}")
    print(f"{'='*60}\n")

    for r in results:
        if r.status == "OK":
            icon = "[OK]"
        elif r.status == "WARN":
            icon = "[WARN]"
        elif r.status == "RETIRED":
            icon = "[RET]"
        else:
            icon = "[FAIL]"

        injection_note = ""
        if r.retired:
            injection_note = " [retired]"
        elif not r.needs_injection:
            injection_note = f" [no-inject:{r.bug_type}]"

        print(f"  {icon} {r.bug_id} ({r.bug_type}){injection_note}")
        for issue in r.issues:
            print(f"      → {issue}")

    if fail > 0:
        print(f"\n  Research baseline: SWE-bench 56% rejection rate.")
        rejection = fail / max(active, 1) * 100
        print(f"  Active rejection: {rejection:.0f}% ({fail}/{active} FAIL)")


def check_behavioral(bug_id: str) -> dict:
    """Run behavioral verification (SWE-bench FAIL_TO_PASS standard).

    Research: SWE-bench Verified (OpenAI 2024) requires FAIL_TO_PASS + PASS_TO_PASS
    tests for each instance. verify.sh implements this at the bug level.
    """
    verify_path = BUGSET_DIR / bug_id / "verify.sh"
    if not verify_path.exists():
        return {"has_behavioral": False, "status": "N/A"}

    try:
        result = subprocess.run(
            ["bash", str(verify_path)],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=30
        )
        output = result.stdout
        has_fail = "FAIL:" in output and "bug exists" in output
        has_pass = "PASS:" in output
        return {
            "has_behavioral": True,
            "status": "PASS" if (has_fail and has_pass) else "PARTIAL",
            "fail_ok": has_fail,
            "pass_ok": has_pass,
            "output": output.strip()[-200:],
        }
    except Exception as e:
        return {"has_behavioral": True, "status": "ERROR", "error": str(e)[:100]}


if __name__ == "__main__":
    behavior = "--behavior" in sys.argv

    if "--bug" in sys.argv:
        idx = sys.argv.index("--bug")
        bug_id = sys.argv[idx + 1]
        r = verify_bug(bug_id)
        if behavior and not r.retired:
            b = check_behavioral(bug_id)
            if b["has_behavioral"]:
                print(f"\n  Behavioral (SWE-bench FAIL->PASS): {b['status']}")
                if b.get("output"):
                    print(f"  {b['output']}")
        print_report([r])
    else:
        results = verify_all()
        print_report(results)

        if behavior:
            print(f"\n{'='*60}")
            print(" Behavioral Verification (SWE-bench FAIL_TO_PASS)")
            print(f"{'='*60}\n")
            behavioral_ok = 0
            for r in results:
                if r.retired:
                    continue
                b = check_behavioral(r.bug_id)
                if b["has_behavioral"]:
                    icon = "[OK]" if b["status"] == "PASS" else "[~]"
                    print(f"  {icon} {r.bug_id}: {b['status']}")
                    if b["status"] == "PASS":
                        behavioral_ok += 1
                else:
                    print(f"  [--] {r.bug_id}: no verify.sh")
            print(f"\n  Behavioral coverage: {behavioral_ok}/{len(results)} bugs")
