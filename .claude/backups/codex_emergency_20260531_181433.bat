@echo off
chcp 65001 >nul
title 皮特接入 Codex
cd /d f:\ClaudeFiles

echo.
echo   ========================================
echo     皮特 → Codex 接管
echo   ========================================
echo.
echo   选模式：
echo     [1] DeepSeek API — 编程+聊天，跟CC一样（需联网）
echo     [2] 本地 Ollama — 免费离线，弱但能聊
echo     [3] 自动检测
echo.

set /p mode="   输入 1/2/3: "
if "%mode%"=="" goto auto

if "%mode%"=="1" goto deepseek
if "%mode%"=="2" goto ollama
if "%mode%"=="3" goto auto
goto deepseek

:deepseek
echo.
echo   DeepSeek 模式启动...
:: 从 Python 取 API key
for /f "delims=" %%k in ('python -c "import json;print(json.load(open(r'f:\ClaudeFiles\pet_config.json','r',encoding='utf-8')).get('api_key',''))"') do set "DS_KEY=%%k"
set OPENAI_API_KEY=%DS_KEY%
set OPENAI_API_BASE=https://api.deepseek.com/v1
echo   Key: %DS_KEY:~0,12%...
codex --model deepseek-chat --cd f:/ClaudeFiles --sandbox danger-full-access --dangerously-bypass-approvals-and-sandbox --no-alt-screen
goto end

:ollama
echo.
echo   本地 Ollama 模式启动...
ollama serve >nul 2>&1
codex --oss --local-provider ollama --model pete-qwen3:latest --cd f:/ClaudeFiles --no-alt-screen
goto end

:auto
echo.
curl -s --connect-timeout 3 https://api.deepseek.com/chat/completions >nul 2>&1
if %errorlevel% equ 0 (
    echo   DeepSeek 通 → API 模式
    goto deepseek
) else (
    echo   DeepSeek 不通 → 本地 Ollama
    goto ollama
)

:end
echo.
echo   皮特已接入 Codex。
echo   如果记忆丢失，说：看看 codex_context.txt
pause
