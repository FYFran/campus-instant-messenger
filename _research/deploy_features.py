import paramiko
c=paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("47.82.103.247",username="root",password="ROOT_PASSWORD_CHANGED_20260615",timeout=10,look_for_keys=False,allow_agent=False)
s=c.open_sftp()
s.put("f:/ClaudeFiles/_research/features.html","/app/static/features.html")
s.close()
def r(cmd,t=10):
    stdin,stdout,stderr=c.exec_command(cmd,timeout=t)
    o=stdout.read().decode(errors='replace').strip()
    e=stderr.read().decode(errors='replace').strip()
    if o:print(o)
    if e:print("E:",e)

r("curl -sk -o /dev/null -w 'features: %{http_code}\n' https://tokenline.top/features.html")

print("\n=== Final site audit ===")
pages=["/","/features.html","/chat/","/register.html","/login.html","/topup.html","/privacy.html","/tos.html","/tools/cv.html","/tools/academic.html","/tools/social.html","/tools/email.html","/tools/translate.html","/docs.html","/api/health"]
for p in pages:
    r(f"curl -sk -o /dev/null -w '{p}: %{{http_code}}\n' https://tokenline.top{p}")

print("\n=== API endpoints ===")
apis=["/api/auth/register","/api/auth/login","/api/auth/request-reset","/api/auth/reset-password","/api/me","/api/chat"]
for a in apis:
    r(f"curl -sk -o /dev/null -w '{a}: %{{http_code}}\n' https://tokenline.top{a}")

print("\n=== Security headers ===")
r("curl -skI https://tokenline.top/ 2>&1 | grep -iE 'content-security|x-frame|x-content|strict-transport'")

print("\n=== rewriter status ===")
r("systemctl status rewriter --no-pager | head -5")
c.close()
