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

def check_triggers():
    """Check all 5 ring triggers from results.tsv."""
    results = load_results()
    events = []

    if not results:
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
            events.append({"ring":"R1_MINE","trigger":f"{len(commits)} fix commits","action":"python growth_engine.py mine","auto":False})
    except: pass

    # R2: Difficulty upgrade — bugs with 3+ perfect scores
    bug_scores = defaultdict(list)
    for r in results:
        bug_scores[r.get("bug_id","?")].append(int(r.get("score",0)))

    for bid, scores in bug_scores.items():
        if len(scores) >= 3 and sum(1 for s in scores if s >= 8) >= 3:
            events.append({"ring":"R2_RETIRE","trigger":f"{bid} 3x perfect","action":f"Retire {bid} -> harder variant","auto":False})

    # R3: Blind spot — same bug c4 consistently 0
    bug_c4 = defaultdict(list)
    for r in results:
        c4 = r.get("c4_hits","")
        if c4:
            bug_c4[r.get("bug_id","?")].append(int(c4))

    for bid, c4s in bug_c4.items():
        if len(c4s) >= 3 and sum(1 for c in c4s if c == 0) >= 3:
            events.append({"ring":"R3_BLINDSPOT","trigger":f"{bid} c4=0 x{len([c for c in c4s if c==0])}","action":"GEPA reflection -> F-rule","auto":True})

    # R4: Overfit — hold-out gap from recent runs
    if len(results) >= 5:
        recent = results[-10:]
        scores_list = [int(r["score"]) for r in recent]
        avg = sum(scores_list) / len(scores_list)
        recent_scores = [int(r["score"]) for r in results[-3:]]
        recent_avg = sum(recent_scores) / len(recent_scores)

        if recent_avg < avg - 4:
            events.append({"ring":"R4_OVERFIT","trigger":f"Recent avg {recent_avg:.0f} < overall {avg:.0f}","action":"Re-select hold-out + GEPA diversity","auto":True})

    # R5: Regression — score below baseline
    if len(results) >= 3:
        recent_3 = [int(r["score"]) for r in results[-3:]]
        avg3 = sum(recent_3) / len(recent_3)
        if avg3 < BASELINE_SCORE - 4:
            events.append({"ring":"R5_REGRESSION","trigger":f"3-run avg {avg3:.0f} < baseline {BASELINE_SCORE}","action":"GEPA analyze -> fix skill -> verify","auto":True})

    return events

def evolve(auto=False):
    """Execute triggered actions."""
    events = check_triggers()

    if not events:
        log("[OK] All clear. No triggers fired.")
        return

    auto_count = 0
    log(f"{len(events)} triggers:")
    for e in events:
        icon = "[AUTO]" if e["auto"] else "[MANUAL]"
        log(f"  {icon} [{e['ring']}] {e['trigger']}")
        log(f"       → {e['action']}")
        if auto and e["auto"]:
            auto_count += 1
            log(f"       [AUTO-EXEC] Would run: {e['action']}")

    log(f"Auto: {auto_count}/{len(events)} | Manual: {len(events)-auto_count}")
    return events

def append_from_workflow(skill_ver, score, ttype, c4_hits, total_bugs=10, model="deepseek-v4", condition="skill"):
    """Called after each T2/T3 run to record result."""
    append_result(skill_ver, score, ttype, c4_hits, total_bugs, model, condition)
    events = check_triggers()
    if events:
        log(f"[!] {len(events)} triggers after this run!")
        for e in events:
            log(f"  [{e['ring']}] {e['action']}")

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

    elif cmd == "log":
        if GROWTH_LOG.exists():
            print(GROWTH_LOG.read_text(encoding="utf-8"))
        else:
            print("No growth log yet.")

    else:
        print("Usage: python pete-skill-evolve.py [check|evolve|auto|append|log]")
        print("  append <ver> <score> <ttype> <c4_hits> — record a T2 run")
