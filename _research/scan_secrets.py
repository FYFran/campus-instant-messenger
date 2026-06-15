"""Simple secret scan of production files"""
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("47.82.103.247", username="root", password="ROOT_PASSWORD_CHANGED_20260615", timeout=15, look_for_keys=False, allow_agent=False)

def run(cmd, t=10):
    stdin, stdout, stderr = c.exec_command(cmd, timeout=t)
    return stdout.read().decode(errors='replace')

# Check key files for hardcoded secrets
files = [
    "/app/static/index.html",
    "/app/static/chat/index.html",
    "/app/static/login.html",
    "/app/static/register.html",
    "/app/static/topup.html",
    "/app/static/dashboard.html",
]

for f in files:
    content = run(f"cat {f} 2>/dev/null")
    if not content:
        continue
    for i, line in enumerate(content.split('\n'), 1):
        low = line.lower()
        if any(x in low for x in ['sk-bl', 'sk-BL', 'Dx2k', 'whsec', 'api_key', 'apikey']):
            # Mask the secret
            safe = line.strip()[:80]
            print(f"SECRET in {f}:{i}: {safe}...")

print("\n=== Also check .env files exposed via web ===")
# These are probe attempts we saw in nginx logs
for path in ["/.env", "/.git/config", "/wp-admin", "/admin/.env", "/backup"]:
    out = run(f"curl -sk -o /dev/null -w '%{{http_code}}' https://tokenline.top{path}")
    print(f"  {path}: {out.strip()}")

print("\n=== Check robots.txt and sitemap ===")
print(run("cat /app/static/robots.txt"))
print(run("cat /app/static/sitemap.xml"))

c.close()
