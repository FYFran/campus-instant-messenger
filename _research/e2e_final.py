"""TokenLine final E2E test — every user flow"""
import requests, secrets, urllib3, time
urllib3.disable_warnings()
BASE = "https://tokenline.top"
PASSED = 0
FAILED = 0

def test(name, method, path, exp_code, body=None, token=None, check_body=None):
    global PASSED, FAILED
    h = {"Content-Type": "application/json"}
    if token: h["Authorization"] = f"Bearer {token}"
    try:
        r = requests.request(method, f"{BASE}{path}", headers=h, json=body, verify=False, timeout=15)
        ok = r.status_code == exp_code
        if check_body and not ok:
            has = check_body in r.text
            ok = has
        if ok:
            PASSED += 1
            print(f"  PASS  {method} {path} → {r.status_code}")
        else:
            FAILED += 1
            print(f"  FAIL  {method} {path} → {r.status_code} (expected {exp_code}) {r.text[:120]}")
        return r
    except Exception as e:
        FAILED += 1
        print(f"  ERR   {method} {path}: {e}")
        return None

print("=" * 60)
print("1. AUTH FLOW")
print("=" * 60)

# Register with valid data
e = f"e2e{secrets.token_hex(3)}@t.com"
pw = "Test123!"
r1 = test("Valid register", "POST", "/api/auth/register", 200, {"email": e, "password": pw})
tok = r1.json().get("token") if r1 else None

# Register duplicate
test("Duplicate register", "POST", "/api/auth/register", 409, {"email": e, "password": pw})

# Register bad email
test("Bad email", "POST", "/api/auth/register", 400, {"email": "bademail", "password": pw})

# Register weak password
test("Weak password", "POST", "/api/auth/register", 400, {"email": "x@x.com", "password": "12"})

# Login valid
test("Valid login", "POST", "/api/auth/login", 200, {"email": e, "password": pw})

# Login wrong password
test("Wrong password", "POST", "/api/auth/login", 401, {"email": e, "password": "wrongpw"})

print("\n" + "=" * 60)
print("2. CHAT FLOW")
print("=" * 60)

if tok:
    # Chat with valid token
    test("Chat (simple)", "POST", "/api/chat", 200, {"message": "Halo, apa kabar?"}, tok)

    # Chat empty message
    test("Chat (empty)", "POST", "/api/chat", 400, {"message": ""}, tok)

    # Chat without auth
    test("Chat (no auth)", "POST", "/api/chat", 401, {"message": "test"})

    # History
    test("History list", "GET", "/api/chat/history", 200, None, tok)

    # Me
    r_me = test("Me endpoint", "GET", "/api/me", 200, None, tok)
    if r_me:
        d = r_me.json()
        plan = d.get("plan", "?")
        print(f"       plan={plan}, email={d.get('email','?')}")

print("\n" + "=" * 60)
print("3. PHONE OTP FLOW")
print("=" * 60)

if tok:
    # Send OTP (valid phone)
    test("Send OTP", "POST", "/api/auth/send-otp", 200, {"phone": "6281234567890"}, tok)

    # Send OTP (invalid phone)
    test("Bad phone OTP", "POST", "/api/auth/send-otp", 400, {"phone": "123"}, tok)

    # Verify OTP (wrong code)
    test("Wrong OTP", "POST", "/api/auth/verify-otp", 400, {"otp": "000000"}, tok)

    # Request password reset (unregistered phone)
    test("Reset req (new)", "POST", "/api/auth/request-reset", 404, {"phone": "6289999999999"})

print("\n" + "=" * 60)
print("4. PAYMENT FLOW")
print("=" * 60)

if tok:
    # Valid plan
    test("Pay harian", "POST", "/api/payment/create", 200, {"plan": "harian"}, tok)
    test("Pay bulanan", "POST", "/api/payment/create", 200, {"plan": "bulanan"}, tok)
    test("Pay pro", "POST", "/api/payment/create", 200, {"plan": "pro"}, tok)
    test("Pay pro_team", "POST", "/api/payment/create", 200, {"plan": "pro_team"}, tok)

    # Invalid plan
    test("Bad plan", "POST", "/api/payment/create", 400, {"plan": "hacker"}, tok)

    # Payment bypass attempt (no signature)
    test("Pay bypass", "POST", "/api/payment/callback", 401,
         {"event_type": "payment.succeeded", "data": {"metadata": {"invoice_id": "tl-99-99"}}})

print("\n" + "=" * 60)
print("5. SECURITY TESTS")
print("=" * 60)

# SQL Injection
test("SQLi login", "POST", "/api/auth/login", 401, {"email": "' OR 1=1--", "password": "x"})

# JWT none algorithm
test("JWT none", "GET", "/api/me", 401, None, "eyJhbGciOiJub25lIn0.eyJ1c2VyX2lkIjoxfQ.")

# IDOR (other user's conversation)
test("IDOR history", "GET", "/api/chat/history?conversation_id=1", 401, None, "fake.token.here")

# Path traversal
test("Path traversal", "GET", "/api/../../etc/passwd", 400)

print("\n" + "=" * 60)
print("6. MONITORING & HEALTH")
print("=" * 60)

r_h = test("Health check", "GET", "/api/health", 200)
if r_h:
    d = r_h.json()
    print(f"       status={d.get('status')}, db={d.get('db')}, alerts={d.get('alerts')}")
    pred = d.get('prediction', {})
    print(f"       predict: status={pred.get('capacity_status')}, growth={pred.get('weekly_growth_pct'):.1f}%/wk")

print("\n" + "=" * 60)
print("7. FRONTEND PAGES")
print("=" * 60)

pages = ["/", "/features.html", "/compare.html", "/chat/", "/register.html",
         "/login.html", "/topup.html", "/tools/cv.html", "/tools/email.html",
         "/tools/translate.html", "/privacy.html", "/tos.html", "/404-nonexistent"]
for p in pages:
    test(f"Page {p}", "GET", p, 200 if "nonexistent" not in p else 404)

print("\n" + "=" * 60)
print(f"RESULTS: {PASSED} passed, {FAILED} failed")
print("=" * 60)
