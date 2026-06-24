# Q02 — Q1: Skipped Security Check in Pipeline

## Bug 描述

campus_go 的 pre-commit hook 配置中，gitleaks 扫描配置了 `--no-git` 标志，跳过了对 git 历史中敏感信息的扫描。检查 `.lefthook.yml` 和相关 hook 配置，确认哪些安全检查被跳过或配置不当。

目标：找出被跳过的安全检查，证明它能漏掉已知的敏感信息。
