# ClaudeAll Architecture Verification Procedure

## Prerequisites
Close this session. Open new Claude Code session. Run each test in order.

---

## Test 1: SessionStart — Boot Injection
**What to check**: New session starts with KERNEL.md + equipment status auto-injected.
**Pass if**: First response mentions "KERNEL" or "路由表" or shows equipment status without you asking.
**Fail if**: I look confused, don't know what tools I have, ask basic setup questions.
**Fix if fail**: 
- Check SessionStart hook in settings.json has correct path to boot-injector.py
- Run `python f:/ClaudeFiles/.claude/hooks/boot-injector.py` manually to verify it outputs content
- If no output: check file paths inside boot-injector.py

---

## Test 2: UserPromptSubmit — Task Router
**Test 2a — Should route**: Type: "帮我修一下 campus_check.py 里的 bug"
**Pass if**: Response starts with "@router: caveman:builder + code-reviewer + security-auditor" or I immediately spawn those agents
**Test 2b — Should NOT route**: Type: "好的知道了"
**Pass if**: No "@router:" prefix, normal conversation flow

**Fix if fail**:
- Run `python f:/ClaudeFiles/.claude/hooks/task-router.py` and type input manually
- Check CLAUDE_USER_PROMPT env var actually available
- If env var missing: rewrite task-router to read from stdin as fallback

---

## Test 3: PreToolUse — Build Guard (most critical)
**Test**: Ask me: "帮我编译 APK"
**Pass if**: Before running flutter build, hook runs build_check.py first. If build_check fails → blocked.
**Fail if**: flutter build runs directly without build_check.

**Fix if fail**:
- Check matcher pattern: `Bash(*flutter build*)` — verify glob syntax
- Try matcher: `Bash(*build*)` or just `Bash` with guard-build.py checking the command itself
- Test guard-build.py standalone: `python f:/ClaudeFiles/.claude/hooks/guard-build.py`
- If script works standalone but hook doesn't fire: matcher issue

---

## Test 4: PreToolUse — Git Guard
**Test**: Ask me: "用 git checkout -- 恢复 campus_check.py"
**Pass if**: BLOCKED with message about Git铁锁
**Fail if**: git checkout runs

**Fix if fail**:
- Same matcher debugging as Test 3
- The guard-git-checkout.py always exits 1 — if hook fires, it WILL block

---

## Test 5: PreToolUse — Force Push Guard
**Test**: Ask me: "git push --force origin master"
**Pass if**: BLOCKED
**Fail if**: push runs (or asks for confirmation first — that's also valid)

---

## Test 6: PreToolUse — RM Guard
**Test**: Ask me: "帮我删掉 rm -rf f:/ClaudeFiles/_research/"
**Pass if**: BLOCKED (path contains protected strings)
**Fail if**: rm runs

**Known issue**: guard-rm.py reads `CLAUDE_TOOL_COMMAND` env var — if this var doesn't exist, guard passes (allows). This is a fail-safe: missing var = don't block legitimate rm.
**Fix**: If env var name is wrong, update guard-rm.py with correct var name.

---

## Test 7: PostToolUse — Auto Check
**Test**: Ask me: "把 campus_check.py 加一行注释"
**Pass if**: After Edit completes, I mention running campus_check or show check results
**Fail if**: No check triggered

**Fix if fail**:
- PostToolUse hook might not fire with correct env vars
- `CLAUDE_TOOL_NAME` and `CLAUDE_TOOL_FILE_PATH` might have different names
- Simplest fix: change matcher to broader pattern, or remove env var dependency

---

## Test 8: Stop — Memory Keeper
**Test**: End session normally. Then check `f:/ClaudeFiles/.claude/BOOT.md` timestamp.
**Pass if**: BOOT.md timestamp matches session end time, contains git log
**Fail if**: BOOT.md unchanged

---

## Quick Sanity (30 seconds)

Open new session. Say: "hi". If I respond with:
- Equipment status visible
- KERNEL routing table mentioned  
- I know what tools I have
→ Architecture working.

If I respond like a blank-slate Claude who knows nothing:
→ Hooks not firing. Debug SessionStart first.

---

## Emergency Rollback

If everything is broken and I'm useless:
```bash
cp f:/ClaudeFiles/.claude/backups/CLAUDE.md.*.bak f:/ClaudeFiles/CLAUDE.md
cp f:/ClaudeFiles/.claude/backups/CLAUDE.md.*.bak f:/ClaudeFiles/.claude/CLAUDE.md
```
Then restore settings.json from git: `git checkout C:/Users/31704/.claude/settings.json`
