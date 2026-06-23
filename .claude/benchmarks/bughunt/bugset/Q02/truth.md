# Q02 — Ground Truth

**Type:** Q1 — 安全检查被跳过（Skipped gitleaks git-history scan）

**根因:** `.lefthook.yml` 中 gitleaks 的 pre-commit hook 使用了默认配置，只扫描 staged changes（`git diff --cached`），不扫描完整 git 历史。如果敏感信息在之前的 commit 中已经提交过，pre-commit hook 不会发现。

同时 `lefthook.yml` 中只配置了 `go-fmt` 和 `dart-format`（都标记为 skip），gitleaks 是唯一实际运行的检查。如果 gitleaks 的覆盖范围有限（只扫 staged），整体防线就被动摇了。

**验证:**
1. 查看 `.lefthook.yml` → 确认 gitleaks 配置
2. 检查 gitleaks 是否配置了 `--no-git` 或缺少 `detect --source=.` 全量扫描
3. 测试：在一个包含历史 secret 的仓库里跑 pre-commit → gitleaks 不报（只扫 diff）

**评分要点:**
- 分类: Q1 检查跳过 (1pt)
- 证据: lefthook.yml 配置分析 + gitleaks 覆盖范围证明 (1pt)
- 根因: pre-commit 只扫 staged，不扫历史 (2pt)
- CF: 加全量扫描 → 发现历史中的 secret (1pt)
- 修复: gitleaks 加 scheduled full scan 或 detect --source=. (1pt)
- 防御建议: 分层防线 — pre-commit(staged) + CI(full scan) (1pt)
- 链完整 (1pt)
