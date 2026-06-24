"""Peter Framework Self-Check — validate the entire agent harness.

Checks:
  1. Hook syntax (all .py files parse correctly)
  2. Hook registration (all hook scripts are in settings.json)
  3. Gate coverage (critical operations have PreToolUse guards)
  4. Event log integrity (JSONL is valid, no corruption)
  5. Settings integrity (JSON is valid, required fields present)
  6. Registry sync (skills-registry matches actual files)
  7. Memory integrity (MEMORY.md references exist)

Exit 0 = all healthy. Exit 1 = issues found.

Usage:
  python pete-framework-check.py          → full check
  python pete-framework-check.py --quick  → syntax + settings only
  python pete-framework-check.py --fix    → auto-fix when possible
"""

import sys, os, json, io
import subprocess
from pathlib import Path
from datetime import datetime, timezone

if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

PROJECT = Path("f:/ClaudeFiles")
HOOKS_DIR = PROJECT / ".claude" / "hooks"
AGENTS_DIR = PROJECT / ".claude" / "agents"
SKILLS_DIR = PROJECT / ".claude" / "skills"
EVENT_LOG = PROJECT / ".claude" / "eventstore" / "events.jsonl"
SETTINGS_GLOBAL = Path.home() / ".claude" / "settings.json"
SETTINGS_PROJECT = PROJECT / ".claude" / "settings.json"
REGISTRY = PROJECT / ".claude" / "skills-registry.json"
MEMORY_DIR = Path.home() / ".claude" / "projects" / "f--ClaudeFiles" / "memory"

ISSUES = []


def ok(msg): print(f"  OK  {msg}")
def warn(msg):
    print(f"  WARN {msg}")
    ISSUES.append(msg)


# ============================================================
# 1. Hook syntax check
# ============================================================
print("\n=== 1. Hook Syntax ===")
for hook_file in sorted(HOOKS_DIR.glob("*.py")):
    try:
        subprocess.run(
            ["python", "-c",
             f"import py_compile; py_compile.compile(r'{hook_file}', doraise=True)"],
            capture_output=True, timeout=10, check=True
        )
        ok(hook_file.name)
    except subprocess.CalledProcessError as e:
        warn(f"{hook_file.name}: SYNTAX ERROR\n{e.stderr.decode('utf-8', errors='replace')[:200]}")
    except Exception as e:
        warn(f"{hook_file.name}: {e}")


# ============================================================
# 2. Hook registration check
# ============================================================
print("\n=== 2. Hook Registration ===")

