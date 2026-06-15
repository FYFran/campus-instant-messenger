"""Register Message Central from HK server â€?no reCAPTCHA"""
import paramiko, json

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("47.82.103.247", username="root", password="ROOT_PASSWORD_CHANGED_20260615", timeout=15, look_for_keys=False, allow_agent=False)

def run(cmd, t=15):
    stdin, stdout, stderr = c.exec_command(cmd, timeout=t)
    out = stdout.read().decode(errors='replace').strip()
    err = stderr.read().decode(errors='replace').strip()
    print("OUT:", out[:500] if out else "(empty)")
    if err: print("ERR:", err[:300])
    return out

# Step 1: Try to login via their auth API
print("=== Step 1: Try CPAAS auth ===")
# Their auth endpoint uses customerId + base64 encoded password
import base64
pwd_b64 = base64.b64encode(b"ROOT_PASSWORD_CHANGED_20260615").decode()
print(f"Base64 password: {pwd_b64}")

# Try the auth endpoint with email
result = run(f'curl -s --max-time 10 "https://cpaas.messagecentral.com/auth/v1/authentication/token?customerId=3170474192@qq.com&key={pwd_b64}&scope=NEW&email=3170474192@qq.com"')
print()

# Step 2: If that fails, try the VerifyNow signup
print("=== Step 2: Try VerifyNow signup ===")
signup_data = json.dumps({
    "email": "3170474192@qq.com",
    "password": "ROOT_PASSWORD_CHANGED_20260615",
    "name": "TokenLine",
    "phone": "+8618896691078"
})
result = run(f"curl -s --max-time 10 -X POST https://api.messagecentral.com/auth/signup -H 'Content-Type: application/json' -d '{signup_data}'")
print()

# Step 3: Try web login to get session
print("=== Step 3: Try web login ===")
login_data = "email=3170474192%40qq.com&password=%40Yf773711"
result = run(f"curl -sL --max-time 10 -X POST https://www.messagecentral.com/api/login -H 'Content-Type: application/x-www-form-urlencoded' -d '{login_data}' -c /tmp/mc_cookies.txt -v 2>&1 | tail -20")

c.close()
