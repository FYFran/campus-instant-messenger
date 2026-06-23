"""
BugHuntBench v2.0 Harness — Agent Skill 自动测试框架.

对标 SWE-bench + AgentBeats + AdaRubric.
核心能力: bug 解析 → agent 执行 → 轨迹捕获 → 自动评分 → 结果汇总.

v2: 答案物理分离 — desc.md (agent 可读) + truth.md (仅评分器)
    bugset/B01/desc.md  bugset/B01/truth.md  bugset/B01/verify.sh

Usage:
    python bughunt_harness.py --bugs B01,B02,B03 --mode quick
    python bughunt_harness.py --bugs all --mode full --output results.tsv
"""

import json
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

# --- Paths ---
BENCH_DIR = Path(__file__).parent
BUGS_DIR = BENCH_DIR / "bugs"          # v1 旧格式 (兼容)
BUGSET_DIR = BENCH_DIR / "bugset"       # v2 新格式 (答案分离)
RESULTS_FILE = BENCH_DIR / "results.tsv"
BUG_PATTERN = re.compile(r"^B\d{2}_.+\.md$")
BUGSET_PATTERN = re.compile(r"^(B|S|C|D|Q|R|M|T|G)\d{2}$")  # Multi-skill: 缉凶/铁壁/明镜/布阵/门神/破阵/元/试金石/火眼

# Skill → bug prefix mapping
SKILL_PREFIX = {
    "缉凶": "B", "铁壁": "S", "明镜": "C", "布阵": "D",
    "门神": "Q", "破阵": "R", "试金石": "T", "元": "M",
    # English aliases
    "bughunt": "B", "security": "S", "code-review": "C",
    "deploy": "D", "quality-gate": "Q", "red-team": "R",
    "testing": "T", "meta": "M",
}

# --- Data Classes ---


@dataclass
class BugSpec:
    """Parsed bug specification from markdown file."""
    id: str
    type_gt: str          # Ground truth T-Type (T0-T7)
    language: str
    difficulty: str
    description: str       # User-facing bug description (for agent)
    ground_truth: dict     # Full ground truth for scoring
    raw_path: Path

    @property
    def scoring_rubric(self) -> dict:
        """Extract scoring criteria from ground truth."""
        return self.ground_truth.get("scoring", {})


@dataclass
class AgentReport:
    """Parsed agent output after bug investigation."""
    bug_id: str
    raw_output: str
    classification: str = ""       # Extracted T-Type
    chain_steps: dict = field(default_factory=dict)  # 7-step outputs
    root_cause: str = ""
    root_cause_file_line: str = ""
    fix_description: str = ""
    cf_evidence: str = ""
    trajectory: list = field(default_factory=list)  # Tool call trace

    @property
    def chain_complete(self) -> bool:
        """Check if all 7 contract steps have non-empty output."""
        required = ["分类", "证据", "追踪", "分析", "修复", "验证", "记录"]
        return all(self.chain_steps.get(s, "").strip() for s in required)


@dataclass
class ScoreCard:
    """Per-bug scoring result."""
    bug_id: str
    score_classification: float = 0.0  # Dimension 1 (0-1, partial=0.5 for valid_alternative)
    score_chain: int = 0              # Dimension 2
    score_evidence: int = 0           # Dimension 3
    score_root_cause: int = 0         # Dimension 4 (0-2)
    score_cf: int = 0                 # Dimension 5
    score_fix: int = 0                # Dimension 6
    score_trace: int = 0              # Dimension 7
    l3_verdict: str = "NOT_RUN"       # L3定性标注
    valid_alternative: bool = False   # Agent found real bug, not injected bug (arXiv:2511.10865)
    notes: str = ""

    @property
    def total(self) -> float:
        return (self.score_classification + self.score_chain +
                self.score_evidence + self.score_root_cause +
                self.score_cf + self.score_fix + self.score_trace)

    @property
    def max_score(self) -> float:
        return 8  # 1+1+1+2+1+1+1


