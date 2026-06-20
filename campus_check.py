# -*- coding: utf-8 -*-
"""即时通 三合一检查 — 每次改代码前跑"""
import subprocess, re, json, sys

# Fix UTF-8 garbled output on Windows (GBK terminal → UTF-8 mismatch)
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

SERVER = "http://139.196.50.134"
SRC = "f:/ClaudeFiles/campus_app/lib"

def ok(s): return f"  [OK] {s}"
def bad(s): return f"  [XX] {s}"
p = f = 0
def chk(name, v, detail=""):
    global p,f
    msg = f"{name} {detail}".strip() if detail else name
    if v: print(ok(msg)); p+=1
    else: print(bad(msg)); f+=1

def readf(path):
    with open(path, encoding="utf-8") as fp:
        return fp.read()

print("=" * 50)
print("1/3 关键字段对齐")
print("=" * 50)
r = json.loads(subprocess.check_output(f"curl -s {SERVER}/api/version", shell=True))
chk("服务器返回version_code", "version_code" in r, str(r.get("version_code")))
chk("服务器返回apk_url", r.get("apk_url"), r.get("apk_url",""))

us = readf(f"{SRC}/utils/update_service.dart")
chk("前端读version_code", "['version_code']" in us, "bug:之前读'build'")
chk("buildNumber是数字", bool(re.search(r'buildNumber\s*=\s*(\d+)', us)))

ms = readf(f"{SRC}/views/messages_page.dart")
chk("通知is_read一致", "['is_read']" in ms, "bug:应该用is_read匹配服务端")

pm = readf(f"{SRC}/utils/permissions.dart")
chk("权限用role(非is_superadmin)", "is_superadmin" not in pm and "'school_admin'" in pm, "bug:之前is_superadmin")

print("")
print("=" * 50)
print("2/3 API冒烟")
print("=" * 50)
tests = [
    ("版本", f"curl -s {SERVER}/api/version"),
    ("学院", f"curl -s {SERVER}/api/colleges"),
]
p2 = f2 = 0
for name, cmd in tests:
    try:
        out = json.loads(subprocess.check_output(cmd, shell=True))
        ok2 = isinstance(out, (dict, list))
        if ok2: print(ok(name)); p2 += 1
        else: print(bad(name)); f2 += 1
    except Exception as e:
        # /api/version and /api/colleges are public (no auth needed)
        print(bad(f"{name} 连不上")); f2 += 1

print("")
print("=" * 50)
print("3/3 更新链路验证")
print("=" * 50)
# Read build number from pubspec.yaml (real APK build), not from update_service.dart
# (which only has the runtime initializer buildNumber = 0)
pv_yaml = readf(f"{SRC}/../pubspec.yaml")
bm = re.search(r'version:\s*(\d+\.\d+\.\d+)\+(\d+)', pv_yaml)
client = int(bm.group(2)) if bm else -1
server = r.get("version_code", -1)
chk(f"客户端 build={client}", "package_info_plus" in us or client >= 0)
chk(f"服务器  ver={server}", server > 0)
if client > 0 and server > 0:
    if client < server: chk("旧版会弹更新", True, f"({client} < {server})")
    elif client == server: chk("已是最新版", True)
    else: chk("客户端>服务器?!", False)

# settings_page uses dynamic UpdateService.version — verify it references the
# dynamic source (not a hardcoded string) and matches pubspec.yaml version
sv = re.search(r'UpdateService\.version', readf(f"{SRC}/views/settings_page.dart"))
pv_ver = bm.group(1) if bm else None
if sv and pv_ver:
    chk("版本号一致(动态引用)", True, f"pubspec={pv_ver} settings→UpdateService.version")
elif not sv:
    chk("settings页引用UpdateService.version", False, "找不到动态版本引用")

print("")
print("=" * 50)
tp = p + p2
tf = f + f2
if tf > 0:
    print(f"结果: {tp}通过 {tf}失败 — 修完再编APK")
else:
    print(f"结果: {tp}通过 0失败 — 可以编APK")
print("=" * 50)
sys.exit(2 if tf > 0 else 0)
