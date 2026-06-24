"""PostToolUse Hook: Auto-run drift check when skill files are modified."""
import sys, os, io, subprocess, json, re
from datetime import datetime
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

tool_name = os.environ.get("CLAUDE_TOOL_NAME", "")
file_path = os.environ.get("CLAUDE_TOOL_FILE_PATH", "")

SKILLS_DIR = "f:/ClaudeFiles/.claude/skills"
DRIFT_CHECK = "f:/ClaudeFiles/.claude/scripts/drift_check.py"
DRIFT_LOG = "f:/ClaudeFiles/.claude/benchmarks/bughunt/drift.log"
SKILL_HEALTH = "f:/ClaudeFiles/.claude/scripts/skill_health.py"


def extract_skill_name(filepath: str) -> str | None:
    """Extract skill name from file path.

    .claude/skills/缉凶.md -> 缉凶
    .claude/skills/火眼/SKILL.md -> 火眼
    """
    rel = os.path.relpath(filepath, SKILLS_DIR)
    parts = Path(rel).parts
    if not parts:
        return None

    # Top-level .md file
    if len(parts) == 1 and parts[0].endswith(".md"):
        name = parts[0].replace(".md", "")
        # Skip non-skill files (references/, _archived/, template)
        if name in ("SKILL_TEMPLATE", "providers"):
            return None
        return name

    # Subdirectory with SKILL.md
    if len(parts) >= 2 and parts[-1] == "SKILL.md":
        name = parts[0]
        if name.startswith("_"):
            return None  # Skip _archived
        return name

    # References directory
    if parts[0] in ("references", "_archived", "benchmarks"):
        return None

    return None


def should_check():
    """Only trigger for skill file edits."""
    if tool_name not in ("Edit", "Write"):
        return False

    # Must be under .claude/skills/ or .claude/benchmarks/bughunt/ (scoring changes)
    norm = os.path.normpath(file_path)
    if norm.startswith(os.path.normpath(SKILLS_DIR)):
        return True
    if "bughunt" in norm and norm.endswith(".py"):
        return True  # Scoring logic changes
    return False


if should_check():
    skill_name = extract_skill_name(file_path)

    # Run drift check on the specific skill
    if skill_name:
        try:
            result = subprocess.run(
                ["python", DRIFT_CHECK, "--skill", skill_name],
                capture_output=True, text=True, timeout=30,
                encoding='utf-8', errors='replace'
            )
            output = result.stdout.strip()
            if output:
                # Check for WARNING or DEGRADED
                if "WARNING" in output or "DEGRADED" in output:
                    print(f"⚠️ 飞轮: Skill漂移检测!")
                    print(f"  {output[:300]}")

                    # Log to drift.log
                    timestamp = datetime.now().isoformat()
                    status = "WARNING" if "WARNING" in output else "DEGRADED"
                    try:
                        with open(DRIFT_LOG, "a", encoding="utf-8") as f:
                            f.write(json.dumps({
                                "skill": skill_name,
                                "status": status,
                                "trigger": "PostToolUse",
                                "file": file_path,
                                "timestamp": timestamp,
                            }, ensure_ascii=False) + "\n")
                    except Exception:
                        pass
                elif "STABLE" in output:
                    # L0+L1 stable — now check L2 benchmark drift
                    try:
                        auto_bm = "f:/ClaudeFiles/.claude/scripts/auto_benchmark.py"
                        bm_result = subprocess.run(
                            ["python", auto_bm, "--skill", skill_name, "--max-drift", "5.0"],
                            capture_output=True, text=True, timeout=60,
                            encoding='utf-8', errors='replace'
                        )
                        if "DRIFT_DOWN" in bm_result.stdout:
                            print(f"⚠️ 飞轮 L2: 基准分数漂移!")
                            print(f"  {bm_result.stdout[-300:]}")
                    except Exception:
                        pass  # L2 check is best-effort, don't block
        except Exception as e:
            print(f"  Drift check skipped (error): {e}")

    # If scoring logic changed, run full health scan
    if "auto_scorer" in file_path or "bughunt_harness" in file_path:
        try:
            result = subprocess.run(
                ["python", SKILL_HEALTH],
                capture_output=True, text=True, timeout=30,
                encoding='utf-8', errors='replace'
            )
            # Only report issues
            if "Needs attention" in result.stdout and "0" not in result.stdout.split("Needs attention:")[-1][:5]:
                print("🔍 评分系统变更 — 健康检查:")
                print(result.stdout[-500:])
        except Exception:
            pass
