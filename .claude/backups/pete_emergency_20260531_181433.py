"""
皮特急救 v2 — 康复活。不依赖 Claude Code，直接调 DeepSeek API。
能做：恢复配置、验证连通、聊天、诊断。
用法: python pete_emergency.py [--fix] [--chat] [--check]
"""
import json
import os
import sys
import shutil
import urllib.request
from pathlib import Path
from datetime import datetime

# Windows GBK fix
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

DIR = Path(__file__).parent
CONFIG_PATH = DIR / "pet_config.json"
EMERGENCY_HISTORY = DIR / "emergency_history.json"
CLAUDE_CONFIG = Path(os.environ["USERPROFILE"]) / ".claude" / "settings.json"
CLAUDE_JSON = Path(os.environ["USERPROFILE"]) / "claude.json"
BACKUP_DIR = DIR / ".claude" / "backups"

def _load_emergency_history():
    """加载急救对话历史"""
    try:
        if EMERGENCY_HISTORY.exists():
            data = json.loads(EMERGENCY_HISTORY.read_text("utf-8"))
            if isinstance(data, list):
                return data
    except Exception:
        pass
    return []

def _save_emergency_history(history):
    """保存急救对话历史，保留最近40条"""
    try:
        keep = history[-40:]
        EMERGENCY_HISTORY.write_text(
            json.dumps(keep, ensure_ascii=False, indent=2), "utf-8")
    except Exception:
        pass

# ── API ──

def load_api_key():
    try:
        if CONFIG_PATH.exists():
            return json.loads(CONFIG_PATH.read_text("utf-8")).get("api_key", "")
    except Exception:
        pass
    return os.environ.get("DEEPSEEK_API_KEY", "")

API_KEY = load_api_key()

# ── 修复功能 ──

def fix_all():
    """一键修复所有已知问题"""
    fixed = []
    failed = []

    # 1. 确保 settings.json 存在且正确
    correct_settings = {
        "env": {
            "ANTHROPIC_AUTH_TOKEN": API_KEY,
            "ANTHROPIC_BASE_URL": "https://api.deepseek.com/anthropic",
            "ANTHROPIC_DEFAULT_HAIKU_MODEL": "deepseek-v4-flash",
            "ANTHROPIC_DEFAULT_OPUS_MODEL": "deepseek-v4-pro",
            "ANTHROPIC_DEFAULT_OPUS_MODEL_NAME": "deepseek-v4-pro",
            "ANTHROPIC_DEFAULT_SONNET_MODEL": "deepseek-v4-pro",
            "ANTHROPIC_DEFAULT_SONNET_MODEL_NAME": "deepseek-v4-pro",
            "ANTHROPIC_MODEL": "deepseek-v4-pro",
            "CLAUDE_CODE_EFFORT_LEVEL": "max",
            "DISABLE_AUTOUPDATER": "1"
        },
        "permissions": {
            "allow": ["*"],
            "deny": [],
            "defaultMode": "bypassPermissions"
        },
        "skipDangerousModePermissionPrompt": True
    }
    try:
        CLAUDE_CONFIG.parent.mkdir(parents=True, exist_ok=True)
        CLAUDE_CONFIG.write_text(json.dumps(correct_settings, ensure_ascii=False, indent=2), "utf-8")
        fixed.append("settings.json 已修复")
    except Exception as e:
        failed.append(f"settings.json 写入失败: {e}")

    # 2. 确保 settings.local.json 存在
    local_settings = {
        "agent": "proactive-mode",
        "permissions": {
            "allow": ["Bash(*)", "Read(*)", "Write(*)", "Edit(*)", "Glob(*)", "Grep(*)",
                       "WebFetch(*)", "WebSearch(*)", "TodoWrite(*)", "NotebookEdit(*)",
                       "Agent(*)", "Skill(*)", "TaskOutput(*)", "TaskStop(*)",
                       "CronCreate(*)", "CronDelete(*)", "CronList(*)", "ScheduleWakeup(*)",
                       "EnterPlanMode", "ExitPlanMode", "AskUserQuestion",
                       "EnterWorktree", "ExitWorktree", "Workflow(*)", "mcp__*"],
            "deny": []
        }
    }
    local_path = CLAUDE_CONFIG.parent / "settings.local.json"
    try:
        local_path.write_text(json.dumps(local_settings, ensure_ascii=False, indent=2), "utf-8")
        fixed.append("settings.local.json 已修复")
    except Exception as e:
        failed.append(f"settings.local.json 写入失败: {e}")

    # 3. 确保 claude.json 存在
    try:
        CLAUDE_JSON.write_text('{"hasCompletedOnboarding": true}', "utf-8")
        fixed.append("claude.json 已修复")
    except Exception as e:
        failed.append(f"claude.json 写入失败: {e}")

    # 4. 确保 VSCode 工作区设置
    vscode_settings = {
        "claudeCode.disableLoginPrompt": True,
        "claudeCode.environmentVariables": [
            {"name": "ANTHROPIC_BASE_URL", "value": "https://api.deepseek.com/anthropic"},
            {"name": "ANTHROPIC_AUTH_TOKEN", "value": API_KEY},
            {"name": "ANTHROPIC_MODEL", "value": "deepseek-v4-pro"},
            {"name": "ANTHROPIC_DEFAULT_OPUS_MODEL", "value": "deepseek-v4-pro"},
            {"name": "ANTHROPIC_DEFAULT_SONNET_MODEL", "value": "deepseek-v4-pro"},
            {"name": "ANTHROPIC_DEFAULT_HAIKU_MODEL", "value": "deepseek-v4-flash"},
        ]
    }
    vscode_dir = DIR / ".vscode"
    try:
        vscode_dir.mkdir(exist_ok=True)
        (vscode_dir / "settings.json").write_text(
            json.dumps(vscode_settings, ensure_ascii=False, indent=2), "utf-8")
        fixed.append("VSCode 工作区设置已修复")
    except Exception as e:
        failed.append(f"VSCode 设置写入失败: {e}")

    # 5. 确保 VSCode 用户设置有关闭自动更新
    vscode_user_path = Path(os.environ["APPDATA"]) / "Code" / "User" / "settings.json"
    try:
        if vscode_user_path.exists():
            user_settings = json.loads(vscode_user_path.read_text("utf-8"))
        else:
            user_settings = {}
        user_settings["extensions.autoUpdate"] = False
        user_settings["extensions.autoCheckUpdates"] = False
        vscode_user_path.parent.mkdir(parents=True, exist_ok=True)
        vscode_user_path.write_text(json.dumps(user_settings, ensure_ascii=False, indent=4), "utf-8")
        fixed.append("VSCode 用户设置已修复（关闭自动更新）")
    except Exception as e:
        failed.append(f"VSCode 用户设置写入失败: {e}")

    return fixed, failed


