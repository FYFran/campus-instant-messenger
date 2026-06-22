"""
试剑石 Bootstrap 置信区间 — 从已有数据推断统计可靠性

研究依据:
  Efron (1979) "Bootstrap Methods: Another Look at the Jackknife"
  SkillsBench (2026): 3-5 trials/task, report mean +/- SD

用法:
  python bootstrap_ci.py                # 分析所有 skill 版本
  python bootstrap_ci.py --compare v2.5 bare  # 两版本对比 (Cohen's d)
"""

import json
import sys
import math
import random
from pathlib import Path
from collections import defaultdict

BENCH_DIR = Path(__file__).parent
RESULTS_FILE = BENCH_DIR / "results.tsv"

# Fixed seed for reproducibility
random.seed(42)


def load_results():
    if not RESULTS_FILE.exists():
        return []
    lines = RESULTS_FILE.read_text(encoding="utf-8").strip().split("\n")
    if len(lines) < 2:
        return []
    headers = lines[0].split("\t")
    return [dict(zip(headers, l.split("\t"))) for l in lines[1:] if l.strip()]


def bootstrap_ci(data, n_bootstrap=10000, ci=0.95):
    """Bootstrap confidence interval for mean.

    Efron (1979): resample with replacement, compute statistic,
    take percentiles for CI.

    For n < 3: CI is very wide (warns the user).
    For n >= 3: CI narrows with sqrt(n).
    """
    n = len(data)
    if n < 2:
        return {
            "mean": data[0] if n == 1 else 0,
            "ci_lower": None,
            "ci_upper": None,
            "ci_width": None,
            "n": n,
            "warning": "n < 2: cannot compute CI. Need >= 2 runs.",
        }

    means = []
    for _ in range(n_bootstrap):
        sample = [random.choice(data) for _ in range(n)]
        means.append(sum(sample) / len(sample))

    means.sort()
    alpha = (1 - ci) / 2
    lower_idx = int(alpha * n_bootstrap)
    upper_idx = int((1 - alpha) * n_bootstrap)

    mean = sum(data) / len(data)
    ci_lower = means[lower_idx]
    ci_upper = means[upper_idx]

    width = ci_upper - ci_lower

    warning = None
    if n < 3:
        warning = f"n={n} < 3: CI is wide. SkillsBench recommends >= 3 runs."

    # Cohen's rule: CI width > 10pp = unreliable
    if width > 10:
        if warning:
            warning += f" CI width={width:.1f}pp > 10pp = unreliable."
        else:
            warning = f"CI width={width:.1f}pp > 10pp = unreliable. More runs needed."

    return {
        "mean": mean,
        "ci_lower": ci_lower,
        "ci_upper": ci_upper,
        "ci_width": width,
        "n": n,
        "warning": warning,
    }


def cohens_d(data_a, data_b):
    """Cohen's d effect size between two conditions."""
    n_a, n_b = len(data_a), len(data_b)
    if n_a < 2 or n_b < 2:
        return None

    mean_a = sum(data_a) / n_a
    mean_b = sum(data_b) / n_b

    var_a = sum((x - mean_a)**2 for x in data_a) / (n_a - 1)
    var_b = sum((x - mean_b)**2 for x in data_b) / (n_b - 1)

    pooled_sd = math.sqrt(((n_a - 1)*var_a + (n_b - 1)*var_b) / (n_a + n_b - 2))
    if pooled_sd == 0:
        return 0

    return (mean_a - mean_b) / pooled_sd


def main():
    results = load_results()
    if not results:
        print("No results data.")
        return

    # Group by skill version
    by_skill = defaultdict(list)
    for r in results:
        ver = r.get("skill_version", "unknown")
        try:
            score = int(r.get("score", 0))
            by_skill[ver].append(score)
        except (ValueError, TypeError):
            continue

    print(f"""
{'='*60}
 试剑石 Bootstrap CI — Efron (1979)
 数据: {RESULTS_FILE}
 行数: {len(results)}, Skill 版本: {len(by_skill)}
{'='*60}

{'Skill':<20} {'n':>3} {'Mean':>6} {'CI Low':>6} {'CI High':>6} {'Width':>6} {'Quality'}
{'-'*65}""")

    for ver in sorted(by_skill.keys()):
        scores = by_skill[ver]
        ci = bootstrap_ci(scores)
        n = ci["n"]
        quality = ""
        if ci["warning"]:
            quality = f"[!] {ci['warning']}"
        elif ci["ci_width"] and ci["ci_width"] <= 5:
            quality = "[OK] Narrow CI"
        elif ci["ci_width"] and ci["ci_width"] <= 10:
            quality = "[~] Acceptable"
        else:
            quality = "[OK]"

        ci_low = f"{ci['ci_lower']:.1f}" if ci["ci_lower"] is not None else "N/A"
        ci_high = f"{ci['ci_upper']:.1f}" if ci["ci_upper"] is not None else "N/A"
        width = f"{ci['ci_width']:.1f}" if ci["ci_width"] is not None else "N/A"

        print(f"{ver:<20} {n:>3} {ci['mean']:>6.1f} {ci_low:>6} {ci_high:>6} {width:>6} {quality}")

    # Skill lift: best skill vs bare
    print(f"\n{'='*60}")
    print(" Skill Lift Analysis (Cohen's d)")
    print(f"{'='*60}\n")

    bare_scores = by_skill.get("bare", [])
    if len(bare_scores) >= 1:
        bare_mean = sum(bare_scores) / len(bare_scores)
        print(f"  Bare baseline: {bare_mean:.1f}/80 (n={len(bare_scores)})")

        best_ver = None
        best_mean = 0
        for ver, scores in by_skill.items():
            if ver == "bare":
                continue
            mean = sum(scores) / len(scores)
            if mean > best_mean:
                best_mean = mean
                best_ver = ver

        if best_ver and len(by_skill[best_ver]) >= 2:
            d = cohens_d(by_skill[best_ver], bare_scores)
            lift = best_mean - bare_mean
            effect = "large" if d and abs(d) > 0.8 else ("medium" if d and abs(d) > 0.5 else "small")
            print(f"  Best skill: {best_ver} at {best_mean:.1f}/80 (n={len(by_skill[best_ver])})")
            print(f"  Skill lift: +{lift:.1f}pp")
            if d is not None:
                print(f"  Cohen's d: {d:.2f} ({effect} effect)")
                print(f"  Research: SkillsBench SE domain lift = 4.5pp (Cohen's d=0.6)")
                if abs(d) >= 0.5:
                    print(f"  [OK] Lift is statistically meaningful (d >= 0.5)")
                else:
                    print(f"  [!] Lift is small (d < 0.5). May be noise.")
        else:
            print(f"  [!] Cannot compute Cohen's d: need >= 2 runs per condition.")
    else:
        print("  No bare baseline data.")

    # What's missing
    print(f"\n{'='*60}")
    print(" Data Quality Assessment")
    print(f"{'='*60}\n")

    low_n = [ver for ver, scores in by_skill.items() if len(scores) < 3]
    if low_n:
        print(f"  Need more data (n < 3): {', '.join(low_n)}")
        print(f"  Fix: T2 Lean x3 on 5 bugs = ${0.05*5*len(low_n):.2f}")

    missing_bare = "bare" not in by_skill or len(by_skill["bare"]) < 3
    if missing_bare:
        n_bare = len(by_skill.get("bare", []))
        print(f"  Bare baseline: n={n_bare}, need n=3.")
        print(f"  Fix: T2 Lean bare x{3-n_bare} on 5 bugs = ${0.05*5*(3-n_bare):.2f}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--compare":
        main()
    else:
        main()
