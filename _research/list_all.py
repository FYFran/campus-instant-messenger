import paramiko
c=paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("47.82.103.247",username="root",password="ROOT_PASSWORD_CHANGED_20260615",timeout=10,look_for_keys=False,allow_agent=False)
def r(cmd,t=8):
    stdin,stdout,stderr=c.exec_command(cmd,timeout=t)
    return stdout.read().decode(errors='replace')

print("=== ALL DEPLOYED FILES ===")
print(r("find /app/static -type f | sort"))

print("\n=== FILE SIZES ===")
print(r("find /app/static -type f -exec ls -la {} \\; | awk '{print $5,$NF}'"))

print("\n=== PAGES WITH TITLES ===")
for f in r("ls /app/static/*.html /app/static/chat/*.html /app/static/tools/*.html 2>/dev/null").split():
    title = r(f"grep '<title>' {f} 2>/dev/null | head -1").strip()
    print(f"  {f.split('/')[-1]:30s} {title[:80]}")

print("\n=== GO ENDPOINTS ===")
print(r("grep -n 'HandleFunc\|Handle(' /app/rewriter-go/main.go"))

print("\n=== PLANS IN CODE ===")
print(r("grep 'plan\|harian\|bulanan\|premium\|tahunan\|gratis' /app/rewriter-go/internal/handler/pay.go | head -20"))

c.close()