# --- Bug Parser ---


def parse_bug_file(filepath: Path) -> Optional[BugSpec]:
    """Parse a bug markdown file into BugSpec.

    Supports two formats:
      v1: bugs/B01_T0_desc.md (description + ground truth in one file)
      v2: bugset/B01/desc.md + bugset/B01/truth.md (separated)
    """
    if filepath.is_dir():
        # v2 format
        return _parse_bug_v2(filepath)
    elif filepath.exists():
        # v1 format (backward compatible)
        return _parse_bug_v1(filepath)
    return None


def _parse_bug_v2(bug_dir: Path) -> Optional[BugSpec]:
    """Parse v2 separated format: bugset/B01/{desc.md, truth.md}."""
    desc_file = bug_dir / "desc.md"
    truth_file = bug_dir / "truth.md"

    if not desc_file.exists() or not truth_file.exists():
        return None

    bug_id = bug_dir.name

    # Parse desc.md for bug_id, type, description
    desc_content = desc_file.read_text(encoding="utf-8")
    header_match = re.match(r"^#\s+([BCDRGQSM]\d+)\s*[—\-]\s*([TRGQDSM]\d+):?\s*(.+)$", desc_content.split("\n")[0])
    if not header_match:
        return None

    type_gt = header_match.group(2)

    # Extract description
    desc_match = re.search(r"## Bug 描述\s*\n(.*)", desc_content, re.DOTALL)
    description = desc_match.group(1).strip() if desc_match else ""

    # Parse truth.md for ground truth
    truth_content = truth_file.read_text(encoding="utf-8")
    truth_match = re.search(r"## Ground Truth\s*\n(.*)", truth_content, re.DOTALL)
    truth_text = truth_match.group(1).strip() if truth_match else truth_content

    ground_truth = _parse_ground_truth(truth_text)
    ground_truth["type"] = type_gt

    # Detect language
    language = "Go"
    if "Python" in truth_text or "async" in description.lower() or "await" in truth_text:
        language = "Python"
    if "Mixed" in truth_text or "CI" in description:
        language = "Mixed"

    difficulty_map = {"T0": "easy", "T1": "medium", "T2": "hard",
                      "T3": "medium", "T4": "easy", "T5": "medium",
                      "T6": "hard", "T7": "easy"}
    difficulty = difficulty_map.get(type_gt, "medium")

    return BugSpec(
        id=bug_id, type_gt=type_gt, language=language, difficulty=difficulty,
        description=description, ground_truth=ground_truth, raw_path=bug_dir,
    )


def _parse_bug_v1(filepath: Path) -> Optional[BugSpec]:
    """Parse v1 combined format: bugs/B01_T0_desc.md (backward compatible)."""
    if not filepath.exists():
        return None

    content = filepath.read_text(encoding="utf-8")

    # Parse header: # B01 — T0: short description
    header_match = re.match(
        r"^#\s+(B\d+)\s*[—\-]\s*(T\d+):?\s*(.+)$",
        content.split("\n")[0]
    )
    if not header_match:
        return None

    bug_id = header_match.group(1)
    type_gt = header_match.group(2)

    # Split into Description and Ground Truth sections
    desc_match = re.search(
        r"## Bug 描述\s*\n(.*?)(?=## Ground Truth)",
        content, re.DOTALL
    )
    truth_match = re.search(
        r"## Ground Truth\s*\n(.*)",
        content, re.DOTALL
    )

    description = desc_match.group(1).strip() if desc_match else ""
    truth_text = truth_match.group(1).strip() if truth_match else ""

    ground_truth = _parse_ground_truth(truth_text)
    ground_truth["type"] = type_gt

    language = "Go"
    if "Python" in truth_text or "async" in description.lower():
        language = "Python"
    if "Mixed" in truth_text or "CI" in description:
        language = "Mixed"

    difficulty_map = {"T0": "easy", "T1": "medium", "T2": "hard",
                      "T3": "medium", "T4": "easy", "T5": "medium",
                      "T6": "hard", "T7": "easy"}
    difficulty = difficulty_map.get(type_gt, "medium")

    return BugSpec(
        id=bug_id, type_gt=type_gt, language=language, difficulty=difficulty,
        description=description, ground_truth=ground_truth, raw_path=filepath,
    )


