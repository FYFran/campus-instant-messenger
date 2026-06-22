"""
BugHuntBench Bug Injection System v2.

Line-based injection: find → replace → run agent → revert.
Each injection is a (file, old_line, new_line) tuple.
Revert uses git checkout on modified files.

Usage:
    python bug_injection.py inject B02   # Apply injection
    python bug_injection.py revert B02   # Revert via git checkout
    python bug_injection.py list         # List available
"""

import subprocess
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

BENCH_DIR = Path(__file__).parent
REPO_ROOT = Path("f:/ClaudeFiles")


@dataclass
class InjectOp:
    """Single injection operation: replace old_text with new_text in file."""
    file: str           # Relative to repo root
    old_text: str       # Text to find and replace
    new_text: str       # Replacement text


@dataclass
class InjectionSpec:
    """Full injection spec for a bug."""
    bug_id: str
    description: str
    injectable: bool
    tag: str  # Marker comment to verify injection
    ops: list[InjectOp] = field(default_factory=list)
    modified_files: list[str] = field(default_factory=list)


# ============================================================
# Injection Definitions
# ============================================================

INJECTIONS: dict[str, InjectionSpec] = {}

def _reg(spec: InjectionSpec):
    INJECTIONS[spec.bug_id] = spec

# B01: Remove ON CONFLICT from signup INSERT (race condition)
_reg(InjectionSpec(
    bug_id="B02",
    description="Remove ON CONFLICT from signup INSERT — reintroduce race condition",
    injectable=True,
    tag="INJECT-B02",
    ops=[
        InjectOp(
            file="campus_go/internal/handlers/activities.go",
            old_text='"INSERT INTO signups (activity_id, user_id, status, signed_at) VALUES ($1,$2,$3,$4) ON CONFLICT (activity_id, user_id) DO NOTHING RETURNING id",',
            new_text='"INSERT INTO signups (activity_id, user_id, status, signed_at) VALUES ($1,$2,$3,$4) RETURNING id",  // INJECT-B02: ON CONFLICT removed',
        ),
    ],
    modified_files=["campus_go/internal/handlers/activities.go"],
))

# B06: Reverse state machine logic
_reg(InjectionSpec(
    bug_id="B06",
    description="Invert approval_required logic — reintroduce state machine stuck",
    injectable=True,
    tag="INJECT-B06",
    ops=[
        InjectOp(
            file="campus_go/internal/handlers/activities.go",
            old_text='\t\tinitialStatus := "pending"\n\t\tif signupMode == "first_come" {\n\t\t\tinitialStatus = "selected"\n\t\t}',
            new_text='\t\t// INJECT-B06: first_come auto-select removed — all signups stay pending\n\t\tinitialStatus := "pending"',
        ),
    ],
    modified_files=["campus_go/internal/handlers/activities.go"],
))

# B09: Remove await
_reg(InjectionSpec(
    bug_id="B09",
    description="Remove await from update_user_points — reintroduce coroutine not executed",
    injectable=True,
    tag="INJECT-B09",
    ops=[
        InjectOp(
            file="campus_app/server/main.py",
            old_text="await update_user_points",
            new_text="update_user_points  # INJECT-B09: await removed",
        ),
    ],
    modified_files=["campus_app/server/main.py"],
))

# B01: rows.Err() already absent — bug naturally present, agent diagnoses from description
_reg(InjectionSpec(
    bug_id="B01", description="rows.Err() missing in ListActivities — naturally present in code",
    injectable=False, tag="",
))

# B09: update_user_points() doesn't exist in current main.py
_reg(InjectionSpec(
    bug_id="B09", description="missing await — function restructured, agent diagnoses from description",
    injectable=False, tag="",
))

# B10: N+1 pattern (correlated subquery still present, inject makes it obvious)
_reg(InjectionSpec(
    bug_id="B10",
    description="Make N+1 more obvious by removing correlated subquery",
    injectable=True,
    tag="INJECT-B10",
    ops=[
        InjectOp(
            file="campus_go/internal/handlers/activities.go",
            old_text='a.max_participants, (SELECT COUNT(*) FROM signups WHERE activity_id=a.id),',
            new_text='a.max_participants, 0 as signup_count,  // INJECT-B10: N+1 — subquery removed',
        ),
    ],
    modified_files=["campus_go/internal/handlers/activities.go"],
))

