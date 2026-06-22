"""Physical Gate: Block git checkout -- <file> (Git铁锁)."""
import sys
print("BLOCKED: git checkout -- <file> is forbidden by Git Gate.", file=sys.stderr)
print("Use git diff to inspect changes, then manually fix.", file=sys.stderr)
sys.exit(2)
