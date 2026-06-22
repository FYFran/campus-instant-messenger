"""Physical Gate: Block git push --force."""
import sys
print("BLOCKED: git push --force is forbidden by Physical Gate.", file=sys.stderr)
print("Use a regular push or create a new branch.", file=sys.stderr)
sys.exit(2)
