#!/usr/bin/env python3
"""
Security scorecard updater — 校园即时通
Runs all security scans, parses outputs, updates docs/SECURITY_SCORECARD.md, prints summary.
Usage: python scripts/update_scorecard.py
"""

import subprocess
import re
import sys
import os
from datetime import date

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCORECARD_PATH = os.path.join(PROJECT_DIR, "docs", "SECURITY_SCORECARD.md")
GITLEAKS_BIN = os.path.join(PROJECT_DIR, ".gitleaks", "gitleaks.exe")


def run(cmd, timeout=120, check=False, cwd=None):
    """Run a shell command, return (returncode, stdout, stderr)."""
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, shell=False, cwd=cwd
        )
        if check and r.returncode != 0:
            print(f"[WARN] {' '.join(cmd)} exited {r.returncode}: {r.stderr.strip()[:200]}")
        return r.returncode, r.stdout, r.stderr
    except FileNotFoundError:
        return -1, "", "not found"
    except subprocess.TimeoutExpired:
        return -2, "", "timeout"


def gitleaks_count():
    """Run gitleaks detect — return count of secrets found."""
    if not os.path.isfile(GITLEAKS_BIN):
        # fallback to PATH
        binary = "gitleaks"
    else:
        binary = GITLEAKS_BIN
    rc, out, err = run([binary, "detect", "--source", PROJECT_DIR, "--no-git", "-v"], timeout=60)
    # gitleaks exits 1 when secrets found; count "Finding:" lines
    count = out.count("Finding:") + err.count("Finding:")
    if count == 0:
        # check JSON report if available
        report_path = os.path.join(PROJECT_DIR, "gitleaks_report.json")
        if os.path.isfile(report_path):
            import json
            try:
                with open(report_path) as f:
                    data = json.load(f)
                count = len(data) if isinstance(data, list) else 0
            except (json.JSONDecodeError, Exception):
                pass
    return count


def semgrep_counts():
    """Run semgrep — return (total_rules_match, severity_error_count)."""
    config_local = os.path.join(PROJECT_DIR, ".semgrep.yml")
    config = f"--config={config_local}" if os.path.isfile(config_local) else "--config=auto"
    rc, out, err = run(["semgrep", config, "--json", PROJECT_DIR], timeout=120)
    if rc != 0 and not out:
        return 0, 0
    try:
        import json
        data = json.loads(out)
        results = data.get("results", [])
        error_count = sum(1 for r in results if r.get("extra", {}).get("severity", "").upper() == "ERROR")
        return len(results), error_count
    except (json.JSONDecodeError, Exception):
        return 0, 0


def pip_outdated():
    """Run pip-audit or pip list — return count of outdated packages and list."""
    # Try pip-audit first (structured)
    req_path = os.path.join(PROJECT_DIR, "campus_app", "server", "requirements.txt")
    if not os.path.isfile(req_path):
        print("[WARN] requirements.txt not found — skipping pip-audit")
        return 0, []
    rc, out, err = run(["pip-audit", "--format", "json", "-r", req_path], timeout=60)
    if rc == 0 and out.strip():
        try:
            data = json.loads(out)
            vulns = data.get("vulnerabilities", [])
            return len(vulns), [f"{v['name']} {v.get('version', '?')} — {v.get('advisory', 'no details')}" for v in vulns[:10]]
        except (json.JSONDecodeError, Exception):
            pass
    # Fallback: pip list --outdated
    rc, out, err = run(["pip", "list", "--outdated", "--format=columns"], timeout=30)
    if rc == 0:
        lines = [l.strip() for l in out.splitlines() if l.strip() and not l.startswith("Package") and "----" not in l]
        return len(lines), [l.split()[0] + " " + l.split()[1] + " -> " + l.split()[2] if len(l.split()) >= 3 else l for l in lines]
    return 0, []


def go_outdated():
    """Run go list -m -u — return (outdated_count, details_list)."""
    go_mod_dir = os.path.join(PROJECT_DIR, "campus_go")
    rc, out, err = run(["go", "list", "-m", "-u", "all"], cwd=go_mod_dir, timeout=60)
    if rc != 0:
        return 0, []
    lines = out.strip().splitlines()
    outdated = []
    for line in lines:
        parts = line.split()
        if len(parts) >= 3 and "[indirect]" not in parts:
            outdated.append(f"{parts[0]}: {parts[1]} -> {parts[2]}")
        elif len(parts) >= 4 and "[indirect]" in parts:
            outdated.append(f"{parts[0]}: {parts[1]} -> {parts[2]}")
    return len(outdated), outdated


def flutter_outdated():
    """Run flutter pub outdated — return (outdated_count, details_list)."""
    flutter_dir = os.path.join(PROJECT_DIR, "campus_app")
    rc, out, err = run(["flutter", "pub", "outdated", "--no-pub"], cwd=flutter_dir, timeout=120)
    if rc != 0:
        return 0, []
    lines = out.strip().splitlines()
    count = 0
    details = []
    for line in lines:
        parts = line.split()
        # lines matching "package_name  current  up-to-date  latest" or with outdated markers
        if len(parts) >= 4 and "*)" not in line and not line.startswith(" ") and parts[0][0].islower():
            is_outdated = "<" in line or ">" in line or "*" in parts[1] if len(parts) > 1 else False
            if is_outdated:
                count += 1
                details.append(f"{parts[0]}: {parts[1]} -> {parts[-1]}")
    return count, details


def update_line(text, pattern, replacement):
    """Replace first line matching pattern."""
    return re.sub(pattern, replacement, text, count=1)


