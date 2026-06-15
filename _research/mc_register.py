"""Complete Message Central registration from HK server"""
import paramiko, base64

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("47.82.103.247", username="root", password="ROOT_PASSWORD_CHANGED_20260615", timeout=15, look_for_keys=False, allow_agent=False)

def run(cmd, t=15):
    stdin, stdout, stderr = c.exec_command(cmd, timeout=t)
    out = stdout.read().decode(errors='replace').strip()
    err = stderr.read().decode(errors='replace').strip()
    print(out[:600] if out else "(empty)")
    if err: print("ERR:", err[:300])
    return out

email = "3170474192@qq.com"
password = "ROOT_PASSWORD_CHANGED_20260615"
phone = "+8618896691078"
pwd_b64 = base64.b64encode(password.encode()).decode()

# 1. Check if we can get a token using email as customerId
print("=== Auth with email ===")
run(f'curl -s "https://cpaas.messagecentral.com/auth/v1/authentication/token?customerId={email}&key={pwd_b64}&scope=NEW&email={email}"')

# 2. Try phone verification - send OTP to 18896691078
print("\n=== Send OTP via VerifyNow ===")
run(f'curl -s -X POST "https://api.messagecentral.com/verify/send" -H "Content-Type: application/json" -d \'{{"phone_number":"{phone}","channel":"sms"}}\'')

# 3. Try the old V3 endpoint with email-based auth
print("\n=== V3 Send OTP ===")
run(f'curl -s "https://cpaas.messagecentral.com/verification/v3/send?countryCode=86&flowType=SMS&mobileNumber=18896691078" -H "accept: */*"')

# 4. Check if the user's account exists by trying forgot password
print("\n=== Forgot password check ===")
run(f'curl -s -X POST "https://www.messagecentral.com/api/forgot-password" -H "Content-Type: application/json" -d \'{{"email":"{email}"}}\'')

# 5. Try signup API directly
print("\n=== Direct signup ===")
run(f'curl -s -X POST "https://api.messagecentral.com/auth/signup" -H "Content-Type: application/json" -d \'{{"email":"{email}","password":"{password}","name":"TokenLine Admin","company":"TokenLine","phone":"{phone}"}}\'')

c.close()
