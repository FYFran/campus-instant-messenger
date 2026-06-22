"""Peter Just MCP — expose justfile recipes as structured tools.

Inspired by just-mcp (PromptExecution). Instead of having Claude read
and parse the raw justfile (wasting context tokens), this script
provides structured tool access to just recipes.

Usage (MCP mode):
  python pete-just-mcp.py list           → JSON list of all recipes
  python pete-just-mcp.py run <recipe>   → execute a recipe
  python pete-just-mcp.py info <recipe>  → show recipe details
  python pete-just-mcp.py validate       → check justfile syntax
"""

import sys, os, json, subprocess, io, re
from pathlib import Path

if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

JUSTFILE = Path("f:/ClaudeFiles/justfile")
JUST_BIN = "just"


def _just(*args) -> tuple[int, str]:
    """Run just command, return (exit_code, output)."""
    try:
        r = subprocess.run(
            [JUST_BIN] + list(args),
            capture_output=True, text=True, timeout=30,
            cwd="f:/ClaudeFiles",
            encoding="utf-8", errors="replace"
        )
        out = (r.stdout or "") + (r.stderr or "")
        return r.returncode, out.strip()
    except FileNotFoundError:
        return 127, "just not installed"
    except subprocess.TimeoutExpired:
        return 124, "timeout"


def list_recipes() -> list[dict]:
    """List all recipes with descriptions (structured JSON)."""
    code, output = _just("--list")
    if code != 0:
        return [{"error": output}]

    recipes = []
    for line in output.split("\n"):
        line = line.strip()
        if not line:
            continue
        # just --list format: "recipe_name              # description"
        parts = line.split("#", 1)
        name = parts[0].strip()
        desc = parts[1].strip() if len(parts) > 1 else ""
        recipes.append({"name": name, "description": desc})

    return recipes


def run_recipe(name: str, *args) -> dict:
    """Execute a specific recipe."""
    code, output = _just(name, *args)
    return {
        "recipe": name,
        "exit_code": code,
        "output": output,
        "success": code == 0,
    }


def info_recipe(name: str) -> dict:
    """Get detailed info about a recipe."""
    # Extract recipe body from justfile
    if not JUSTFILE.exists():
        return {"error": "justfile not found"}

    content = JUSTFILE.read_text(encoding="utf-8")
    # Find recipe definition
    pattern = rf"^{name}\s*:"
    lines = content.split("\n")
    recipe_lines = []
    in_recipe = False
    indent = ""

    for line in lines:
        if re.match(pattern, line):
            in_recipe = True
            recipe_lines.append(line)
            continue
        if in_recipe:
            if line.strip() == "" and recipe_lines:
                break
            if not line.startswith(" ") and not line.startswith("\t") and line.strip():
                break
            recipe_lines.append(line)

    return {
        "name": name,
        "body": "\n".join(recipe_lines) if recipe_lines else "(recipe not found in file)",
        "line_count": len(recipe_lines),
    }


def validate() -> dict:
    """Validate justfile syntax."""
    code, output = _just("--dump")
    return {
        "valid": code == 0,
        "output": output[:500] if code != 0 else "OK",
    }


def cmd():
    if len(sys.argv) < 2:
        print("Usage: pete-just-mcp.py <list|run|info|validate> [args...]")
        sys.exit(1)

    cmd_name = sys.argv[1]
    args = sys.argv[2:]

    if cmd_name == "list":
        recipes = list_recipes()
        # JSON output for MCP
        print(json.dumps(recipes, ensure_ascii=False, indent=2))

    elif cmd_name == "run":
        if not args:
            print(json.dumps({"error": "recipe name required"}))
            sys.exit(1)
        result = run_recipe(args[0], *args[1:])
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif cmd_name == "info":
        if not args:
            print(json.dumps({"error": "recipe name required"}))
            sys.exit(1)
        result = info_recipe(args[0])
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif cmd_name == "validate":
        result = validate()
        print(json.dumps(result, ensure_ascii=False))

    else:
        print(json.dumps({"error": f"unknown command: {cmd_name}"}))


if __name__ == "__main__":
    cmd()
