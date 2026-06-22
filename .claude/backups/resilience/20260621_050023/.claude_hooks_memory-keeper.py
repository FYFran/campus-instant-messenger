"""Stop Hook: Auto-save state, extract lessons, update BOOT.md."""
import os, sys, subprocess
from datetime import datetime, timedelta

now = datetime.now().strftime("%Y-%m-%d %H:%M")

# 1. Scan recent memory files
memory_dir = os.path.expanduser("~/.claude/projects/f--ClaudeFiles/memory")
recent_lessons = []
try:
    files = []
    for f in os.listdir(memory_dir):
        if f.endswith(".md") and f != "MEMORY.md" and f != "SYSTEM_STATE.md":
            path = os.path.join(memory_dir, f)
            mtime = os.path.getmtime(path)
            files.append((mtime, f))
    files.sort(reverse=True)
    recent_lessons = [f"- {name}" for _, name in files[:5]]
except:
    recent_lessons = ["(无法读取 memory 目录)"]

recent_lessons_text = "\n".join(recent_lessons) if recent_lessons else "(暂无)"

# 2. Generate BOOT.md snapshot
boot = f"""# BOOT.md — 自动生成 ({now})

## 装备状态
- Hermes Agent: 检查 `~/.local/bin/hermes gateway status`
- Gateway PID: 上次记录 9872
- DeepSeek V4 API: ✅
- HK隧道: 139.196.50.134
- TokenLine服务器: 47.82.103.247

## 物理门状态
- guard-build: ✅ 编译前强制 build_check
- guard-git-checkout: ✅ 禁止 git checkout 单文件
- guard-force-push: ✅ 禁止 force push
- guard-rm: ✅ 禁止 rm -rf 项目目录

## 最近教训
启动后立刻 Run: watcher 扫一圈。然后 Read memory/MEMORY.md 最后 5 条 memory。
审查/debug 前强制 recall: search_nodes query="当前任务关键词"

最近 5 条 memory:
{recent_lessons_text}

## 最近变更
自动从 git log 提取最近 3 次提交

## 活跃任务
检查 ACTIVE_TASKS.md
"""

boot_path = "f:/ClaudeFiles/.claude/BOOT.md"
with open(boot_path, "w", encoding="utf-8") as f:
    f.write(boot)

# 3. Trigger event log snapshot (PROJECTMEM: regenerate MEMORY.md from events)
try:
    subprocess.run(
        ["python", "f:/ClaudeFiles/.claude/pete-eventlog.py", "snapshot"],
        capture_output=True, text=True, timeout=15
    )
except:
    pass

# 4. Append git log to BOOT
try:
    result = subprocess.run(
        ["git", "-C", "f:/ClaudeFiles", "log", "--oneline", "-5"],
        capture_output=True, text=True, timeout=10
    )
    with open(boot_path, "a", encoding="utf-8") as f:
        f.write(f"\n## 最近提交\n```\n{result.stdout}\n```\n")
except:
    pass

print(f"✅ BOOT.md 已更新 ({now}) — 注入 {len(recent_lessons)} 条最近教训")