def _parse_ground_truth(text: str) -> dict:
    """Extract structured ground truth from markdown text."""
    result = {
        "root_cause": "",
        "fix": "",
        "scoring": {
            "classification": "",
            "evidence_required": [],
            "root_cause_match": "",
            "cf_required": "",
            "fix_match": "",
        }
    }

    # Extract root cause
    rc_match = re.search(r"\*\*根因[：:]\*\*\s*(.+?)(?=\*\*正确|\*\*评分|\Z)", text, re.DOTALL)
    if rc_match:
        result["root_cause"] = rc_match.group(1).strip()

    # Extract fix
    fix_match = re.search(r"\*\*正确修复[：:]\*\*\s*(.+?)(?=\*\*正确响应|\*\*评分|\Z)", text, re.DOTALL)
    if fix_match:
        result["fix"] = fix_match.group(1).strip()

    # Special case for T7 (NOT_A_BUG)
    resp_match = re.search(r"\*\*正确响应[：:]\*\*\s*(.+?)(?=\*\*评分|\Z)", text, re.DOTALL)
    if resp_match:
        result["fix"] = resp_match.group(1).strip()

    # Parse scoring points
    for line in text.split("\n"):
        line = line.strip()
        if "分类:" in line:
            result["scoring"]["classification"] = line.split(":", 1)[-1].strip()
        elif "证据:" in line:
            result["scoring"]["evidence_required"].append(line.split(":", 1)[-1].strip())
        elif "根因:" in line:
            result["scoring"]["root_cause_match"] = line.split(":", 1)[-1].strip()
        elif "CF:" in line:
            result["scoring"]["cf_required"] = line.split(":", 1)[-1].strip()
        elif "修复:" in line:
            result["scoring"]["fix_match"] = line.split(":", 1)[-1].strip()

    return result


# --- Agent Report Parser ---


