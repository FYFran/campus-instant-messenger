"""跨后端一致�?�?SSH到服务器对比Python(9500) vs Go(9501)
用法: python test_cross_backend.py
"""

import paramiko, os, json, urllib.request

PASS = 0; FAIL = 0

def _ssh_test():
    global PASS, FAIL
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect('139.196.50.134', username='root',
              password=os.environ.get('SSH_PASSWORD','ROOT_PASSWORD_CHANGED_20260615'),
              timeout=20, look_for_keys=False, allow_agent=False)

    script = '''
import urllib.request, json

PY = "http://127.0.0.1:9500"
GO = "http://127.0.0.1:9501"
results = []

def req(base, method, path, data=None, token=None):
    h = {"Content-Type": "application/json"}
    if token: h["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode() if data else None
    r = urllib.request.Request(base+path, data=body, headers=h, method=method)
    try:
        resp = urllib.request.urlopen(r, timeout=8)
        return resp.status, json.loads(resp.read())
    except Exception as e:
        return 0, {"error": str(e)}

# Public
for name, method, path, data in [
    ("version", "GET", "/api/version", None),
    ("colleges", "GET", "/api/colleges", None),
]:
    sp, dp = req(PY, method, path, data)
    sg, dg = req(GO, method, path, data)
    ok = sp == 200 and sg == 200
    results.append((name, ok, f"PY={sp} GO={sg}"))
    if ok and "version" in name:
        match = dp.get("version") == dg.get("version")
        results.append(("version_value", match, f"PY={dp.get('version')} GO={dg.get('version')}"))
    if ok and "colleges" in name:
        match = len(dp) == len(dg)
        results.append(("colleges_count", match, f"PY={len(dp)} GO={len(dg)}"))

# Auth
sp, dp = req(PY, "POST", "/api/login", {"student_id":"10000","password":"10000"})
sg, dg = req(GO, "POST", "/api/login", {"student_id":"10000","password":"10000"})
ok = sp == 200 and sg == 200
results.append(("login", ok, f"PY={sp} GO={sg}"))
if ok:
    py_tok = dp.get("token","")
    go_tok = dg.get("token","")
    for field in ["id","role","name"]:
        match = dp["user"].get(field) == dg["user"].get(field)
        results.append((f"login_user_{field}", match, f"PY={dp['user'].get(field)} GO={dg['user'].get(field)}"))

    # Auth endpoints
    for name, method, path in [
        ("me", "GET", "/api/me"),
        ("activities", "GET", "/api/activities?limit=3"),
        ("notifications", "GET", "/api/notifications?limit=5"),
        ("my_signups", "GET", "/api/my-signups"),
    ]:
        sp, dp = req(PY, method, path, token=py_tok)
        sg, dg = req(GO, method, path, token=go_tok)
        ok = sp == 200 and sg == 200
        results.append((name, ok, f"PY={sp} GO={sg}"))

# Wrong password
sp, dp = req(PY, "POST", "/api/login", {"student_id":"10000","password":"wrong"})
sg, dg = req(GO, "POST", "/api/login", {"student_id":"10000","password":"wrong"})
ok = (sp in (401,403)) and (sg in (401,403))
results.append(("wrong_pw", ok, f"PY={sp} GO={sg}"))

for name, ok, detail in results:
    print(f"RESULT:{name}:{'PASS' if ok else 'FAIL'}:{detail}")
'''

    stdin, stdout, stderr = c.exec_command(f'python3 -c "{script}"', timeout=30)
    out = stdout.read().decode()
    err = stderr.read().decode()
    c.close()

    for line in out.split('\n'):
        if line.startswith('RESULT:'):
            parts = line.split(':', 3)
            name, status, detail = parts[1], parts[2], parts[3]
            if status == 'PASS':
                PASS += 1
                print(f"  [OK] {name}")
            else:
                FAIL += 1
                print(f"  [FAIL] {name} �?{detail}")
    if err and 'ERROR' in err:
        print(f"  ERR: {err[:200]}")

print(f"\n{'='*50}")
print(f"  Cross-Backend Consistency")
_ssh_test()
total = PASS + FAIL
if FAIL == 0:
    print(f"  RESULT: ALL {PASS} PASSED")
else:
    print(f"  PASS: {PASS}  |  FAIL: {FAIL}")
print(f"{'='*50}")
