"""
皮特 跨会话错误记忆索引器
扫描 .fixes/ 目录 → 提取 bug 模式 → 检测同模式重复 → 建议 F-rule

借鉴: No-No Debug (29→6 errors/week, cross-session memory)
用法: python pete-memory-index.py scan    # 扫描并报告
      python pete-memory-index.py suggest  # 建议候选 F-rule
"""

import re
from pathlib import Path
from datetime import datetime
from collections import Counter, defaultdict

FIXES_DIR = Path(".fixes")
PATTERNS_FILE = Path(".claude/benchmarks/bughunt/bug-patterns.md")

# Pattern extraction rules: keyword → pattern name
PATTERN_RULES = {
    "nil deref|nil pointer|nil pointer dereference": "nil-deref",
    "race condition|TOCTOU|concurrent|竞态|ON CONFLICT": "race-condition",
    "missing await|coroutine|GC回收": "missing-await",
    "N\\+1|correlated subquery|performance.*slow|越来越慢": "n-plus-1",
    "strings\\.Contains|部分匹配|partial match|substring": "imprecise-match",
    "int\\(\\)|truncat|截断|round": "type-truncation",
    "nginx|proxy_pass|port.*95\\d\\d|配置回退": "nginx-config",
    "JWT_SECRET|token.*refresh|401.*重启": "jwt-config",
    "state.*stuck|pending.*不变|状态机.*卡": "state-machine",
    "NOT_A_BUG|产品设计|符合预期": "not-a-bug",
    "commented out|DISABLED FOR TESTING|注释掉": "disabled-code",
    "rate limit|限流|brute force": "rate-limit",
}


def scan_fixes():
    """Scan .fixes/ for bug patterns."""
    if not FIXES_DIR.exists():
        print("No .fixes/ directory yet.")
        return []

    fixes = []
    for f in sorted(FIXES_DIR.glob("*.md")):
        try:
            content = f.read_text(encoding="utf-8")
        except:
            continue
        fixes.append({"file": f.name, "content": content, "mtime": f.stat().st_mtime})

    return fixes


def extract_patterns(fixes):
    """Extract bug patterns from fix files."""
    pattern_counts = Counter()
    bug_pattern_map = defaultdict(list)

    for fix in fixes:
        content = fix["content"]
        for regex, name in PATTERN_RULES.items():
            if re.search(regex, content, re.IGNORECASE):
                pattern_counts[name] += 1
                bug_pattern_map[name].append(fix["file"])

    return pattern_counts, bug_pattern_map


def suggest_frules(pattern_counts, bug_pattern_map, threshold=3):
    """Suggest F-rules for patterns that appear 3+ times."""
    suggestions = []

    for pattern, count in pattern_counts.most_common():
        if count >= threshold:
            files = bug_pattern_map[pattern][:3]
            suggestions.append({
                "pattern": pattern,
                "count": count,
                "files": files,
                "candidate": f"F-candidate: {pattern} 出现 {count} 次 → 检查是否需要 F-rule",
            })

    return suggestions


def main():
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "scan"

    fixes = scan_fixes()
    if not fixes:
        print("No fixes found. Run some T2 investigations first.")
        return

    pattern_counts, bug_pattern_map = extract_patterns(fixes)
    suggestions = suggest_frules(pattern_counts, bug_pattern_map)

    print(f"Scanned {len(fixes)} fix files.\n")

    if cmd == "scan":
        print("Pattern frequency:")
        for pattern, count in pattern_counts.most_common():
            bar = "█" * min(count, 20)
            print(f"  {pattern:<25} {count:>3} {bar}")

    if suggestions:
        print(f"\n[GROWTH] {len(suggestions)} patterns at threshold:")
        for s in suggestions:
            print(f"  {s['pattern']}: {s['count']}x → files: {', '.join(s['files'][:2])}")

    if cmd == "suggest":
        print("\n=== Candidate F-rules ===")
        for s in suggestions:
            print(f"\n## F-candidate: {s['pattern']}")
            print(f"Occurrences: {s['count']}")
            print(f"Example files: {', '.join(s['files'][:2])}")
            print(f"Action: Lean T2 validate on bugs matching this pattern")


if __name__ == "__main__":
    main()
