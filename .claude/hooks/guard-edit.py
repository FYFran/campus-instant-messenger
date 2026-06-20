"""PreToolUse Hook: Guard Edit/Write — Red lane file warnings + spec reminder."""
import os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

tool_name = os.environ.get("CLAUDE_TOOL_NAME", "")
file_path = os.environ.get("CLAUDE_TOOL_FILE_PATH", "")

RED_LANE_PATTERNS = [
    "auth", "login", "signin", "signup", "register", "credential",
    "payment", "pay", "billing", "crypto", "encrypt", "decrypt",
    "migration", "migrate", "schema", "token", "jwt", "session",
    "password", "secret", "otp", "permission", "role", "admin",
    "security", "safety", ".env", "config", "terraform", ".tf",
    "infrastructure", "iac"
]

YELLOW_LANE_PATTERNS = [
    "handler", "controller", "service", "middleware", "business",
    "api", "endpoint", "route", "database", "db", "query",
    "transform", "background", "job", "worker"
]

def check():
    if tool_name not in ("Edit", "Write"):
        return

    if not file_path:
        return

    filename = os.path.basename(file_path).lower()
    fullpath = file_path.lower()

    warnings = []

    # Red lane check
    for pattern in RED_LANE_PATTERNS:
        if pattern in fullpath:
            warnings.append(f"🔴 RED LANE: {file_path}")
            warnings.append("   AI只起草，人工重写。必须 senior+security review + 威胁模型。")
            warnings.append("   检查: AuthN/AuthZ | 加密正确 | 无硬编码密钥 | 输入验证")
            break

    if not warnings:
        for pattern in YELLOW_LANE_PATTERNS:
            if pattern in fullpath:
                warnings.append(f"🟡 YELLOW LANE: {file_path}")
                warnings.append("   需要 senior sign-off + SAST + 依赖扫描")
                break

    # Spec reminder for new files or large edits
    if tool_name == "Write":
        warnings.append("📋 新文件创建→确认有 spec.md?")
        warnings.append("   模板: f:/ClaudeFiles/spec-template.md")

    if warnings:
        print("\n".join(warnings))

check()