def parse_agent_report(raw_output: str, bug_id: str) -> AgentReport:
    """Parse agent's bug report output into structured AgentReport."""
    report = AgentReport(bug_id=bug_id, raw_output=raw_output)

    # Extract T-Type classification
    type_match = re.search(
        r"(?:Type|分类)[：:]\s*(T\d|T_AUTH|T\d\s*\(|NOT_A_BUG)",
        raw_output
    )
    if type_match:
        report.classification = type_match.group(1).strip()

    # Extract 7 contract chain steps
    step_patterns = {
        "分类": r"(?:##?\s*)?(?:分类|Classification)[：:]\s*(.+?)(?=\n(?:##?\s*)?(?:证据|追踪|分析|修复|验证|记录|Evidence|Trace|Analysis|Fix|Verify)|\n\n---|\Z)",
        "证据": r"(?:##?\s*)?(?:证据|Evidence)[：:]\s*(.+?)(?=\n(?:##?\s*)?(?:追踪|分析|修复|验证|记录|Trace|Analysis|Fix|Verify)|\n\n---|\Z)",
        "追踪": r"(?:##?\s*)?(?:追踪|Trace)[：:]\s*(.+?)(?=\n(?:##?\s*)?(?:分析|修复|验证|记录|Analysis|Fix|Verify)|\n\n---|\Z)",
        "分析": r"(?:##?\s*)?(?:分析|Analysis)[：:]\s*(.+?)(?=\n(?:##?\s*)?(?:修复|验证|记录|Fix|Verify)|\n\n---|\Z)",
        "修复": r"(?:##?\s*)?(?:修复|Fix)[：:]\s*(.+?)(?=\n(?:##?\s*)?(?:验证|记录|Verify)|\n\n---|\Z)",
        "验证": r"(?:##?\s*)?(?:验证|Verif)[：:]\s*(.+?)(?=\n(?:##?\s*)?(?:记录|Record)|\n\n---|\Z)",
        "记录": r"(?:##?\s*)?(?:记录|Record)[：:]\s*(.+?)(?=\n\n---|\Z)",
    }

    for step, pattern in step_patterns.items():
        match = re.search(pattern, raw_output, re.DOTALL | re.IGNORECASE)
        if match:
            report.chain_steps[step] = match.group(1).strip()[:2000]

    # Extract root cause with file:line
    rc_match = re.search(
        r"(?:根因|Root Cause|ROOT CAUSE)[：:]\s*(.+?)(?=\n\n|\n(?:##|[A-Z]{2,}:)|Confidence|Counterfactual|\Z)",
        raw_output, re.DOTALL | re.IGNORECASE
    )
    if rc_match:
        report.root_cause = rc_match.group(1).strip()[:500]
        # Try to extract file:line
        fl_match = re.search(
            r'([\w./]+\.(?:go|py|js|ts|dart))[:.](\d+)',
            rc_match.group(1)
        )
        if fl_match:
            report.root_cause_file_line = f"{fl_match.group(1)}:{fl_match.group(2)}"

    # Extract CF evidence
    cf_match = re.search(
        r"(?:Counterfactual|CF|反事实)[：:]?\s*(.+?)(?=\n\n|\n(?:##|[A-Z]{2,}:)|\Z)",
        raw_output, re.DOTALL | re.IGNORECASE
    )
    if cf_match:
        report.cf_evidence = cf_match.group(1).strip()[:500]

    # Extract fix
    fix_match = re.search(
        r"(?:修复|Fix|FIX)[：:]?\s*(.+?)(?=\n\n|\n(?:##|[A-Z]{2,}:)|\Z)",
        raw_output, re.DOTALL | re.IGNORECASE
    )
    if fix_match:
        report.fix_description = fix_match.group(1).strip()[:500]

    return report


# --- Rule-Based Scorer ---


def score_by_rules(report: AgentReport, bug: BugSpec) -> ScoreCard:
    """Rule-based scoring for dimensions 1, 2, 7 (zero token cost)."""
    card = ScoreCard(bug_id=bug.id)

    # Dimension 1: Classification (T-Type match)
    agent_type = report.classification.strip().upper()
    gt_type = bug.type_gt.strip().upper()
    # Normalize: T1, T1(, T1（ → T1
    agent_type_clean = re.match(r'(T\d|NOT_A_BUG)', agent_type)
    if agent_type_clean:
        agent_type_clean = agent_type_clean.group(1)
        if agent_type_clean == gt_type or (agent_type_clean == "NOT_A_BUG" and gt_type == "T7"):
            card.score_classification = 1
        elif agent_type_clean == "T7" and gt_type == "T7":
            card.score_classification = 1
        else:
            card.notes += f"Type mismatch: agent={agent_type_clean} gt={gt_type}; "
    else:
        # Agent used non-standard type (e.g. T_AUTH, T9) — may indicate valid_alternative
        card.notes += f"Non-std type: agent={agent_type} gt={gt_type}; "

    # Dimension 2: Chain completeness
    if report.chain_complete:
        card.score_chain = 1
    else:
        missing = [s for s in ["分类", "证据", "追踪", "分析", "修复", "验证", "记录"]
                   if not report.chain_steps.get(s, "").strip()]
        card.notes += f"Missing steps: {missing}; "

    # Dimension 7: Trace compliance (gate/red-line adherence)
    card.score_trace = _check_trace_compliance(report)

    return card