# Env-only bugs
for bid, desc in [
    ("B03", "strings.Contains college matching — architecture shifted"),
    ("B04", "int() truncation — Python code restructured"),
    ("B05", "nginx proxy_pass wrong port — infrastructure bug"),
    ("B07", "Go 1.23 NULL Scan + SQLite mismatch — environment bug"),
    ("B08", "NOT_A_BUG — correct behavior, always identifiable"),
]:
    _reg(InjectionSpec(
        bug_id=bid, description=desc, injectable=False, tag="",
    ))


# ============================================================
# Injection Manager
# ============================================================

class InjectionManager:
    def __init__(self, repo_root: Path = REPO_ROOT):
        self.repo_root = repo_root
        self._applied: set[str] = set()

    def inject(self, bug_id: str) -> bool:
        """Apply injection for a bug. Returns True if successful."""
        spec = INJECTIONS.get(bug_id)
        if not spec:
            print(f"  Unknown bug: {bug_id}")
            return False
        if not spec.injectable:
            return True  # env-only — no injection needed

        for op in spec.ops:
            filepath = self.repo_root / op.file
            if not filepath.exists():
                print(f"  File not found: {filepath}")
                return False

            content = filepath.read_text(encoding="utf-8")
            if op.old_text not in content:
                # Check if already injected
                if spec.tag in content:
                    self._applied.add(bug_id)
                    return True
                print(f"  Pattern not found in {op.file}")
                return False

            new_content = content.replace(op.old_text, op.new_text, 1)
            filepath.write_text(new_content, encoding="utf-8")

        self._applied.add(bug_id)
        return True

    def revert(self, bug_id: str) -> bool:
        """Revert injection via git checkout."""
        spec = INJECTIONS.get(bug_id)
        if not spec or not spec.injectable:
            return True

        for f in spec.modified_files:
            filepath = self.repo_root / f
            subprocess.run(
                ["git", "checkout", "--", str(filepath)],
                cwd=self.repo_root,
                capture_output=True,
            )

        self._applied.discard(bug_id)
        return True

    def is_injected(self, bug_id: str) -> bool:
        """Check if a bug injection is currently applied."""
        spec = INJECTIONS.get(bug_id)
        if not spec or not spec.injectable:
            return False
        for op in spec.ops:
            filepath = self.repo_root / op.file
            if filepath.exists():
                if spec.tag in filepath.read_text(encoding="utf-8"):
                    return True
        return False

    def revert_all(self):
        for bug_id in list(self._applied):
            self.revert(bug_id)

    @property
    def injectable_bugs(self) -> list[str]:
        return [bid for bid, s in INJECTIONS.items() if s.injectable]

    @property
    def env_only_bugs(self) -> list[str]:
        return [bid for bid, s in INJECTIONS.items() if not s.injectable]


def main():
    if len(sys.argv) < 2:
        print("Usage: python bug_injection.py <inject|revert|list|check> [bug_id]")
        sys.exit(1)

    cmd = sys.argv[1]
    mgr = InjectionManager()

    if cmd == "list":
        print("=== Injectable Bugs ===")
        for bid in mgr.injectable_bugs:
            print(f"  {bid}: {INJECTIONS[bid].description}")
        print("\n=== Environment-Only Bugs ===")
        for bid in mgr.env_only_bugs:
            print(f"  {bid}: {INJECTIONS[bid].description}")

    elif cmd == "check":
        bug_id = sys.argv[2] if len(sys.argv) > 2 else None
        if bug_id:
            injected = mgr.is_injected(bug_id)
            print(f"{bug_id}: {'INJECTED' if injected else 'CLEAN'}")
        else:
            for bid in INJECTIONS:
                injected = mgr.is_injected(bid)
                if injected:
                    print(f"{bid}: INJECTED")

    elif cmd == "inject":
        bug_id = sys.argv[2]
        ok = mgr.inject(bug_id)
        print(f"{bug_id}: {'INJECTED' if ok else 'FAILED'}")
        sys.exit(0 if ok else 1)

    elif cmd == "revert":
        bug_id = sys.argv[2] if len(sys.argv) > 2 else None
        if bug_id:
            mgr.revert(bug_id)
            print(f"{bug_id}: REVERTED")
        else:
            mgr.revert_all()
            print("All reverted")

    else:
        print(f"Unknown: {cmd}")


if __name__ == "__main__":
    main()
