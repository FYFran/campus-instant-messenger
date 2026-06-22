"""UserPromptSubmit Hook: Semantic task routing with path-scoped skills.

v3 — Google ADK progressive disclosure + Anthropic path-scoped skills.
  Stage 1 (regex, 0ms): catch obvious patterns
  Stage 2 (semantic, <5ms): keyword match against L1 skill registry
  Stage 3 (LLM fallback): for ambiguous queries (future)

Path scope (Anthropic pattern):
  Skills with path_scope only activate when CWD matches.
  flutter-doctor only loads in campus_app/, backend-surgeon only in _research/rewriter-go/.
  General skills (null path_scope) always available.

Recall injection: code-reviewer/security-auditor/debugger routes auto-inject memory recall.
"""

import sys, os, re, json
from pathlib import Path

user_input = os.environ.get("CLAUDE_USER_PROMPT", sys.stdin.read() if sys.stdin else "")

if len(user_input.strip()) < 10:
    sys.exit(0)

# Negation detection: skip routing for "I don't want X" patterns
NEGATION_PATTERNS = [
    r"(不想|不要|别用|不需要|不是.*这个|算了|不用).*",
    r"(what|how|why|when|where|who|is|are|can|do|should).*\?",  # pure questions
    r"^(好|OK|行|嗯|对|是|没错|yes|no|okay)[\s。.!！]*$",       # simple confirmations
    r"^(真的|确定|是吗|你确定|对不对|是不是).*",                    # doubt/verification
    r"^[?？].*",                                                # question marks
    r"^(这个|那个|什么|怎么|为什么).*\?$",                         # pure questions
]
for np in NEGATION_PATTERNS:
    if re.search(np, user_input, re.IGNORECASE):
        sys.exit(0)  # Don't route conversational/negation/queries

# === L1 Registry (always loaded, ~1KB) ===
REGISTRY_PATH = Path("f:/ClaudeFiles/.claude/skills-registry.json")
registry = {}
if REGISTRY_PATH.exists():
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))

skills = registry.get("skills", {})
path_scopes = registry.get("path_scopes", {})

# Current working directory for path scope filtering
cwd = os.environ.get("CLAUDE_CODE_CWD", os.getcwd()).replace("\\", "/")


def path_scope_match(skill_scope: str | None) -> bool:
    """Check if skill's path scope matches current CWD."""
    if skill_scope is None:
        return True  # General skill, always available
    return skill_scope in cwd


def _inject_recall(skill_names: list[str]):
    """Inject memory recall for review/debug/security routes."""
    RECALL_SKILLS = {"code-reviewer", "security-auditor", "debugger", "refactor-master"}
    if any(s in RECALL_SKILLS for s in skill_names):
        print("@recall: 执行前 search_nodes + Read MEMORY.md + pete-memory-api.py recall")


def _suggest_l2(skill_names: list[str]):
    """Suggest L2 loading for matched skills (Google ADK progressive disclosure)."""
    l2_files = []
    for name in skill_names:
        skill = skills.get(name, {})
        l2_file = skill.get("l2_file")
        if l2_file:
            l2_files.append(l2_file)

    if l2_files:
        print(f"@L2: {' '.join(l2_files)}")


# ============================================================
# Stage 1: Regex fast path (0ms, catches 80% of cases)
# ============================================================
REGEX_ROUTES = [
    # Code changes
    (r"(修.*bug|fix.*bug|修.*报错|改.*代码|修.*这个问题|patch)",
     ["caveman:builder", "code-reviewer", "security-auditor"]),
    # Refactor
    (r"(重[构写]|refactor|rewrite|重新[写设计])",
     ["refactor-master", "architect"]),
    # Security audit
    (r"(安全审计|漏洞扫描|安全.*查|security.*audit|渗透测试)",
     ["security-auditor"]),
    # Deploy
    (r"(部署到|deploy|上线到服务器|发布.*版本|push.*production)",
     ["deploy-captain"]),
    # Test
    (r"(跑.*测试|写.*测试|test.*suite|验证.*功能|check.*regression)",
     ["test-generator", "api-tester"]),
    # UI design
    (r"(设计.*UI|设计.*界面|改.*样式|做.*landing|改.*颜色|impeccable)",
     ["impeccable"]),
    # Architecture
    (r"(设计.*架构|系统设计|技术选型|新.*系统.*设计|ADR)",
     ["architect"]),
    # Code review
    (r"(review.*PR|审查.*代码|code.*review|代码质量)",
     ["code-reviewer", "security-auditor"]),
    # File search
    (r"(找.*所有|搜.*全项目|在哪.*定义|列出.*文件|grep)",
     ["codegraph_context"]),
    # Pantheon
    (r"(重要.*改|关键.*改|mission.critical|pantheon|高强度)",
     ["pantheon"]),
    # Watcher
    (r"(自检|watch.*系统|发现.*问题|系统.*监控)",
     ["watcher"]),
]

matched = False
for pattern, skill_names in REGEX_ROUTES:
    if re.search(pattern, user_input, re.IGNORECASE):
        # Filter by path scope
        active = [s for s in skill_names
                  if path_scope_match(skills.get(s, {}).get("path_scope"))]
        if active:
            print(f"@router: {' + '.join(active)}")
            _inject_recall(active)
            _suggest_l2(active)
        matched = True
        break

# ============================================================
# Stage 2: Semantic keyword matching (<5ms)
# ============================================================
if not matched:
    user_lower = user_input.lower()
    scores = []
    for name, skill in skills.items():
        triggers = skill.get("triggers", [])
        if not triggers:
            continue
        if not path_scope_match(skill.get("path_scope")):
            continue
        score = sum(1 for t in triggers if t.lower() in user_lower)
        if score > 0:
            scores.append((score, name, skill))

    scores.sort(reverse=True)

    if scores:
        top_score = scores[0][0]
        best = [s[1] for s in scores if s[0] >= top_score][:3]
        # Only route if we have a meaningful match (score >= 1)
        if top_score >= 1:
            print(f"@router[semantic]: {' + '.join(best)}")
            _inject_recall(best)
            _suggest_l2(best)
            matched = True


# ============================================================
# Path scope hint (Anthropic pattern: scope default skills)
# ============================================================
for scope_path, scope_cfg in path_scopes.items():
    if scope_path in cwd:
        defaults = scope_cfg.get("default_skills", [])
        if defaults:
            print(f"@scope[{scope_path}]: 默认可用 {' '.join(defaults)}")
        break
