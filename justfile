# Pete 项目命令手册 — 全部委托给 pete.py
# 用法: just <命令>
#       python pete.py <命令>  (等效)

# 一键发布：版本Bump→编译Go→编译Flutter→部署→装手机
release:
    bash scripts/release.sh

default:
    @just --list

# ── 开发 ──
fix:
    python pete.py fix
frontend-check:
    python pete.py frontend
go-check:
    python pete.py go-check
go-build:
    python pete.py go-build
backend-check:
    python pete.py backend
clean:
    python pete.py clean
selfcheck:
    python pete.py selfcheck

# ── 测试 ──
test-all:
    python pete.py test
test-fuzz:
    python test_fuzz.py
test-cross:
    python test_cross_backend.py
e2e:
    python pete.py e2e
ci:
    python pete.py ci
ci-all:
    python pete.py ci

# ── 编译 ──
build: check-build
    python pete.py build

check-build:
    @echo "=== Build Gate: build_check ==="
    python f:/ClaudeFiles/build_check.py
phone: build
    python pete.py phone

# ── 主控管线 ──
pipeline:
    bash pipeline_master.sh --full
pipeline-quick:
    bash pipeline_master.sh --quick
pipeline-deploy:
    bash pipeline_master.sh --deploy
pipeline-provenance:
    bash pipeline_provenance.sh
# ── Git hooks ──
hooks:
    lefthook run pre-commit
hooks-all:
    lefthook run pre-push

# ── 安全恢复（替代 git checkout --）──
restore file:
    @echo "=== RESTORE GATE ==="
    @echo "即将丢弃本地修改: {{file}}"
    @git diff -- {{file}} 2>&1 || echo "(new/untracked)"
    @echo "确认恢复？运行: git checkout -- {{file}}"

# ── 安全删除（替代 rm -rf）──
nuke target:
    @echo "=== NUKE GATE ==="
    @echo "检查: {{target}}"
    @python f:/ClaudeFiles/.claude/hooks/guard-rm-nuke.py "{{target}}"
# ── 蓝绿部署 ──
deploy-bg:
    bash deploy_blue_green.sh
# ── 测试 ──
test-e2e:
    bash e2e_user_flow.sh
test-load:
    bash load_test.sh 50 200
test-contract:
    python api_contract_test.py
test-schema:
    python schema_validate.py
test-migration:
    bash migration_test.sh
test-go:
    cd campus_go && JWT_SECRET=test DATABASE_URL=postgres://test go test ./... -count=1
# ── 全量测试 ──
test-all-extended: test-e2e test-load test-contract test-schema test-migration test-go

# ── 部署 ──
deploy:
    python pete.py deploy
server-deploy:
    python pete.py server-deploy
bump ver code:
    python pete.py bump {{ver}} {{code}}
rollback:
    python pete.py rollback

# ── 运维 ──
status:
    python pete.py status
dashboard:
    python pete.py dashboard
alert-test:
    python pete.py alert
emu:
    python pete.py emu

# ── 安全 ──
redteam:
    bash redteam_toolkit/run_arsenal.sh quick
redteam-full:
    bash redteam_toolkit/run_arsenal.sh full
redteam-api:
    bash redteam_toolkit/run_arsenal.sh api
redteam-mobile:
    bash redteam_toolkit/run_arsenal.sh mobile
redteam-db:
    bash redteam_toolkit/run_arsenal.sh db
review:
    python pete.py review
security-scan:
    bash security_scan.sh