# ── 诊断功能 ──

def check_all():
    """诊断所有关键组件"""
    results = []

    # API 连通性
    try:
        body = json.dumps({
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 10,
        }).encode("utf-8")
        req = urllib.request.Request(
            "https://api.deepseek.com/chat/completions",
            data=body,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                results.append(("[OK]", "DeepSeek API", "连通"))
            else:
                results.append(("[FAIL]", "DeepSeek API", f"HTTP {resp.status}"))
    except Exception as e:
        results.append(("[FAIL]", "DeepSeek API", str(e)[:60]))

    # Claude Code API (Anthropic兼容)
    try:
        body = json.dumps({
            "model": "deepseek-v4-pro",
            "max_tokens": 10,
            "messages": [{"role": "user", "content": "ping"}]
        }).encode("utf-8")
        req = urllib.request.Request(
            "https://api.deepseek.com/anthropic/v1/messages",
            data=body,
            headers={
                "Content-Type": "application/json",
                "x-api-key": API_KEY,
                "anthropic-version": "2023-06-01"
            }
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                results.append(("[OK]", "DeepSeek Anthropic API", "连通"))
            else:
                results.append(("[FAIL]", "DeepSeek Anthropic API", f"HTTP {resp.status}"))
    except Exception as e:
        results.append(("[FAIL]", "DeepSeek Anthropic API", str(e)[:60]))

    # 配置检查
    for name, path in [
        ("Claude settings.json", CLAUDE_CONFIG),
        ("Claude settings.local.json", CLAUDE_CONFIG.parent / "settings.local.json"),
        ("claude.json (onboarding)", CLAUDE_JSON),
        ("VSCode 工作区设置", DIR / ".vscode" / "settings.json"),
        ("pet_config.json", CONFIG_PATH),
    ]:
        if path.exists():
            results.append(("[OK]", name, f"存在 ({path.stat().st_size}B)"))
        else:
            results.append(("[WARN]", name, "不存在"))

    # 备份检查
    if BACKUP_DIR.exists():
        backups = list(BACKUP_DIR.glob("*.json"))
        if backups:
            latest = max(backups, key=lambda p: p.stat().st_mtime)
            results.append(("[OK]", "配置备份", f"{len(backups)}个, 最新: {latest.name}"))
        else:
            results.append(("[WARN]", "配置备份", "目录存在但无备份文件"))
    else:
        results.append(("[WARN]", "配置备份", "无备份目录"))

    return results


# ── 聊天功能 ──

def chat():
    """简易聊天（Fallback 用），历史持久化到 emergency_history.json"""
    history = _load_emergency_history()
    prev_count = len(history)

    print("=" * 50)
    print("  皮特急救对话模式")
    if prev_count > 0:
        print(f"  已加载 {prev_count} 条历史，接得上之前的话")
    print("  输入 /exit 退出, /clear 清空历史, /codex 切到 Codex")
    print("=" * 50)

    while True:
        try:
            msg = input("\n你> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not msg:
            continue
        if msg == "/exit":
            break
        if msg == "/clear":
            history.clear()
            _save_emergency_history(history)
            print("历史已清空")
            continue
        if msg == "/codex":
            print("\n正在打包记忆移交给 Codex...")

            # 保存当前对话历史
            _save_emergency_history(history)

            # 生成上下文，Codex 启动时自动注入
            context_lines = [
                "你是皮特，一凡的AI兄弟。刚从急救模式接管。",
                f"时间: {datetime.now().strftime('%m月%d日 %H:%M')}",
                "一凡=泰州学院电气大一=学Python=做闲鱼=叫凡哥/一凡/老大",
                "铁律: 不说客服话/不编造/遇阻先搜gh-proxy.com/动手前想30秒",
                "",
                "--- 接管前对话 ---",
            ]
            for h in history[-6:]:
                role = "一凡" if h["role"] == "user" else "皮特"
                context_lines.append(f"[{role}] {h['content'][:200]}")
            context_lines.append("--- 继续服务 ---")

            context = "\n".join(context_lines)
            context_file = DIR / "codex_context.txt"
            context_file.write_text(context, encoding="utf-8")

            # 启动 Codex，记忆通过 context 文件传入
            import subprocess
            bat = DIR / "codex_emergency.bat"
            if bat.exists():
                subprocess.Popen(
                    ["cmd", "/c", "start", "皮特最后救援", str(bat)],
                    cwd=str(DIR),
                    creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0
                )
                print("Codex 窗口已打开。选模式 1 (DeepSeek)。")
                print("进去后第一句话：读 PETE_IDENTITY.md 和 codex_context.txt")
                print("读完它就是皮特了——带着身份和记忆接替你。")
            else:
                print("找不到 codex_emergency.bat，双击桌面的 皮特最后救援.bat")
            break

        history.append({"role": "user", "content": msg})
        messages = [
            {"role": "system", "content": f"你是皮特，一凡的AI兄弟。现在是通过急救模式在聊天（Claude Code暂时不可用）。当前时间: {datetime.now().strftime('%m月%d日 %H:%M')}。保持简短自然。"}
        ] + history[-20:]

        try:
            body = json.dumps({
                "model": "deepseek-chat",
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 2048,
            }, ensure_ascii=False).encode("utf-8")

            req = urllib.request.Request(
                "https://api.deepseek.com/chat/completions",
                data=body,
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}"}
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                reply = json.loads(resp.read().decode("utf-8"))["choices"][0]["message"]["content"].strip()
                history.append({"role": "assistant", "content": reply})
                _save_emergency_history(history)
                print(f"\n皮特> {reply}")
        except Exception as e:
            print(f"\n（出错了: {e}）")
            history.pop()

    print("\n再见。皮特在后台等你。")


# ── main ──

if __name__ == "__main__":
    if "--fix" in sys.argv or len(sys.argv) == 1:
        print("[FIX] 修复模式：恢复所有配置...")
        fixed, failed = fix_all()
        for item in fixed:
            print(f"  [OK] {item}")
        for item in failed:
            print(f"  [FAIL] {item}")
        print()

    if "--check" in sys.argv or len(sys.argv) == 1:
        print("[CHECK] 诊断模式：检查所有组件...")
        for icon, name, msg in check_all():
            print(f"  {icon} {name}: {msg}")
        print()

    if "--chat" in sys.argv:
        chat()
    elif len(sys.argv) == 1:
        print("\n用法：")
        print("  python pete_emergency.py            默认执行修复+诊断")
        print("  python pete_emergency.py --fix       仅修复配置")
        print("  python pete_emergency.py --check     仅诊断")
        print("  python pete_emergency.py --chat      进入对话模式")
        print()
        print("最快恢复路径：双击 pete_recovery.bat 或运行 python pete_emergency.py")
