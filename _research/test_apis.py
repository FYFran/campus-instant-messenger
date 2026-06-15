import paramiko
c=paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("47.82.103.247",username="root",password="ROOT_PASSWORD_CHANGED_20260615",timeout=10,look_for_keys=False,allow_agent=False)
def r(cmd,t=10):
    stdin,stdout,stderr=c.exec_command(cmd,timeout=t)
    return stdout.read().decode(errors='replace').strip()

tests = [
    ('POST /api/auth/register', '-d \'{"email":"test@t.com","password":"Test123!"}\''),
    ('POST /api/auth/request-reset', '-d \'{"phone":"6281234567890"}\''),
    ('POST /api/auth/reset-password', '-d \'{"phone":"6281234567890","otp":"123456","new_password":"Test123!"}\''),
]
for name, data in tests:
    cmd = f"curl -sk -o /dev/null -w '%{{http_code}}' {data} https://tokenline.top{name}"
    out = r(cmd)
    print(f"  {out}  {name}")

print("\n=== Logs ===")
print(r("journalctl -u rewriter --no-pager -n 3 2>&1"))
c.close()