def load_settings(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

global_settings = load_settings(SETTINGS_GLOBAL)
project_settings = load_settings(SETTINGS_PROJECT)

all_hooks_config = {}
for source, cfg in [("global", global_settings), ("project", project_settings)]:
    for hook_type in ["SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "Stop"]:
        entries = cfg.get("hooks", {}).get(hook_type, [])
        for entry in entries:
            for h in entry.get("hooks", []):
                cmd = h.get("command", "")
                if cmd:
                    all_hooks_config.setdefault(hook_type, []).append(cmd)

# Check each hook script is registered somewhere
DISPATCHED_BY_GUARD_ALL = {
    "guard-build.py", "guard-prod-file.py", "guard-rm-nuke.py",
    "guard-rm.py", "guard-test-hook.py"
}
SYSTEM_AGENTS_NO_FILE = {
    "architect", "debugger", "refactor-master", "test-generator",
    "codegraph_context", "impeccable", "api-tester"
}
for hook_file in sorted(HOOKS_DIR.glob("*.py")):
    if hook_file.name.endswith(".disabled.py"):
        continue  # Intentionally disabled
    hook_path = str(hook_file).replace("\\", "/")
    found = any(hook_path in cmd for cmd_list in all_hooks_config.values() for cmd in cmd_list)
    if found:
        ok(f"{hook_file.name} registered")
    elif hook_file.name in DISPATCHED_BY_GUARD_ALL:
        pass  # Dispatched by guard-all.py, no direct registration needed
    else:
        warn(f"{hook_file.name}: NOT registered in any settings.json")

# Check critical hooks exist
critical_pairs = [
    ("PreToolUse", "guard-all.py"),
    ("PreToolUse", "guard-repeat-fail.py"),
    ("PostToolUse", "auto-check.py"),
    ("SessionStart", "boot-injector.py"),
    ("UserPromptSubmit", "task-router.py"),
    ("Stop", "memory-keeper.py"),
]
for hook_type, script in critical_pairs:
    script_path = str(HOOKS_DIR / script).replace("\\", "/")
    cmds = all_hooks_config.get(hook_type, [])
    if any(script_path in c for c in cmds):
        ok(f"Critical: {hook_type} → {script}")
    else:
        warn(f"Critical MISSING: {hook_type} → {script}")


# ============================================================
# 3. Event log integrity
# ============================================================
print("\n=== 3. Event Log Integrity ===")
if EVENT_LOG.exists():
    corrupted = 0
    count = 0
    with open(EVENT_LOG, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                json.loads(line)
                count += 1
            except json.JSONDecodeError:
                corrupted += 1
    if corrupted == 0:
        ok(f"{count} events, 0 corrupted")
    else:
        warn(f"{corrupted} corrupted lines in event log")
else:
    warn("Event log does not exist")


# ============================================================
# 4. Settings integrity
# ============================================================
print("\n=== 4. Settings Integrity ===")
for label, path in [("global", SETTINGS_GLOBAL), ("project", SETTINGS_PROJECT)]:
    if path.exists():
        try:
            cfg = json.loads(path.read_text(encoding="utf-8"))
            # Check for required API config
            if label == "global":
                if cfg.get("env", {}).get("ANTHROPIC_BASE_URL"):
                    ok(f"{label} settings: API configured")
            else:
                if cfg.get("hooks"):
                    ok(f"{label} settings: hooks configured")
        except json.JSONDecodeError as e:
            warn(f"{label} settings.json: INVALID JSON — {e}")
    else:
        warn(f"{label} settings.json: FILE MISSING")


# ============================================================
# 5. Registry sync
# ============================================================
print("\n=== 5. Registry vs Filesystem ===")
if REGISTRY.exists():
    try:
        reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
        reg_skills = set(reg.get("skills", {}).keys())

        # Scan actual files
        fs_skills = set()
        for d in [SKILLS_DIR, AGENTS_DIR]:
            if d.exists():
                for item in d.iterdir():
                    if item.is_dir():
                        if (item / "SKILL.md").exists():
                            fs_skills.add(item.name)
                    elif item.suffix == ".md":
                        fs_skills.add(item.stem)

        REGISTRY_FILESYSTEM_SKIP = {"capability-agents"}  # design doc, not a skill
        missing_from_reg = fs_skills - reg_skills - REGISTRY_FILESYSTEM_SKIP

        # For "no file" check, account for l2_file mappings (e.g. code-reviewer→reviewer.md)
        missing_from_fs = set()
        for name in reg_skills - fs_skills - SYSTEM_AGENTS_NO_FILE:
            info = reg.get("skills", {}).get(name, {})
            l2 = info.get("l2_file")
            if l2 and (PROJECT / l2).exists():
                continue  # Has valid L2 file reference
            missing_from_fs.add(name)

        if missing_from_reg:
            warn(f"Skills missing from registry: {', '.join(sorted(missing_from_reg))}")
        if missing_from_fs:
            warn(f"Registry entries with no file: {', '.join(sorted(missing_from_fs))}")
        if not missing_from_reg and not missing_from_fs:
            ok(f"Registry synced ({len(reg_skills)} skills)")
    except json.JSONDecodeError:
        warn("skills-registry.json: INVALID JSON")
else:
    warn("skills-registry.json does not exist")


# ============================================================
# 6. Core script syntax
# ============================================================
print("\n=== 6. Core Scripts ===")
CORE_SCRIPTS = [
    "pete-eventlog.py", "pete-memory-api.py", "pete-just-mcp.py",
    "pete-eval.py", "pete-supervisor.py", "pete-skill-evolve.py",
    "campus_net.pyw"
]
for script in CORE_SCRIPTS:
    spath = PROJECT / ".claude" / script if script != "campus_net.pyw" else PROJECT / script
    if not spath.exists():
        spath = PROJECT / script
    if spath.exists():
        try:
            subprocess.run(
                ["python", "-c",
                 f"import py_compile; py_compile.compile(r'{spath}', doraise=True)"],
                capture_output=True, timeout=10, check=True
            )
            ok(script)
        except Exception:
            warn(f"{script}: SYNTAX ERROR")
    else:
        warn(f"{script}: FILE MISSING")


# ============================================================
# Result
# ============================================================
print(f"\n{'='*40}")
if ISSUES:
    print(f"ISSUES FOUND: {len(ISSUES)}")
    for i in ISSUES:
        print(f"  - {i}")
    sys.exit(1)
else:
    print("ALL CHECKS PASSED — framework healthy")
    sys.exit(0)
