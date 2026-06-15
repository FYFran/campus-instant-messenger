"""Bug hunt: test for authorization and edge cases"""
import paramiko, requests, json, secrets

# Suppress SSL warnings for local testing
import urllib3
urllib3.disable_warnings()

BASE = "https://tokenline.top"

def test(name, method, path, expected_code, body=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        if method == "GET":
            r = requests.get(f"{BASE}{path}", headers=headers, verify=False, timeout=10)
        else:
            r = requests.post(f"{BASE}{path}", headers=headers, json=body, verify=False, timeout=10)
        ok = r.status_code == expected_code
        mark = "OK" if ok else f"FAIL (expected {expected_code}, got {r.status_code})"
        print(f"  [{mark}] {method} {path}")
        if not ok:
            print(f"         Response: {r.text[:200]}")
        return r
    except Exception as e:
        print(f"  [ERR] {method} {path}: {e}")
        return None

# Register two users
e1 = f"bugtest1{secrets.token_hex(2)}@t.com"
e2 = f"bugtest2{secrets.token_hex(2)}@t.com"

print("=== Setup: register two users ===")
r1 = test("register1", "POST", "/api/auth/register", 200, {"email": e1, "password": "Test123!"})
r2 = test("register2", "POST", "/api/auth/register", 200, {"email": e2, "password": "Test123!"})
t1 = r1.json().get("token") if r1 else None
t2 = r2.json().get("token") if r2 else None
uid1 = r1.json().get("user",{}).get("id") if r1 else None
uid2 = r2.json().get("user",{}).get("id") if r2 else None
print(f"  User1: {uid1}, User2: {uid2}")

print("\n=== BUG 1: IDOR â€?read another user's conversations ===")
# User1 creates a conversation
test("chat_as_u1", "POST", "/api/chat", 200,
     {"message": "Rahasia user 1: password saya adalah hunter2"}, t1)
# User2 tries to read it â€?conversations are sequential, try id=1
test("u2_reads_u1_history", "GET", "/api/chat/history?conversation_id=1", 200, None, t2)
# This should return 403/404, not 200 with content

print("\n=== BUG 2: X-Forwarded-For spoofing ===")
for i in range(5):
    headers = {"Content-Type": "application/json", "X-Forwarded-For": f"169.254.{i}.1"}
    r = requests.post(f"{BASE}/api/auth/register", headers=headers,
                      json={"email": f"spam{i}{secrets.token_hex(2)}@t.com", "password": "Test123!"},
                      verify=False, timeout=10)
    if r.status_code == 429:
        print(f"  Rate limit works on spoofed IP {i}")
    else:
        print(f"  [BYPASS] Spoofed IP {i}: {r.status_code}")

print("\n=== BUG 3: Chat message byte vs character length ===")
emoji_msg = "a" * 2001 + "ðŸ˜€ðŸ˜€ðŸ˜€"  # 2001 bytes + 12 bytes emoji
if t1:
    test("byte_vs_char", "POST", "/api/chat", 200, {"message": emoji_msg}, t1)
    # If it returns 200, byte check passed but character count is wrong

print("\n=== BUG 4: Payment create with invalid plan ===")
if t1:
    test("bad_plan", "POST", "/api/payment/create", 400,
         {"plan": "hackerman"}, t1)

print("\n=== BUG 5: Register with fake email ===")
test("bad_email1", "POST", "/api/auth/register", 400,
     {"email": "notanemail", "password": "Test123!"})
test("bad_email2", "POST", "/api/auth/register", 400,
     {"email": "", "password": "Test123!"})

print("\n=== BUG 6: Chat without auth ===")
test("no_auth_chat", "POST", "/api/chat", 401,
     {"message": "hello"})

print("\n=== BUG 7: Register with very long email ===")
test("long_email", "POST", "/api/auth/register", 400,
     {"email": "a" * 200 + "@b.com", "password": "Test123!"})

print("\n=== BUG 8: Duplicate register ===")
test("dup_register", "POST", "/api/auth/register", 409,
     {"email": e1, "password": "Test123!"})

print("\n=== Server: check rewriter status ===")
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect("47.82.103.247", username="root", password="ROOT_PASSWORD_CHANGED_20260615", timeout=10, look_for_keys=False, allow_agent=False)
stdin, stdout, stderr = client.exec_command("systemctl status rewriter --no-pager | head -8; echo '---'; docker ps --format '{{.Names}} {{.Status}}'")
print(stdout.read().decode())
client.close()
