import paramiko
c=paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("47.82.103.247",username="root",password="ROOT_PASSWORD_CHANGED_20260615",timeout=10,look_for_keys=False,allow_agent=False)
s=c.open_sftp()
s.put("f:/ClaudeFiles/_research/compare-v2.html","/app/static/compare.html")
s.close()
def r(cmd,t=10):
    stdin,stdout,stderr=c.exec_command(cmd,timeout=t)
    o=stdout.read().decode(errors='replace').strip()
    if o:print(o)
r("curl -sk -o /dev/null -w 'compare: %{http_code}\n' https://tokenline.top/compare.html")
r("curl -sk -o /dev/null -w 'index: %{http_code}\n' https://tokenline.top/")

# Quick verify pricing in index
r("curl -sk https://tokenline.top/ | grep -o 'Rp [0-9,.]*' | head -10")
c.close()
