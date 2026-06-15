"""Check production frontend files for secrets"""
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("47.82.103.247", username="root", password="ROOT_PASSWORD_CHANGED_20260615", timeout=15, look_for_keys=False, allow_agent=False)

def run(cmd, t=10):
    stdin, stdout, stderr = c.exec_command(cmd, timeout=t)
    return stdout.read().decode(errors='replace')

print("=== Production frontend files ===")
print(run("ls -la /app/static/"))
print(run("ls -la /app/static/chat/"))

print("\n=== Scan for secrets in production files ===")
print(run("grep -rn 'sk-\|Dx2k\|whsec\|eyJ\|api[_-]key\|secret\|password\s*=' /app/static/*.html /app/static/chat/*.html 2>/dev/null | grep -v 'placeholder\|type=.password\|hidden\|<!--'"))

print("\n=== Check /app/static/chat/index.html for secrets ===")
out = run("cat /app/static/chat/index.html 2>/dev/null")
# Only show sensitive lines
for line in out.split('\n'):
    low = line.lower()
    if any(x in low for x in ['sk-', 'api_key', 'apikey', 'secret', 'token', 'Dx2k', 'whsec', 'eyJhbG']):
        print(f"  FOUND: {line.strip()[:120]}")

print("\n=== Check /app/static/index.html for secrets ===")
out = run("cat /app/static/index.html 2>/dev/null")
for line in out.split('\n'):
    low = line.lower()
    if any(x in low for x in ['sk-', 'api_key', 'apikey', 'secret', 'Dx2k', 'whsec']):
        print(f"  FOUND: {line.strip()[:120]}")

c.close()
