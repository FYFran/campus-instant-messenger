import paramiko
c=paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("47.82.103.247",username="root",password="ROOT_PASSWORD_CHANGED_20260615",timeout=10,look_for_keys=False,allow_agent=False)
s=c.open_sftp()
s.put("f:/ClaudeFiles/_research/refund.html","/app/static/refund.html")
s.put("f:/ClaudeFiles/_research/register.html","/app/static/register.html")
s.close()
def r(cmd,t=10):
    stdin,stdout,stderr=c.exec_command(cmd,timeout=t)
    o=stdout.read().decode(errors='replace').strip()
    if o:print(o)

# Add refund badge to landing page hero section
r("sed -i '/Garansi 7 Hari/a\\    <div class=\"trust-item\"><span class=\"trust-dot\"></span><a href=\"/refund.html\" style=\"color:var(--green);font-weight:600\">Token Sisa Selalu Bisa Di-refund</a></div>' /app/static/index.html")

# Verify
for p in ["/refund.html","/register.html","/"]:
    r(f"curl -sk -o /dev/null -w '{p}: %{{http_code}}\n' https://tokenline.top{p}")

# Check checkbox on register page
r("curl -sk https://tokenline.top/register.html | grep -o 'Syarat & Ketentuan' | head -1")
r("curl -sk https://tokenline.top/register.html | grep -o 'agree' | head -1")
c.close()