def _check_trace_compliance(report: AgentReport) -> int:
    """Check if agent followed contract chain rules."""
    violations = []

    raw = report.raw_output

    # Check for common contract violations
    # 5 Red Lines from 缉凶 v2.0:
    # 1. 不复现不修
    if "复现" not in raw and "repro" not in raw.lower():
        # Not necessarily a violation for T7 or emergency
        pass

    # 2. 不 Counterfactual 不提交
    if report.cf_evidence and len(report.cf_evidence) < 20:
        violations.append("CF evidence too short (possible template)")

    # 3. Confidence check
    if "conf: 0." in raw.lower() or "confidence: 0." in raw.lower():
        # Low confidence should be marked SUSPECT
        pass

    # 4. Gate skipping
    if report.chain_complete:
        # All steps present — good
        pass
    else:
        missing = [s for s in ["分类", "证据", "追踪", "分析", "修复", "验证", "记录"]
                   if not report.chain_steps.get(s, "").strip()]
        if len(missing) <= 1:
            violations.append(f"Minor gate skip: {missing}")
        else:
            violations.append(f"MAJOR gate skip: {missing}")

    return 1 if len(violations) <= 1 else 0


# --- Agent Prompt Builder ---

# Per-skill prompt templates
_SKILL_PROMPTS = {
    "缉凶": {
        "role": "缉凶 agent — Bug 排查合同框架 v2.0",
        "type_label": "T-Type",
        "type_options": "T0稳定复现 / T1竞态时序 / T2多因素 / T3无报错数据错 / T4昨天还好 / T5状态机异常 / T6特定环境 / T7代码对需求错",
        "chain": ["分类", "证据", "追踪", "分析", "修复", "验证", "记录"],
        "output_prefix": "SCORE_CARD: T分类|链完整|证据|根因|CF|修复",
    },
    "破阵": {
        "role": "破阵 agent — 对抗演练 v2.1（3角色×7阶段）",
        "type_label": "R-Type",
        "type_options": "R0认证绕过 / R1权限提升链 / R2重放攻击 / R3注入 / R4信息泄露",
        "chain": ["侦察", "武器化", "投放", "利用", "安装", "C2", "行动"],
        "output_prefix": "SCORE_CARD: R分类|链完整|利用路径|根因|攻击链|修复",
    },
    "门神": {
        "role": "门神 agent — 上线前质量门禁 v2.1",
        "type_label": "Q-Type",
        "type_options": "Q0恒真检查 / Q1检查跳过 / Q2阈值绕过 / Q3误报",
        "chain": ["检查清单", "逐项验证", "门禁判定", "风险分级", "修复建议"],
        "output_prefix": "SCORE_CARD: Q分类|链完整|绕过证据|根因|门禁BYPASS|修复",
    },
    "布阵": {
        "role": "布阵 agent — 安全部署 v3.0（9阶段流水线）",
        "type_label": "D-Type",
        "type_options": "D0备份缺陷 / D1冒烟跳过 / D2中止条件缺失 / D3回滚失败",
        "chain": ["稳态表征", "pre-flight", "部署检查", "冒烟验证", "回滚评估"],
        "output_prefix": "SCORE_CARD: D分类|链完整|缺陷证据|根因|部署风险|修复",
    },
    "火眼": {
        "role": "火眼 agent — 项目差距分析引擎 v1.1（7-Phase）",
        "type_label": "G-Type",
        "type_options": "G0维度缺失 / G1交叉验证漏报 / G2静默降级 / G3分类错误",
        "chain": ["PreScan", "Map", "Probe", "Confirm", "Synthesize"],
        "output_prefix": "SCORE_CARD: G分类|链完整|gap证据|根因|遗漏影响|修复",
    },
    "试金石": {
        "role": "试金石 agent — 测试锻造 v1.0（RED-GREEN-REFACTOR）",
        "type_label": "M-Type",
        "type_options": "M0恒真测试 / M1过度Mock / M2边界缺失 / M3断言错误",
        "chain": ["测试意图", "RED验证", "边界枚举", "Mock审计", "GREEN确认"],
        "output_prefix": "SCORE_CARD: M分类|链完整|测试缺陷证据|根因|覆盖缺口|修复",
    },
}

