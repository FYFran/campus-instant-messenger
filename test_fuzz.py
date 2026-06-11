"""API Fuzz 测试 — 随机边界输入验证
用法: python test_fuzz.py

原则:
  - 所有端点不接受随机输入导致500
  - 401/404/422/400 都是合法响应
  - 500/崩溃/非JSON响应 = 失败
  - 只测公开端点(不需要有效token)
"""

import urllib.request, urllib.error, json, sys, time, random, string

BASE = "http://139.196.50.134"
PASS = 0
FAIL = 0

def _rand_str(min_len=0, max_len=200):
    chars = string.ascii_letters + string.digits + "!@#$%^&*(){}[]|\\:;\"'<>,.?/~`  \n\t\r\0"
    length = random.randint(min_len, max_len)
    return ''.join(random.choice(chars) for _ in range(length))

def _rand_int():
    return random.choice([-1, 0, 1, 999999999, -999999999, 2**31-1, -(2**31)])

def _rand_json():
    return {
        "student_id": _rand_str(0, 50),
        "password": _rand_str(0, 100),
        "name": _rand_str(0, 500),
        "college": _rand_str(0, 200),
        "phone": _rand_str(0, 30),
        "role": _rand_str(0, 20),
        "nested": {"deep": _rand_str(0, 1000)},
        "array": [_rand_str(0, 50) for _ in range(random.randint(0, 5))],
        "number": _rand_int(),
        "bool": random.choice([True, False, "not_bool", None, 0, 1, [], {}]),
    }

# 公开端点列表 — (method, path, body_generator)
ENDPOINTS = [
    ("GET", "/api/version", None),
    ("GET", "/api/health", None),
    ("GET", "/api/colleges", None),
    ("POST", "/api/login", lambda: {"student_id": _rand_str(0, 50), "password": _rand_str(0, 100)}),
    ("POST", "/api/register", lambda: _rand_json()),
    ("POST", "/api/token/refresh", lambda: {"refresh_token": _rand_str(0, 200)}),
    ("POST", "/api/auth/reset-password", lambda: {"name": _rand_str(0, 100), "phone": _rand_str(0, 30), "student_id": _rand_str(0, 50)}),
    # 路径参数 fuzz — 用随机ID
    ("GET", f"/api/activities/{_rand_int()}", None),
    ("GET", f"/api/notices/{_rand_int()}", None),
    # 带无效token的受保护端点
    ("GET", "/api/me", None),  # no auth → 401 expected
    ("GET", "/api/activities", None),  # no auth → 401 expected
]

def fuzz(method, path, body_gen, iterations=5):
    global PASS, FAIL
    for i in range(iterations):
        data = body_gen() if body_gen else None
        if path == "/api/activities/{_rand_int()}" or path == "/api/notices/{_rand_int()}":
            p = f"/api/activities/{random.randint(-999, 999999)}" if "activities" in path else f"/api/notices/{random.randint(-999, 999999)}"
        else:
            p = path

        body = json.dumps(data).encode() if data else None
        req = urllib.request.Request(f"{BASE}{p}", data=body,
            headers={"Content-Type": "application/json"}, method=method)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = resp.read()
                try:
                    json.loads(raw)
                except:
                    FAIL += 1
                    print(f"  [FAIL] {method} {p}: non-JSON response (status={resp.status})")
                    continue
                if resp.status >= 500:
                    FAIL += 1
                    print(f"  [FAIL] {method} {p}: 5xx={resp.status} body={raw[:100]}")
                    continue
                PASS += 1
        except urllib.error.HTTPError as e:
            raw = e.read()
            try: json.loads(raw)
            except:
                FAIL += 1
                print(f"  [FAIL] {method} {p}: non-JSON error body (status={e.code})")
                continue
            if e.code >= 500:
                FAIL += 1
                print(f"  [FAIL] {method} {p}: 5xx={e.code} body={raw[:100]}")
                continue
            PASS += 1  # 4xx is OK
        except Exception as e:
            FAIL += 1
            print(f"  [FAIL] {method} {p}: connection error: {e}")

print(f"\n{'='*50}")
print(f"  API Fuzz Test — {BASE}")
print(f"  {len(ENDPOINTS)} endpoints x 5 iterations each")
print(f"{'='*50}\n")

for method, path, gen in ENDPOINTS:
    fuzz(method, path, gen, 5)

total = PASS + FAIL
print(f"\n{'='*50}")
if FAIL == 0:
    print(f"  RESULT: ALL {total} PASSED — 无500/崩溃/非JSON")
else:
    print(f"  PASS: {PASS}  |  FAIL: {FAIL}")
    print(f"  RESULT: {FAIL} FAILURES")
print(f"{'='*50}\n")
sys.exit(0 if FAIL == 0 else 1)