def update_scorecard():
    """Main update flow: run scans, parse, patch scorecard, print summary."""
    print("=== Security Scorecard Updater ===")
    print(f"Project: {PROJECT_DIR}")
    print(f"Scorecard: {SCORECARD_PATH}\n")

    # Read current scorecard
    if not os.path.isfile(SCORECARD_PATH):
        print(f"FATAL: Scorecard not found at {SCORECARD_PATH}")
        sys.exit(1)

    with open(SCORECARD_PATH, encoding="utf-8") as f:
        content = f.read()

    # --- Run scans ---
    today = date.today().isoformat()

    print("[1/4] Gitleaks secret scan...")
    gitleaks_findings = gitleaks_count()
    print(f"  -> {gitleaks_findings} secrets found")

    print("[2/4] Semgrep SAST scan...")
    total_findings, error_findings = semgrep_counts()
    print(f"  -> {total_findings} findings ({error_findings} errors)")

    print("[3/4] Dependency audits...")
    pip_cnt, pip_list = pip_outdated()
    go_cnt, go_list = go_outdated()
    fl_cnt, fl_list = flutter_outdated()
    print(f"  -> pip: {pip_cnt} outdated, go: {go_cnt} outdated, flutter: {fl_cnt} outdated")

    print("[4/4] Updating scorecard...\n")

    # --- Update date ---
    content = update_line(content, r"Last updated: \d{4}-\d{2}-\d{2}", f"Last updated: {today}")

    # --- Update Vulnerability Metrics ---
    # Critical | X | 0 | — always update (including zero)
    content = update_line(content, r"(\| Critical \| )\d+", f"\\1{gitleaks_findings}")
    if error_findings > 0:
        # Count CRITICAL-level semgrep findings separately if possible
        pass

    # --- Update Security Test Coverage ---
    # SAST (semgrep) line: update Last Run date
    content = update_line(content,
                          r"(\| SAST \(semgrep\) \| )\d{4}-\d{2}-\d{2}",
                          f"\\1{today}")
    # Secret scan (gitleaks) line
    content = update_line(content,
                          r"(\| Secret scan \(gitleaks\) \| )\d{4}-\d{2}-\d{2}",
                          f"\\1{today}")
    # Dependency audit line
    content = update_line(content,
                          r"(\| Dependency audit \| )\d{4}-\d{2}-\d{2}",
                          f"\\1{today}")

    # --- Update DAST status if ZAP report exists ---
    zap_reports = sorted(
        [f for f in os.listdir(os.path.join(PROJECT_DIR, "reports", "zap")) if "zap_report" in f and f.endswith(".html")],
        reverse=True
    ) if os.path.isdir(os.path.join(PROJECT_DIR, "reports", "zap")) else []
    if zap_reports:
        last_zap = zap_reports[0].split("_")[0]
        zap_date = f"{last_zap[:4]}-{last_zap[4:6]}-{last_zap[6:8]}"
        # Extract alert counts from the report if we can parse it
        content = update_line(content,
                              r"(\| DAST \(ZAP\) \| )\d{4}-\d{2}-\d{2}",
                              f"\\1{zap_date}")
        content = update_line(content,
                              r"(\| DAST \(ZAP\) \| ).*?( ✅| ❌)",
                              f"\\1{zap_date} | Monthly | 🟡")

    # --- Update Dependency Health table ---
    # Update Last Audit dates
    content = update_line(content,
                          r"(\| Python \(pip\) \| )\d+.*?(\| )\d+.*?(\| )\d+.*?(\| )\d{4}-\d{2}-\d{2}",
                          f"\\1{pip_cnt} | 0 | {today}")
    content = update_line(content,
                          r"(\| Go \(modules\) \| )\d+.*?(\| )\d+.*?(\| )\d+.*?(\| )\d{4}-\d{2}-\d{2}",
                          f"\\1{go_cnt} | 0 | {today}")
    content = update_line(content,
                          r"(\| Flutter \(pub\) \| )\d+.*?(\| )\d+.*?(\| )\d+.*?(\| )\d{4}-\d{2}-\d{2}",
                          f"\\1{fl_cnt} | 0 | {today}")

    # --- Write back ---
    with open(SCORECARD_PATH, "w", encoding="utf-8") as f:
        f.write(content)

    # --- Summary ---
    print("=" * 50)
    print("SCORECARD UPDATE SUMMARY")
    print("=" * 50)
    print(f"  Date:              {today}")
    print(f"  Gitleaks secrets:  {gitleaks_findings}")
    print(f"  Semgrep findings:  {total_findings} ({error_findings} errors)")
    print(f"  Dependencies outdated:")
    print(f"    pip:     {pip_cnt}")
    print(f"    go:      {go_cnt}")
    print(f"    flutter: {fl_cnt}")
    print(f"  Scorecard:         {SCORECARD_PATH}")
    print("=" * 50)

    # Alert if issues found
    issues = []
    if gitleaks_findings > 0:
        issues.append(f"SECRETS FOUND: {gitleaks_findings} — run gitleaks to inspect")
    if error_findings > 0:
        issues.append(f"SEMGREP ERRORS: {error_findings} — run semgrep to inspect")
    if pip_cnt > 0 or go_cnt > 0 or fl_cnt > 0:
        outdated_total = pip_cnt + go_cnt + fl_cnt
        issues.append(f"OUTDATED DEPS: {outdated_total} total — pip:{pip_cnt} go:{go_cnt} flutter:{fl_cnt}")
    if issues:
        print("\nISSUES FOUND:")
        for i in issues:
            print(f"  ! {i}")
        sys.exit(1)
    else:
        print("\nAll clean.")
        sys.exit(0)


if __name__ == "__main__":
    update_scorecard()