_SKILL_RESOURCES = {
    "缉凶": "f:/ClaudeFiles/bug-patterns.md",
    "破阵": "f:/ClaudeFiles/.claude/skills/references/redteam-playbook.md",
    "门神": "f:/ClaudeFiles/.claude/benchmarks/bughunt/bughunt_ci.py",
    "布阵": "f:/ClaudeFiles/campus_go/",
    "火眼": "f:/ClaudeFiles/.claude/skills/火眼/SKILL.md",
    "试金石": "f:/ClaudeFiles/campus_go/internal/handlers/",
}


def build_agent_prompt(bug: BugSpec, skill_name: str = "缉凶") -> str:
    """Build the prompt for spawning an agent with the correct skill contract.

    Adapts the output format, type taxonomy, and chain steps based on the skill.
    """
    cfg = _SKILL_PROMPTS.get(skill_name, _SKILL_PROMPTS["缉凶"])
    resource = _SKILL_RESOURCES.get(skill_name, "f:/ClaudeFiles/campus_go/")

    chain_steps = "\n".join(
        f"**{s}** — ___" for s in cfg["chain"]
    )

    return f"""你是{cfg['role']}。严格按合同链输出。

## 调查目标

{bug.description}

## 合同链（必须全填，每步产出=下步门票）

{chain_steps}

**{cfg['type_label']}分类**: {cfg['type_options']}

## 资源
- campus_go 代码在 f:/ClaudeFiles/campus_go/
- campus_app 在 f:/ClaudeFiles/campus_app/
- 生产服务器: 139.196.50.134
- 参考: {resource}

## 输出格式

输出完整报告（所有 {len(cfg['chain'])} 步），最后一行：
{cfg['output_prefix']}"""


# --- Judge Prompt Builder ---


def build_judge_prompt(
    dimension: str,
    agent_report: AgentReport,
    bug: BugSpec,
    score: int = 0,
) -> str:
    """Build a prompt for LLM judge to score a specific dimension.

    Dimensions:
    - evidence (3): 复现步骤 + baseline 可验证
    - root_cause (4): 根因与 truth 一致 (0-2)
    - cf (5): CF 有 pre/post 证据
    """
    prompts = {
        "evidence": f"""你是独立评分 agent。评估以下 bug report 的【证据充分性】。

Bug 描述: {bug.description}

Agent 证据输出:
{agent_report.chain_steps.get('证据', 'N/A')}

评分标准:
- 1: 包含具体的复现步骤 + 可验证的 baseline 输出（如 curl 命令 + 响应）
- 0: 只有笼统描述（如"复现成功"）或无 baseline

返回 JSON: {{"score": 0|1, "confidence": 0-100, "reasoning": "引用具体证据或缺失点"}}""",

        "root_cause": f"""你是独立评分 agent。评估以下 bug report 的【根因正确性】。

Bug 描述: {bug.description}

Ground Truth 根因方向: {bug.ground_truth.get('root_cause', 'N/A')[:300]}

Agent 根因: {agent_report.root_cause}
Agent 文件引用: {agent_report.root_cause_file_line}

评分标准:
- 2: 根因与 ground truth 方向一致，file:line 引用正确，因果链完整
- 1: 方向对但细节偏差（正确函数但错误行号，或漏了次要因素）
  OR 发现了一个 valid alternative — agent找到了真实的bug，虽非GT注入的bug，但在同一大类（如auth漏洞/data错误/竞态等），证据链完整，file:line具体
- 0: 根因错误或分析完全跑偏（幻觉、不存在的bug、错误的因果分析）

valid_alternative 判定条件（必须全部满足）:
  a) Agent确实找到了一个真实的bug（非幻觉）
  b) Bug类型与GT属于同一大类（如都是auth问题/都是数据错误/都是竞态）
  c) 证据链完整（有具体的复现步骤或代码引用）
  d) 有file:line级别的具体位置引用，非泛泛而谈

返回 JSON: {{"score": 0|1|2, "confidence": 0-100, "reasoning": "一句话", "matches_gt": true|false, "valid_alternative": true|false}}""",

        "cf": f"""你是独立评分 agent。评估以下 bug report 的【Counterfactual 真实性】。

Agent CF 输出:
{agent_report.cf_evidence}

评分标准:
- 1: CF 包含可验证的 pre/post 对比证据（具体数据、日志、测试结果），不是模板文字
- 0: CF 只有声明性语句（如"修后 OK"）无 pre/post 对比数据

返回 JSON: {{"score": 0|1, "confidence": 0-100, "reasoning": "引用 CF 中的具体证据或缺失点"}}""",
    }

    return prompts.get(dimension, "")


