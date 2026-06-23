"""
试剑石 成长编排器 v2 — 5环自进化引擎
每个 T2/T3 run 自动追加 results.tsv → 检测触发 → 执行动作 → 验证
用法: python pete-skill-evolve.py check    # 检测触发条件
      python pete-skill-evolve.py evolve   # 执行自动动作
      python pete-skill-evolve.py log      # 查看成长日志
"""

import json, sys
from pathlib import Path
from datetime import datetime
from collections import defaultdict

BENCH_DIR = Path(".claude/benchmarks/bughunt")
RESULTS_FILE = BENCH_DIR / "results.tsv"
PER_BUG_FILE = BENCH_DIR / "per_bug_results.tsv"
GROWTH_LOG = BENCH_DIR / "growth.log"
LEADERBOARD = BENCH_DIR / "LEADERBOARD.md"
BASELINE_SCORE = 76  # 95% of 80 max

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    try:
        print(line)
    except UnicodeEncodeError:
        print(line.encode("ascii", errors="replace").decode("ascii"))
    with open(GROWTH_LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def append_result(skill_ver, score, ttype, c4_hits, total_bugs, model="deepseek-v4", condition="skill"):
    """Append a T2/T3 run result to results.tsv."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header = "timestamp\tskill_version\tscore\tttype\tc4_hits\ttotal_bugs\tmodel\tcondition\n"

    if not RESULTS_FILE.exists():
        RESULTS_FILE.write_text(header, encoding="utf-8")

    line = f"{ts}\t{skill_ver}\t{score}\t{ttype}\t{c4_hits}\t{total_bugs}\t{model}\t{condition}\n"
    with open(RESULTS_FILE, "a", encoding="utf-8") as f:
        f.write(line)

    log(f"Appended: {skill_ver} score={score} ttype={ttype} c4={c4_hits}/{total_bugs}")

def load_results():
    if not RESULTS_FILE.exists():
        return []
    lines = RESULTS_FILE.read_text(encoding="utf-8").strip().split("\n")
    if len(lines) < 2:
        return []
    headers = lines[0].split("\t")
    return [dict(zip(headers, l.split("\t"))) for l in lines[1:] if l.strip()]

def load_per_bug_results():
    """Load per-bug scoring data (bug_id, dimensions, total)."""
    if not PER_BUG_FILE.exists():
        return []
    lines = PER_BUG_FILE.read_text(encoding="utf-8").strip().split("\n")
    if len(lines) < 2:
        return []
    headers = lines[0].split("\t")
    return [dict(zip(headers, l.split("\t"))) for l in lines[1:] if l.strip()]

def scan_agent_candidates():
    """Scan .fixes/ for agent-written pattern-candidate.md files.

    Contract step 8 (成长反馈) produces these. Each file describes an uncovered
    misclassification pattern or quality trap with a suggested F-rule.
    Returns list of {file, pattern, signal, suggested_f_rule, timestamp}.
    """
    import re, os
    fixes_dir = Path(".fixes")
    candidates = []
    if not fixes_dir.exists():
        return candidates

    for f in sorted(fixes_dir.glob("*pattern-candidate*")):
        try:
            content = f.read_text(encoding="utf-8")
            # Extract structured fields (match both "Pattern:" and "## Pattern" forms)
            pattern = re.search(r'#*\s*[Pp]attern:?\s*(.+)', content)
            signal = re.search(r'#*\s*[Ss]ignal:?\s*(.+)', content)
            rule = re.search(r'[Ss]uggested.?[Ff][- ]?[Rr]ule:?\s*(.+)', content)
            if pattern:
                candidates.append({
                    "file": str(f),
                    "pattern": pattern.group(1).strip(),
                    "signal": (signal.group(1).strip() if signal else "?"),
                    "suggested_f_rule": (rule.group(1).strip() if rule else "?"),
                    "timestamp": datetime.fromtimestamp(os.path.getmtime(str(f))).strftime("%Y-%m-%d %H:%M"),
                })
        except Exception:
            continue
    return candidates


def check_triggers():
    """Check all 6 ring triggers. R0=agent feedback, R1-R5=benchmark-driven."""
    summary = load_results()
    per_bug = load_per_bug_results()
    agent_candidates = scan_agent_candidates()
    events = []

    # R0: Agent self-reported patterns (contract step 8: 成长反馈)
    for c in agent_candidates:
        events.append({
            "ring": "R0_AGENT_FEEDBACK",
            "trigger": f"Agent reported: {c['pattern'][:80]}",
            "action": f"Review {c['file']} → if valid, add F-rule to 致命误判表",
            "auto": False,  # Requires human review before adding to skill
            "candidate": c,
        })

    if not summary and not per_bug and not agent_candidates:
        log("No results data. Run T2 at least once.")
        return events

    # R1: Bug mining — git log for recent fixes
    import subprocess
    try:
        r = subprocess.run(
            ["git","log","--oneline","--since=14.days","--grep=fix\\|bug\\|修复"],
            capture_output=True, text=True, timeout=10, encoding="utf-8", errors="replace"
        )
        commits = [l for l in r.stdout.split("\n") if l.strip()]
        if len(commits) >= 5:
            events.append({"ring":"R1_MINE","trigger":f"{len(commits)} fix commits in 14 days","action":"python growth_engine.py mine","auto":False})
    except: pass

    # R2: Difficulty upgrade — per-bug: 3+ perfect scores (total >= 7)
    bug_scores = defaultdict(list)
    for r in per_bug:
        bid = r.get("bug_id","")
        if not bid or not bid.startswith("B"):
            continue
        try:
            bug_scores[bid].append(int(r.get("total", 0)))
        except (ValueError, TypeError):
            continue

    for bid, scores in bug_scores.items():
        perfect = sum(1 for s in scores if s >= 7)
        if len(scores) >= 3 and perfect >= 3:
            events.append({"ring":"R2_RETIRE","trigger":f"{bid} {perfect}x perfect (>=7/8) in {len(scores)} runs","action":f"Retire {bid} -> generate harder variant","auto":False})

    # R3: Blind spot — per-bug: score_root consistently 0 (root cause never found)
    bug_root = defaultdict(list)
    for r in per_bug:
        bid = r.get("bug_id","")
        if not bid or not bid.startswith("B"):
            continue
        try:
            bug_root[bid].append(int(r.get("score_root", -1)))
        except (ValueError, TypeError):
            continue

    for bid, roots in bug_root.items():
        zeros = sum(1 for s in roots if s == 0)
        if len(roots) >= 2 and zeros >= 2:
            events.append({"ring":"R3_BLINDSPOT","trigger":f"{bid} score_root=0 x{zeros}/{len(roots)}","action":"GEPA reflection -> F-rule for root cause","auto":True})

    # R4: Overfit — summary: recent 3-run avg < overall avg - 4pp
    if len(summary) >= 5:
        all_scores = [int(r["score"]) for r in summary]
        overall_avg = sum(all_scores) / len(all_scores)
        recent_3 = all_scores[-3:]
        recent_avg = sum(recent_3) / len(recent_3)

        if recent_avg < overall_avg - 4:
            events.append({"ring":"R4_OVERFIT","trigger":f"Recent avg {recent_avg:.0f} vs overall {overall_avg:.0f} (gap={overall_avg-recent_avg:.0f}pp)","action":"Re-select hold-out + GEPA diversity optimization","auto":True})

    # R5: Regression — same-version 3-run avg below baseline
    # Only fires when ALL 3 runs are skill condition AND same version
    if len(summary) >= 3:
        recent_3 = summary[-3:]
        # All must be same version + skill condition
        versions = set(r.get("skill_version","") for r in recent_3)
        conditions = set(r.get("condition","") for r in recent_3)
        if len(versions) == 1 and conditions == {"skill"}:
            scores = [int(r["score"]) for r in recent_3]
            avg3 = sum(scores) / len(scores)
            if avg3 < BASELINE_SCORE - 4:
                ver = list(versions)[0]
                events.append({"ring":"R5_REGRESSION","trigger":f"{ver}: 3-run avg {avg3:.0f} < baseline {BASELINE_SCORE} (gap={BASELINE_SCORE-avg3:.0f}pp)","action":f"GEPA analyze {ver} -> fix skill -> verify","auto":True})

    return events

def evolve(auto=False):
    """Execute triggered actions.

    Auto triggers execute immediately. Manual triggers generate NEXT_ACTION.md.
    """
    events = check_triggers()

    if not events:
        log("[OK] All clear. No triggers fired.")
        return events

    actions_taken = []

    for e in events:
        icon = "[AUTO]" if e["auto"] else "[MANUAL]"
        log(f"  {icon} [{e['ring']}] {e['trigger']}")

        if e["ring"] == "R0_AGENT_FEEDBACK":
            c = e.get("candidate", {})
            log(f"       → Agent-suggested F-rule: {c.get('suggested_f_rule','?')}")
            log(f"       → Review {c.get('file','?')} before adding to 致命误判表")
            log(f"       → Pattern: {c.get('pattern','?')}")
            actions_taken.append(f"AgentFeedback: {c.get('suggested_f_rule','?')[:60]}")

        elif e["ring"] == "R3_BLINDSPOT" and e["auto"]:
            # Auto: run SkillAxe → generate F-candidate
            bug_id = e.get("bug_id", "?")
            log(f"       → SkillAxe analyzing {bug_id}...")
            _run_skillaxe_for_bug(bug_id)
            actions_taken.append(f"SkillAxe: {bug_id}")

        elif e["ring"] == "R5_REGRESSION" and e["auto"]:
            # Auto: run SkillAxe full diagnosis
            log(f"       → SkillAxe full diagnosis...")
            _run_skillaxe_full()
            actions_taken.append("SkillAxe: full diagnosis")

        elif e["ring"] == "R4_OVERFIT" and e["auto"]:
            log(f"       → Re-selecting hold-out + diversity check")
            actions_taken.append("Overfit: diversity check recommended")

        elif e["ring"] == "R2_RETIRE":
            log(f"       → Auto-retire candidate. Run: just retire-{e.get('bug_id','?')}")
            actions_taken.append(f"Retire: {e.get('bug_id','?')}")

        elif e["ring"] == "R1_MINE":
            log(f"       → Run: python growth_engine.py mine")
            actions_taken.append("Mine: git history scanned")

    # Write next action file
    NEXT = BENCH_DIR / "NEXT_ACTION.md"
    with open(NEXT, "w", encoding="utf-8") as f:
        f.write(f"# Next Action — {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
        f.write(f"Triggers: {len(events)} fired, {sum(1 for e in events if e['auto'])} auto\n\n")
        for e in events:
            f.write(f"- [{e['ring']}] {e['trigger']}\n")
            f.write(f"  → {e['action']}\n\n")
        if actions_taken:
            f.write(f"\nActions taken: {', '.join(actions_taken)}\n")

    log(f"Actions: {len(actions_taken)} | NEXT_ACTION.md written")
    return events


def _run_skillaxe_for_bug(bug_id: str):
    """Run SkillAxe diagnosis for a specific bug's blind spot."""
    try:
        import subprocess
        result = subprocess.run(
            ["python", str(BENCH_DIR / "skillaxe_diagnose.py"), "--suggest"],
            capture_output=True, text=True, timeout=30, cwd=str(BENCH_DIR.parent.parent)
        )
        # Log output
        for line in result.stdout.strip().split("\n"):
            if "F" in line and ":" in line:
                log(f"  Candidate: {line.strip()}")
    except Exception as e:
        log(f"  SkillAxe error: {e}")


def _run_skillaxe_full():
    """Run full SkillAxe 4-dim diagnosis."""
    try:
        import subprocess
        result = subprocess.run(
            ["python", str(BENCH_DIR / "skillaxe_diagnose.py")],
            capture_output=True, text=True, timeout=30, cwd=str(BENCH_DIR.parent.parent)
        )
        for line in result.stdout.strip().split("\n"):
            if "D" in line and ":" in line:
                log(f"  {line.strip()}")
    except Exception as e:
        log(f"  SkillAxe error: {e}")

def append_from_workflow(skill_ver, score, ttype, c4_hits, total_bugs=10, model="deepseek-v4", condition="skill"):
    """Called after each T2/T3 run to record result."""
    append_result(skill_ver, score, ttype, c4_hits, total_bugs, model, condition)
    events = check_triggers()
    if events:
        log(f"[!] {len(events)} triggers after this run!")
        for e in events:
            log(f"  [{e['ring']}] {e['action']}")

def append_per_bug(bug_id, gt_type, agent_type, score_class, score_chain, score_evidence, score_root, score_cf, score_fix, total, notes="", bonus=0, hypothesis=""):
    """Record per-bug scoring data. bonus=1 means agent found real bug different from GT."""
    ts = datetime.now().strftime("%Y-%m-%dT%H:%M")
    header = "timestamp\tbug_id\tgt_type\tagent_type\tscore_class\tscore_chain\tscore_evidence\tscore_root\tscore_cf\tscore_fix\ttotal\tbonus\thypothesis\tnotes\n"

    if not PER_BUG_FILE.exists():
        PER_BUG_FILE.write_text(header, encoding="utf-8")

    hyp_short = (hypothesis or "")[:80].replace("\t", " ").replace("\n", " ")
    line = f"{ts}\t{bug_id}\t{gt_type}\t{agent_type}\t{score_class}\t{score_chain}\t{score_evidence}\t{score_root}\t{score_cf}\t{score_fix}\t{total}\t{bonus}\t{hyp_short}\t{notes}\n"
    with open(PER_BUG_FILE, "a", encoding="utf-8") as f:
        f.write(line)

    bonus_flag = " [BONUS]" if bonus else ""
    log(f"Per-bug: {bug_id} type={agent_type} total={total}/8{bonus_flag} {notes}")

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"

    if cmd == "check":
        events = check_triggers()
        print(f"\n{len(events)} triggers found")

    elif cmd == "evolve":
        evolve(auto=False)

    elif cmd == "auto":
        evolve(auto=True)

    elif cmd == "append":
        ver, score, ttype, c4 = sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
        append_result(ver, score, ttype, c4, 10)

    elif cmd == "per-bug":
        # python pete-skill-evolve.py per-bug B01 T0 T0 1 1 1 2 1 1 7 "notes"
        bug_id, gt, agent = sys.argv[2], sys.argv[3], sys.argv[4]
        sc, sch, se, sr, scf, sf = [int(x) for x in sys.argv[5:11]]
        total = int(sys.argv[11])
        notes = sys.argv[12] if len(sys.argv) > 12 else ""
        append_per_bug(bug_id, gt, agent, sc, sch, se, sr, scf, sf, total, notes)

    elif cmd == "log":
        if GROWTH_LOG.exists():
            print(GROWTH_LOG.read_text(encoding="utf-8"))
        else:
            print("No growth log yet.")

    else:
        print("Usage: python pete-skill-evolve.py [check|evolve|auto|append|log]")
        print("  append <ver> <score> <ttype> <c4_hits> — record a T2 run")
