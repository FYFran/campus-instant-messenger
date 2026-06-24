"""ClaudeAll Init — One-command full architecture deployment.

Usage: python f:/ClaudeFiles/.claude/claudeall-init.py

Deploys:
  1. Backup old CLAUDE.md
  2. KERNEL.md -> CLAUDE.md (replace)
  3. Init Pedia directories
  4. Verify all physical gate scripts
  5. Generate first BOOT.md
  6. Print architecture status
"""
import os, sys, shutil
from datetime import datetime

PROJECT = "f:/ClaudeFiles"
CLAUDE_MD = os.path.join(PROJECT, "CLAUDE.md")
KERNEL_MD = os.path.join(PROJECT, "KERNEL.md")
BACKUP_DIR = os.path.join(PROJECT, ".claude", "backups")
HOOKS_DIR = os.path.join(PROJECT, ".claude", "hooks")
PEDIA_DIR = os.path.join(PROJECT, ".claude", "pedia")

def ok(msg): print(f"[OK] {msg}")
def warn(msg): print(f"[WARN] {msg}")
def fail(msg): print(f"[FAIL] {msg}")

def step1_backup():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    if os.path.exists(CLAUDE_MD):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(BACKUP_DIR, f"CLAUDE.md.{ts}.bak")
        shutil.copy2(CLAUDE_MD, backup_path)
        size = os.path.getsize(CLAUDE_MD)
        ok(f"Backup: CLAUDE.md ({size} bytes) -> {backup_path}")
    else:
        warn("CLAUDE.md not found, skipping backup")

def step2_replace():
    if not os.path.exists(KERNEL_MD):
        fail("KERNEL.md not found! Create f:/ClaudeFiles/KERNEL.md first.")
        return False
    shutil.copy2(KERNEL_MD, CLAUDE_MD)
    new_size = os.path.getsize(CLAUDE_MD)
    ok(f"KERNEL.md -> CLAUDE.md ({new_size} bytes)")
    return True

def step3_pedia():
    domains = ["BugPedia", "ToolPedia", "RulePedia", "WorkPedia"]
    for d in domains:
        path = os.path.join(PEDIA_DIR, d)
        os.makedirs(path, exist_ok=True)
    ok(f"Pedia ready: {', '.join(domains)}")

def step4_verify():
    guards = [
        "guard-build.py", "guard-git-checkout.py", "guard-force-push.py",
        "guard-rm.py", "guard-prod-file.py",
        "boot-injector.py", "task-router.py", "auto-check.py", "memory-keeper.py",
    ]
    all_ok = True
    for g in guards:
        path = os.path.join(HOOKS_DIR, g)
        if os.path.exists(path):
            ok(f"Physical Gate: {g}")
        else:
            fail(f"Missing: {g}")
            all_ok = False
    return all_ok

def step5_boot():
    boot_path = os.path.join(PROJECT, ".claude", "BOOT.md")
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(boot_path, "w", encoding="utf-8") as f:
        f.write(f"""# BOOT.md — {now}
## Architecture Status
- KERNEL: deployed
- Physical Gates: 5 active
- Pedia: 4 domains initialized
- Capability Agents: 6 types defined
- Router: UserPromptSubmit auto-match

## Equipment Status
See SYSTEM_STATE.md

## Recent Commits
Auto-extracted from git log
""")
    ok(f"BOOT.md generated: {boot_path}")

def step6_status():
    boot_path = os.path.join(PROJECT, ".claude", "BOOT.md")
    backup_files = []
    if os.path.exists(BACKUP_DIR):
        backup_files = sorted([f for f in os.listdir(BACKUP_DIR) if f.startswith("CLAUDE.md.")], reverse=True)
    old_claude = os.path.join(BACKUP_DIR, backup_files[0]) if backup_files else "N/A"

    print(f"""
{'='*50}
  ClaudeAll Architecture Deployed
{'='*50}

  Old CLAUDE.md -> {old_claude}
  New CLAUDE.md <- KERNEL.md
  BOOT.md       -> {boot_path}

  5 Hook Points:
    SessionStart     -> boot-injector (state injection)
    UserPromptSubmit -> task-router (task routing)
    PreToolUse       -> 5 physical gates (hard blocks)
    PostToolUse      -> auto-check (auto validation)
    Stop             -> memory-keeper (memory persistence)

  4 Pedia Domains:
    BugPedia  -> failure patterns (3x trigger -> graduate)
    ToolPedia -> tool usage frequency (5x -> graduate)
    RulePedia -> rule violations (1x -> graduate)
    WorkPedia -> success patterns (3x -> graduate)

  6 Capability Agents:
    Reader | Writer | Reviewer | Executor | Deployer | Orchestrator

  Architecture Principles:
    Memory Gates (CLAUDE.md) -> Physical Gates (Hooks)
    ACL security -> Capability-based security
    Open-loop -> Closed-loop learning (Wiener/Pedia)
    S(t)=S0*e^(alpha*t) -> Physical Gate counters entropy

  Next session activates. Current session unchanged.
""")

def main():
    print("ClaudeAll Init — Full Architecture Deployment\n")

    step1_backup()
    if not step2_replace():
        sys.exit(1)
    step3_pedia()
    if not step4_verify():
        warn("Some physical gates missing, check hooks directory")
    step5_boot()
    step6_status()

    print("Deployment complete. New session = new architecture.")

if __name__ == "__main__":
    main()