# --- Results Management ---


def load_results(filepath: Path = RESULTS_FILE) -> list[dict]:
    """Load existing results from TSV file."""
    if not filepath.exists():
        return []

    lines = filepath.read_text(encoding="utf-8").strip().split("\n")
    if len(lines) < 2:
        return []

    headers = lines[0].split("\t")
    results = []
    for line in lines[1:]:
        if not line.strip():
            continue
        values = line.split("\t")
        result = dict(zip(headers, values))
        results.append(result)

    return results


def append_result(
    card: ScoreCard,
    bug: BugSpec,
    model: str = "",
    skill: str = "缉凶",
    filepath: Path = RESULTS_FILE,
) -> None:
    """Append a single scoring result to TSV."""
    exists = filepath.exists()
    timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M")

    row = (
        f"{timestamp}\t{card.bug_id}\t{bug.type_gt}\t{card.score_classification}\t"
        f"{card.score_chain}\t{card.score_evidence}\t{card.score_root_cause}\t"
        f"{card.score_cf}\t{card.score_fix}\t{card.score_trace}\t"
        f"{card.total}\t{model}\t{skill}\t{card.l3_verdict}\t"
        f"{card.notes}\n"
    )

    if not exists:
        header = (
            "timestamp\tbug_id\tgt_type\tclassification\tchain_complete\t"
            "evidence\troot_cause\tcf\tfix\ttrace\ttotal\tmodel\tskill\t"
            "l3_verdict\tnotes\n"
        )
        filepath.write_text(header + row, encoding="utf-8")
    else:
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(row)


def generate_summary(results: list[ScoreCard]) -> str:
    """Generate a markdown summary from scoring results."""
    if not results:
        return "No results."

    total_score = sum(r.total for r in results)
    max_possible = sum(r.max_score for r in results)
    pct = total_score / max_possible * 100 if max_possible > 0 else 0

    type_correct = sum(1 for r in results if r.score_classification == 1)
    chain_complete = sum(1 for r in results if r.score_chain == 1)
    root_hit = sum(1 for r in results if r.score_root_cause == 2)
    root_partial = sum(1 for r in results if r.score_root_cause == 1)

    lines = [
        "# BugHuntBench Run Summary",
        "",
        f"**Run time:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"**Bugs:** {len(results)}",
        f"**Total Score:** {total_score}/{max_possible} = {pct:.1f}%",
        "",
        "## Metrics",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| T-Type Accuracy | {type_correct}/{len(results)} ({type_correct/len(results)*100:.0f}%) |",
        f"| Chain Completeness | {chain_complete}/{len(results)} ({chain_complete/len(results)*100:.0f}%) |",
        f"| Root Cause Hit Rate | {root_hit}/{len(results)} ({root_hit/len(results)*100:.0f}%) |",
        f"| Root Cause Partial | {root_partial}/{len(results)} ({root_partial/len(results)*100:.0f}%) |",
        "",
        "## Per-Bug Scores",
        "",
        "| ID | GT Type | Class | Chain | Evidence | Root | CF | Fix | Trace | Total | L3 |",
        "|----|---------|-------|-------|----------|------|----|-----|-------|-------|----|",
    ]

    for r in results:
        lines.append(
            f"| {r.bug_id} | — | {r.score_classification} | {r.score_chain} | "
            f"{r.score_evidence} | {r.score_root_cause} | {r.score_cf} | {r.score_fix} | "
            f"{r.score_trace} | **{r.total}** | {r.l3_verdict} |"
        )

    return "\n".join(lines)


