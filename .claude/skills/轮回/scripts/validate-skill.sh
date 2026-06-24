#!/usr/bin/env bash
# Skill Lab — 快速验证脚本
# 检查 skill 的基本健康状态，不替代完整评估
set -euo pipefail

SKILL_DIR="${1:-}"
if [ -z "$SKILL_DIR" ]; then
  echo "Usage: validate-skill.sh <skill-directory>"
  exit 1
fi

SKILL_MD="$SKILL_DIR/SKILL.md"
if [ ! -f "$SKILL_MD" ]; then
  echo "FAIL: SKILL.md not found in $SKILL_DIR"
  exit 1
fi

ISSUES=0

# 1. Frontmatter 存在
if ! head -1 "$SKILL_MD" | grep -q '^---$'; then
  echo "WARN: No frontmatter found"
  ISSUES=$((ISSUES + 1))
fi

# 2. Constitution 存在（或至少有关键约束）
if ! grep -qi "CONSTITUTION\|安全约束\|绝对不能" "$SKILL_MD"; then
  echo "WARN: No CONSTITUTION or safety constraints found — forge will create one"
  ISSUES=$((ISSUES + 1))
fi

# 3. 体积检查
SIZE=$(wc -c < "$SKILL_MD")
if [ "$SIZE" -gt 50000 ]; then
  echo "WARN: SKILL.md is large ($SIZE bytes)"
  ISSUES=$((ISSUES + 1))
fi

# 4. 空行/格式
if grep -q $'\r' "$SKILL_MD"; then
  echo "WARN: CRLF line endings detected"
  ISSUES=$((ISSUES + 1))
fi

if [ "$ISSUES" -eq 0 ]; then
  echo "OK: $SKILL_MD passed basic checks"
else
  echo "DONE: $ISSUES warning(s) found (non-blocking)"
fi
