"""SessionStart Hook: Auto-inject BOOT.md + recent MEMORY into context."""
import os, sys

boot_path = "f:/ClaudeFiles/.claude/BOOT.md"
memory_dir = "C:/Users/31704/.claude/projects/f--ClaudeFiles/memory"
kernel_path = "f:/ClaudeFiles/KERNEL.md"

output = []

# 1. Load KERNEL
if os.path.exists(kernel_path):
    output.append("## KERNEL（物理门已就位，路由表可用）")
    output.append(open(kernel_path, encoding="utf-8").read()[:3000])

# 1.5 Load Code Quality Rules (IVR Framework)
checklist_path = "f:/ClaudeFiles/CODE_REVIEW_CHECKLIST.md"
if os.path.exists(checklist_path):
    output.append("## AI代码质量法则（IVR: Intent-Validation-Refinement）")
    output.append("Spec先于代码 | AI输出=Draft Zero | 小块迭代 | 5min review per 1min gen")
    output.append(f"10点清单: {checklist_path}")
    output.append(f"spec模板: f:/ClaudeFiles/spec-template.md")

# 2. Load SYSTEM_STATE
state_path = os.path.join(memory_dir, "SYSTEM_STATE.md")
if os.path.exists(state_path):
    output.append("## 装备状态快照")
    output.append(open(state_path, encoding="utf-8").read()[:2000])

# 3. Load active tasks
tasks_path = "f:/ClaudeFiles/.claude/ACTIVE_TASKS.md"
if os.path.exists(tasks_path):
    output.append("## 活跃任务")
    output.append(open(tasks_path, encoding="utf-8").read()[:1000])

# 4. Load recent memory
memories = []
if os.path.exists(memory_dir):
    for f in sorted(os.listdir(memory_dir), reverse=True):
        if f.endswith(".md") and f not in ("MEMORY.md", "SYSTEM_STATE.md"):
            mem_path = os.path.join(memory_dir, f)
            try:
                content = open(mem_path, encoding="utf-8").read()
                memories.append(f"- [{f[:-3]}]: {content[:120]}")
            except:
                pass
            if len(memories) >= 5:
                break

if memories:
    output.append("## 最近记忆")
    output.extend(memories)

print("\n\n".join(output))