# --- Bug Discovery ---


def discover_bugs() -> list[Path]:
    """Discover all bugs. Prefer v2 format (bugset/) over v1 (bugs/)."""
    # v2 format: directories under bugset/
    if BUGSET_DIR.exists():
        dirs = sorted(
            [d for d in BUGSET_DIR.iterdir() if d.is_dir() and BUGSET_PATTERN.match(d.name)],
            key=lambda x: x.name
        )
        if dirs:
            return dirs

    # v1 fallback: individual markdown files
    if BUGS_DIR.exists():
        return sorted(
            [f for f in BUGS_DIR.iterdir() if BUG_PATTERN.match(f.name)],
            key=lambda x: x.name
        )
    return []


def load_bugs(bug_ids: Optional[list[str]] = None) -> list[BugSpec]:
    """Load bugs by ID or all bugs if no IDs specified."""
    all_paths = discover_bugs()
    bugs = []

    for filepath in all_paths:
        bug = parse_bug_file(filepath)
        if bug and (bug_ids is None or bug.id in bug_ids):
            bugs.append(bug)

    return bugs


# --- Main CLI ---


def main():
    """CLI entry point for running benchmarks."""
    import argparse

    parser = argparse.ArgumentParser(
        description="BugHuntBench — Agent Skill 自动测试框架"
    )
    parser.add_argument(
        "--bugs", type=str, default="all",
        help="Bug IDs to run (comma-separated, e.g. B01,B02,B03) or 'all'"
    )
    parser.add_argument(
        "--mode", type=str, default="quick",
        choices=["quick", "full", "verify"],
        help="quick=rule-based only, full=LLM judge, verify=cross-model verify"
    )
    parser.add_argument(
        "--output", type=str, default=str(RESULTS_FILE),
        help="Output TSV file path"
    )
    parser.add_argument(
        "--list", action="store_true",
        help="List all available bugs and exit"
    )
    parser.add_argument(
        "--summary", action="store_true",
        help="Print summary of existing results and exit"
    )

    args = parser.parse_args()

    # List bugs mode
    if args.list:
        bugs = load_bugs()
        print(f"Found {len(bugs)} bugs:")
        for b in bugs:
            print(f"  {b.id} — {b.type_gt} ({b.language}, {b.difficulty})")
        return

    # Summary mode
    if args.summary:
        results = load_results()
        if not results:
            print("No results found.")
            return
        print(f"Loaded {len(results)} results.")
        # Find latest run
        timestamps = sorted(set(r.get("timestamp", "") for r in results), reverse=True)
        if timestamps:
            latest = timestamps[0]
            latest_results = [r for r in results if r.get("timestamp") == latest]
            total = sum(int(r.get("total", 0)) for r in latest_results)
            print(f"Latest run ({latest}): {total}/{len(latest_results)*8}")
        return

    # Load bugs
    if args.bugs == "all":
        bug_ids = None
    else:
        bug_ids = [b.strip() for b in args.bugs.split(",")]

    bugs = load_bugs(bug_ids)
    if not bugs:
        print(f"No bugs found for: {args.bugs}")
        sys.exit(1)

    print(f"Loaded {len(bugs)} bugs for mode '{args.mode}'.")

    # For quick mode: rule-based scoring only
    # Full mode requires agent execution (done by Claude Code Agent tool)
    # This script handles the parsing + rule-scoring + results

    if args.mode == "quick":
        print("Quick mode: rule-based scoring ready.")
        print("Use Agent tool to run bugs, then parse with parse_agent_report().")
        print("Call score_by_rules() for each result.")

    print(f"\nOutput will be written to: {args.output}")


if __name__ == "__main__":
    main()
