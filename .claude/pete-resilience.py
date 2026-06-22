"""Peter Resilience — backup, verify, and restore critical framework files.

Usage:
  python pete-resilience.py backup        → snapshot all critical files
  python pete-resilience.py verify        → compare current vs last backup
  python pete-resilience.py restore       → restore from last backup (DRY RUN)
  python pete-resilience.py restore --force  → actually restore
  python pete-resilience.py list          → show backup history
"""

import sys, os, json, io, hashlib, shutil
from datetime import datetime, timezone
from pathlib import Path

if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BACKUP_DIR = Path("f:/ClaudeFiles/.claude/backups/resilience")
CRITICAL_FILES = [
    ".claude/settings.json",
    ".claude/settings.local.json",
    ".claude/CLAUDE.md",
    ".claude/skills-registry.json",
    ".claude/eventstore/events.jsonl",
    ".claude/hooks/task-router.py",
    ".claude/hooks/guard-all.py",
    ".claude/hooks/guard-repeat-fail.py",
    ".claude/hooks/auto-check.py",
    ".claude/hooks/boot-injector.py",
    ".claude/hooks/memory-keeper.py",
    "CLAUDE.md",
    "KERNEL.md",
]

BACKUP_DIR.mkdir(parents=True, exist_ok=True)
PROJECT = Path("f:/ClaudeFiles")


def file_hash(path: Path) -> str:
    """SHA256 of file content."""
    if not path.exists():
        return "MISSING"
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def backup():
    """Create a timestamped snapshot of all critical files."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    snapshot_dir = BACKUP_DIR / ts
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    manifest = {"timestamp": ts, "files": {}}

    for rel_path in CRITICAL_FILES:
        src = PROJECT / rel_path
        if src.exists():
            dst = snapshot_dir / rel_path.replace("/", "_").replace("\\", "_")
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            h = file_hash(src)
            manifest["files"][rel_path] = {"hash": h, "size": src.stat().st_size}
        else:
            manifest["files"][rel_path] = {"hash": "MISSING", "size": 0}

    manifest_path = snapshot_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))

    print(f"Backup: {ts}")
    print(f"Files: {len([f for f in manifest['files'].values() if f['hash'] != 'MISSING'])}/{len(CRITICAL_FILES)}")
    print(f"Location: {snapshot_dir}")

    # Cleanup: keep last 10 backups
    snapshots = sorted(BACKUP_DIR.glob("20*"))
    for old in snapshots[:-10]:
        shutil.rmtree(old)

    return manifest


def verify():
    """Compare current files against latest backup."""
    snapshots = sorted(BACKUP_DIR.glob("20*"))
    if not snapshots:
        print("No backups found. Run 'backup' first.")
        return

    latest = snapshots[-1]
    manifest_path = latest / "manifest.json"
    if not manifest_path.exists():
        print(f"Manifest missing in {latest.name}")
        return

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    print(f"Comparing against backup: {manifest['timestamp']}")
    print()

    changed = 0
    missing = 0

    for rel_path, info in manifest["files"].items():
        src = PROJECT / rel_path
        old_hash = info["hash"]
        new_hash = file_hash(src)

        if new_hash == "MISSING":
            print(f"  LOST  {rel_path}")
            missing += 1
        elif new_hash != old_hash:
            print(f"  CHANGED {rel_path}")
            changed += 1

    if changed == 0 and missing == 0:
        print("  All files unchanged since last backup.")
    else:
        print(f"\n{changed} changed, {missing} missing.")


def restore(force: bool = False):
    """Restore from latest backup."""
    snapshots = sorted(BACKUP_DIR.glob("20*"))
    if not snapshots:
        print("No backups found.")
        return

    latest = snapshots[-1]
    manifest_path = latest / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    print(f"Restore from: {manifest['timestamp']}")
    if not force:
        print("DRY RUN — use --force to actually restore")
        print()

    for rel_path, info in manifest["files"].items():
        if info["hash"] == "MISSING":
            continue
        backup_file = latest / rel_path.replace("/", "_").replace("\\", "_")
        target = PROJECT / rel_path

        if force:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup_file, target)
            print(f"  RESTORED {rel_path}")
        else:
            exists = "EXISTS" if target.exists() else "MISSING"
            print(f"  [dry] {rel_path} ({exists})")

    if force:
        print(f"\nRestored {len(manifest['files'])} files from backup.")


def list_backups():
    """Show backup history."""
    snapshots = sorted(BACKUP_DIR.glob("20*"))
    for s in snapshots:
        mf = s / "manifest.json"
        if mf.exists():
            m = json.loads(mf.read_text(encoding="utf-8"))
            count = len([f for f in m["files"].values() if f["hash"] != "MISSING"])
            print(f"  {m['timestamp']}: {count} files")


def cmd():
    if len(sys.argv) < 2:
        print("Usage: pete-resilience.py <backup|verify|restore|list>")
        sys.exit(1)

    cmd_name = sys.argv[1]

    if cmd_name == "backup":
        backup()
    elif cmd_name == "verify":
        verify()
    elif cmd_name == "restore":
        restore(force="--force" in sys.argv)
    elif cmd_name == "list":
        list_backups()
    else:
        print(f"Unknown: {cmd_name}")


if __name__ == "__main__":
    cmd()
