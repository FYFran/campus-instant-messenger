"""
试剑石 v2.0 迁移脚本 — 答案物理分离.

旧结构: bugs/B01_T0_nil_deref.md (描述+答案同文件)
新结构: bugs/B01/
          desc.md     ← agent 可读（用户视角描述）
          truth.md    ← 仅评分器可读（根因+修复+评分要点）
          verify.sh   ← 执行验证脚本（可选）
          inject.diff ← 注入补丁（可选，仅注入型 bug）

运行: python migrate_v2.py
"""

import re
import shutil
from pathlib import Path

BENCH_DIR = Path(__file__).parent
OLD_BUGS_DIR = BENCH_DIR / "bugs"
NEW_BUGS_DIR = BENCH_DIR / "bugset"  # 新目录名，避免和旧 bugs/ 冲突


def parse_old_bug(filepath: Path) -> dict:
    """Parse old bug format into structured data."""
    content = filepath.read_text(encoding="utf-8")

    # Parse header
    header = content.split("\n")[0]
    match = re.match(r"^#\s+(B\d+)\s*[—\-]\s*(T\d+):?\s*(.+)$", header)
    if not match:
        return None

    bug_id = match.group(1)
    bug_type = match.group(2)
    bug_title = match.group(3)

    # Extract description
    desc_match = re.search(
        r"## Bug 描述\s*\n(.*?)(?=## Ground Truth)",
        content, re.DOTALL
    )
    description = desc_match.group(1).strip() if desc_match else ""

    # Extract ground truth
    truth_match = re.search(
        r"## Ground Truth\s*\n(.*)",
        content, re.DOTALL
    )
    truth_text = truth_match.group(1).strip() if truth_match else ""

    return {
        "id": bug_id,
        "type": bug_type,
        "title": bug_title,
        "description": description,
        "truth": truth_text,
    }


def create_verify_script(bug: dict) -> str:
    """Generate a verify.sh for bugs that can be verified by running code."""
    scripts = {
        "B01": '#!/bin/bash\n# Verify: empty DB should return 200, not 500\n# Run: DATABASE_URL=postgres://... bash verify.sh\ncd f:/ClaudeFiles/campus_go\ngo test -tags=integration -run TestListActivitiesEmptyDB ./internal/handlers/',
        "B02": '#!/bin/bash\n# Verify: concurrent signup should not create duplicates\ncd f:/ClaudeFiles/campus_go\ngo test -tags=integration -run TestSignupConcurrent ./internal/handlers/',
        "B10": '#!/bin/bash\n# Verify: query plan should use index, not seq scan on signups\ncd f:/ClaudeFiles/campus_go\ngo test -run TestListActivitiesSQLSyntax ./internal/handlers/',
    }
    return scripts.get(bug["id"], "")


def migrate():
    """Run full migration."""
    if NEW_BUGS_DIR.exists():
        print(f"WARNING: {NEW_BUGS_DIR} already exists. Delete it first to re-migrate.")
        return

    NEW_BUGS_DIR.mkdir(parents=True, exist_ok=True)

    old_files = sorted(OLD_BUGS_DIR.glob("B*.md"))
    migrated = 0

    for filepath in old_files:
        bug = parse_old_bug(filepath)
        if not bug:
            print(f"  SKIP: {filepath.name} (parse failed)")
            continue

        # Create bug directory
        bug_dir = NEW_BUGS_DIR / bug["id"]
        bug_dir.mkdir(exist_ok=True)

        # Write desc.md (agent-readable)
        desc_content = f"# {bug['id']} — {bug['type']}: {bug['title']}\n\n## Bug 描述\n\n{bug['description']}\n"
        (bug_dir / "desc.md").write_text(desc_content, encoding="utf-8")

        # Write truth.md (scorer-only)
        truth_content = f"# {bug['id']} — Ground Truth\n\n{bug['truth']}\n"
        (bug_dir / "truth.md").write_text(truth_content, encoding="utf-8")

        # Write verify.sh (if applicable)
        verify = create_verify_script(bug)
        if verify:
            (bug_dir / "verify.sh").write_text(verify, encoding="utf-8")

        migrated += 1
        print(f"  {bug['id']}: desc.md + truth.md" + (" + verify.sh" if verify else ""))

    # Write README
    readme = """# 试剑石 Bug 库

## 目录结构

```
B01/
  desc.md     ← agent 可读（用户视角 bug 描述）
  truth.md    ← 仅评分器可读（根因 + 修复 + 评分要点）
  verify.sh   ← 执行验证脚本（可选）
  inject.diff ← 注入补丁（可选）

B02/
  ...
```

## 安全规则

1. **desc.md 公开** — agent 调查时只能读这个文件
2. **truth.md 私有** — 仅评分器（试剑石 Judge）有权读取
3. **verify.sh 私有** — 执行验证时由 sandbox 运行
4. **禁止 agent 读取 bugset/*/truth.md** — 违反 = 污染告警

## 注入型 Bug

| ID | 注入方式 | 注入目标 |
|----|---------|---------|
| B02 | 行替换 | activities.go (ON CONFLICT 移除) |
| B06 | 行替换 | activities.go (approval_required 逻辑反转) |
| B10 | 行替换 | activities.go (子查询替换为 0) |
"""
    (NEW_BUGS_DIR / "README.md").write_text(readme, encoding="utf-8")

    # Backup old bugs
    backup_dir = BENCH_DIR / "bugs_old_v1"
    if not backup_dir.exists():
        shutil.move(str(OLD_BUGS_DIR), str(backup_dir))
        print(f"\nOld bugs backed up to: {backup_dir}")

    print(f"\nMigrated {migrated}/{len(old_files)} bugs to {NEW_BUGS_DIR}")
    print("Next: update bughunt_harness.py to read from new structure")


if __name__ == "__main__":
    migrate()
