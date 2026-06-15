"""Find working OTP SMS provider from HK server"""
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("47.82.103.247", username="root", password="ROOT_PASSWORD_CHANGED_20260615", timeout=15, look_for_keys=False, allow_agent=False)

def run(cmd, t=10):
    stdin, stdout, stderr = c.exec_command(cmd, timeout=t)
    return stdout.read().decode(errors='replace').strip()

# Check Message Central's actual signup flow
print("=== Message Central ===")
print(run("curl -sL --max-time 5 -o /dev/null -w '%{http_code}' https://www.messagecentral.com/pricing"))
print(run("curl -sL --max-time 5 -o /dev/null -w '%{http_code}' https://www.messagecentral.com/contact-sales"))

# Check if VerifyNow API is accessible (this is what we actually need)
print("\n=== VerifyNow API test ===")
print(run('curl -s --max-time 5 -X POST https://api.messagecentral.com/verify/send -H "Content-Type: application/json" -d \'{"phone_number":"+628123456789","channel":"sms"}\''))

# Check Twilio
print("\n=== Twilio ===")
print(run("curl -sL --max-time 5 -o /dev/null -w '%{http_code}' https://www.twilio.com/signup"))

# Check Brevo (email relay as fallback)
print("\n=== Brevo ===")
print(run("curl -sL --max-time 5 -o /dev/null -w '%{http_code}' https://www.brevo.com/"))
print(run("curl -sL --max-time 5 -o /dev/null -w '%{http_code}' https://app.brevo.com/"))

c.close()
