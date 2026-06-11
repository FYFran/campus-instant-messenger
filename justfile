# Pete 项目命令手册 — 全部委托给 pete.py
# 用法: just <命令>
#       python pete.py <命令>  (等效)

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
test-e2e:
    python test_e2e.py
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
build:
    python pete.py build
phone: build
    python pete.py phone

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
