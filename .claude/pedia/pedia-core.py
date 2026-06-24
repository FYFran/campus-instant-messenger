"""Pedia Core — Capture → Graduate → Prevent 学习回路.

Usage:
  python pedia-core.py capture <BugPedia|ToolPedia|RulePedia|WorkPedia> "<entry>"
  python pedia-core.py check <domain>   — check for graduated rules
  python pedia-core.py graduate <domain> — check thresholds, graduate patterns
"""
import sys, os, json, hashlib
from datetime import datetime
from collections import Counter

PEDIA_DIR = os.path.dirname(os.path.abspath(__file__))
GRADUATED_DIR = os.path.join(PEDIA_DIR, "graduated")
os.makedirs(GRADUATED_DIR, exist_ok=True)

DOMAINS = {
    "BugPedia": {"threshold": 3, "file": "bugs.jsonl"},
    "ToolPedia": {"threshold": 5, "file": "tool-usage.jsonl"},
    "RulePedia": {"threshold": 1, "file": "rule-violations.jsonl"},
    "WorkPedia": {"threshold": 3, "file": "workflows.jsonl"},
}

def capture(domain, entry):
    """Append an event to the domain's append-only log."""
    if domain not in DOMAINS:
        print(f"Unknown domain: {domain}")
        sys.exit(1)

    log_path = os.path.join(PEDIA_DIR, domain, DOMAINS[domain]["file"])
    record = {
        "timestamp": datetime.now().isoformat(),
        "entry": entry,
        "hash": hashlib.md5(entry.encode()).hexdigest()[:8]
    }
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    # Check if this entry should trigger graduation
    _check_graduation(domain)

def graduate(domain):
    """Force-check domain for graduation candidates."""
    if domain not in DOMAINS:
        print(f"Unknown domain: {domain}")
        sys.exit(1)
    _check_graduation(domain)

def _check_graduation(domain):
    """Check if any pattern in domain has crossed graduation threshold."""
    log_path = os.path.join(PEDIA_DIR, domain, DOMAINS[domain]["file"])
    threshold = DOMAINS[domain]["threshold"]

    if not os.path.exists(log_path):
        return

    entries = []
    with open(log_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))

    # Count patterns by hash
    hashes = [e["hash"] for e in entries]
    counts = Counter(hashes)

    for h, count in counts.items():
        if count >= threshold:
            grad_path = os.path.join(GRADUATED_DIR, f"{domain}-{h}.md")
            if not os.path.exists(grad_path):
                # Find the actual entry
                sample = next(e["entry"] for e in entries if e["hash"] == h)
                with open(grad_path, "w", encoding="utf-8") as f:
                    f.write(f"""# {domain} Graduated Rule ({h})
**触发次数**: {count}/{threshold}
**首次发现**: {entries[0]['timestamp']}
**最近触发**: {entries[-1]['timestamp']}

## 规则
{sample}

## 预防措施
此规则已自动注入 SessionStart。Agent 在每次会话启动时自动加载。
""")
                print(f"🎓 GRADUATED: {domain}/{h} — count {count} >= {threshold}")

def list_graduated():
    """List all graduated rules for SessionStart injection."""
    rules = []
    if os.path.exists(GRADUATED_DIR):
        for f in sorted(os.listdir(GRADUATED_DIR)):
            if f.endswith(".md"):
                rules.append(os.path.join(GRADUATED_DIR, f))
    return rules

def inject_rules():
    """Print all graduated rules for injection into context."""
    rules = list_graduated()
    if rules:
        print("## 🛡️ 免疫规则（自动注入）\n")
        for r in rules:
            name = os.path.basename(r).replace(".md", "")
            with open(r, encoding="utf-8") as f:
                content = f.read()
            # Extract just the rule part
            print(f"**{name}**: {content.split('## 规则')[1].split('## 预防措施')[0].strip() if '## 规则' in content else content[:200]}")
            print()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: pedia-core.py <capture|check|graduate|inject> [domain] [entry]")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "capture":
        capture(sys.argv[2], sys.argv[3])
    elif cmd == "graduate":
        graduate(sys.argv[2]) if len(sys.argv) > 2 else [graduate(d) for d in DOMAINS]
    elif cmd == "check":
        domain = sys.argv[2] if len(sys.argv) > 2 else None
        domains = [domain] if domain else DOMAINS.keys()
        for d in domains:
            log_path = os.path.join(PEDIA_DIR, d, DOMAINS[d]["file"])
            count = 0
            if os.path.exists(log_path):
                with open(log_path, encoding="utf-8") as f:
                    count = sum(1 for _ in f)
            print(f"{d}: {count} entries (threshold: {DOMAINS[d]['threshold']})")
    elif cmd == "inject":
        inject_rules()
