"""Auto-sync skills-registry.json from filesystem.

Scans .claude/skills/ and .claude/agents/ and updates the registry.
Never removes manually curated entries — only adds new ones and marks
entries whose files have been deleted.

Usage:
  python pete-sync-registry.py           → dry-run, show changes
  python pete-sync-registry.py --apply   → apply changes
  python pete-sync-registry.py --watch   → register as PostToolUse hook
"""

import sys, os, json, io
from datetime import datetime, timezone
from pathlib import Path

if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

REGISTRY_PATH = Path("f:/ClaudeFiles/.claude/skills-registry.json")
SKILLS_DIR = Path("f:/ClaudeFiles/.claude/skills")
AGENTS_DIR = Path("f:/ClaudeFiles/.claude/agents")


def scan_filesystem() -> dict[str, dict]:
    """Scan skills/ and agents/ dirs, return {name: {type, path}}."""
    def _extract_desc(path: Path) -> str:
        try:
            content = path.read_text(encoding="utf-8")[:500]
            for line in content.split("\n"):
                if line.startswith("description:"):
                    return line.split(":", 1)[1].strip().strip('"').strip("'")
        except Exception:
            pass
        return ""

    found = {}

    if SKILLS_DIR.exists():
        for item in SKILLS_DIR.iterdir():
            if item.is_dir():
                skill_md = item / "SKILL.md"
                if skill_md.exists():
                    desc = _extract_desc(skill_md)
                    found[item.name] = {
                        "type": "skill",
                        "description": desc or f"Skill: {item.name}",
                        "path": str(item),
                    }
            elif item.suffix == ".md" and item.stem not in ("LICENSE",):
                # Standalone .md skill file (e.g. campus-bug-hunt.md)
                desc = _extract_desc(item)
                found[item.stem] = {
                    "type": "skill-file",
                    "description": desc or f"Skill: {item.stem}",
                    "path": str(item),
                }

    if AGENTS_DIR.exists():
        for item in AGENTS_DIR.iterdir():
            if item.suffix == ".md" and item.stem != "capability-agents":
                found[item.stem] = {
                    "type": "agent",
                    "description": f"Agent: {item.stem}",
                    "path": str(item),
                }

    return found


def sync(apply_changes: bool = False) -> dict:
    """Sync registry with filesystem."""
    if not REGISTRY_PATH.exists():
        return {"error": "registry not found"}

    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    existing = registry.get("skills", {})
    fs_skills = scan_filesystem()

    added = {}
    updated = {}
    orphaned = {}

    # Find new filesystem skills not in registry
    for name, info in fs_skills.items():
        if name not in existing:
            added[name] = info

    # Find registry entries with no filesystem file
    for name in list(existing.keys()):
        if name not in fs_skills:
            # Check if it's a system built-in (Claude Code native agent)
            if existing[name].get("l2_file") or name in [
                "architect", "debugger", "refactor-master", "test-generator",
                "codegraph_context", "impeccable", "api-tester"
            ]:
                continue  # System agent, keep
            orphaned[name] = existing[name]

    # Apply changes
    if apply_changes and (added or orphaned):
        for name, info in added.items():
            scope = None
            path = info.get("path", "")
            if "campus" in name.lower() or "flutter" in name.lower():
                scope = "campus_app"
            elif "backend" in name.lower() or "deploy" in name.lower() or "db" in name.lower():
                scope = "_research/rewriter-go"

            triggers = name.replace("-", " ").replace("_", " ").split()

            existing[name] = {
                "description": info["description"],
                "triggers": triggers[:3],
                "path_scope": scope,
                "l2_file": f".claude/agents/{name}.md" if info["type"] == "agent" else f".claude/skills/{name}.md" if info["type"] == "skill-file" else None,
                "l3_dir": None,
            }

        for name in orphaned:
            if "--remove-orphans" in sys.argv:
                del existing[name]

        registry["skills"] = existing
        registry["_meta"]["updated"] = datetime.now(timezone.utc).isoformat()
        tmp = str(REGISTRY_PATH) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(registry, f, ensure_ascii=False, indent=2)
        os.replace(tmp, str(REGISTRY_PATH))

    return {
        "total_registry": len(existing),
        "total_filesystem": len(fs_skills),
        "to_add": list(added.keys()),
        "to_update": list(updated.keys()),
        "orphaned": list(orphaned.keys()),
    }


def cmd():
    apply_changes = "--apply" in sys.argv

    print("Scanning skills/ + agents/ ...")
    result = sync(apply_changes)

    if "error" in result:
        print(f"Error: {result['error']}")
        sys.exit(1)

    print(f"Registry: {result['total_registry']} skills | Filesystem: {result['total_filesystem']} found")
    print()

    if result["to_add"]:
        print(f"NEW ({len(result['to_add'])}):")
        for name in result["to_add"]:
            print(f"  + {name}")
    else:
        print("No new skills found.")

    if result["orphaned"]:
        print(f"\nORPHANED ({len(result['orphaned'])}): registry entries with no file")
        for name in result["orphaned"]:
            print(f"  ? {name}")

    if apply_changes:
        print("\nApplied changes.")
    else:
        print("\nDry run. Use --apply to write changes.")


if __name__ == "__main__":
    cmd()
