#!/usr/bin/env python3
"""TokenLine smoke test — quick verification of all critical endpoints."""
import urllib.request, json, sys, time, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE = "https://tokenline.top"
FAIL = 0
OK = 0

def test(name, method, path, body=None, want_status=200, token=None):
    global OK, FAIL
    url = BASE + path
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        status = resp.status
        if status == want_status:
            OK += 1
            print(f"  ✅ {name}: {status}")
        else:
            FAIL += 1
            print(f"  ❌ {name}: expected {want_status}, got {status}")
    except urllib.error.HTTPError as e:
        if e.code == want_status:
            OK += 1
            print(f"  ✅ {name}: {e.code} (expected)")
        else:
            FAIL += 1
            print(f"  ❌ {name}: expected {want_status}, got {e.code}")
    except Exception as e:
        FAIL += 1
        print(f"  ❌ {name}: {e}")

print("=== TokenLine Smoke Test ===")
print()

# 1. Public pages
print("--- Pages ---")
for page, name in [("/", "Home"), ("/login.html", "Login"), ("/register.html", "Register"),
    ("/topup.html", "Topup"), ("/chat/", "Chat"), ("/about.html", "About"),
    ("/docs.html", "Docs"), ("/privacy.html", "Privacy"), ("/tos.html", "TOS")]:
    test(name, "GET", page)

# 2. Health
print("\n--- Health ---")
test("Health API", "GET", "/api/health")

# 3. Auth
print("\n--- Auth ---")
email = f"smoke_{int(time.time())}@test.com"
pw = "test123456"
test("Register", "POST", "/api/auth/register", {"email": email, "password": pw})
test("Register duplicate", "POST", "/api/auth/register", {"email": email, "password": pw}, want_status=409)
test("Login", "POST", "/api/auth/login", {"email": email, "password": pw})
test("Login bad pw", "POST", "/api/auth/login", {"email": email, "password": "wrong!!!"}, want_status=401)

# Get token for protected tests
req = urllib.request.Request(BASE + "/api/auth/login",
    data=json.dumps({"email": email, "password": pw}).encode(),
    headers={"Content-Type": "application/json"}, method="POST")
try:
    resp = urllib.request.urlopen(req, timeout=10)
    token = json.loads(resp.read()).get("token", "")
except:
    token = ""

# 4. Protected endpoints
print("\n--- Protected ---")
test("Get me", "GET", "/api/me", token=token)
test("Get balance", "GET", "/api/me/balance", token=token)
test("Send OTP", "POST", "/api/auth/send-otp", {"phone": "628123456789"}, token=token)
test("Verify OTP wrong", "POST", "/api/auth/verify-otp", {"otp": "000000"}, token=token, want_status=400)
test("Change password", "POST", "/api/auth/change-password", {"old_password": pw, "new_password": pw}, token=token)
test("Chat Flash", "POST", "/api/chat", {"message": "Halo", "model": "deepseek-v4-flash"}, token=token)
test("Get packs", "GET", "/api/packs")

# 5. Security
print("\n--- Security ---")
test("CORS good origin", "GET", "/api/health", token=None)  # already tested
test("Noauth protect", "GET", "/api/me", token=None, want_status=401)
test("Bad JWT", "GET", "/api/me", token="invalid.jwt.token", want_status=401)

print(f"\n{'='*40}")
print(f"Results: {OK} passed, {FAIL} failed, {OK+FAIL} total")
if FAIL:
    print("❌ SOME TESTS FAILED")
    sys.exit(1)
else:
    print("✅ ALL TESTS PASSED")
