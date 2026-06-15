import paramiko
c=paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("47.82.103.247",username="root",password="ROOT_PASSWORD_CHANGED_20260615",timeout=15,look_for_keys=False,allow_agent=False)
s=c.open_sftp()
s.put("f:/ClaudeFiles/_research/rewriter-go/rewriter-linux","/tmp/rewriter-linux")
s.close()
def r(cmd,t=10):
    stdin,stdout,stderr=c.exec_command(cmd,timeout=t)
    o=stdout.read().decode(errors='replace').strip()
    if o:print(o)
    e=stderr.read().decode(errors='replace').strip()
    if e:print("E:",e)

r("systemctl stop rewriter; fuser -k 9100/tcp 2>/dev/null; sleep 2; mv /tmp/rewriter-linux /app/rewriter-go/rewriter-linux; chown tokenline:tokenline /app/rewriter-go/rewriter-linux; chmod 755 /app/rewriter-go/rewriter-linux; systemctl start rewriter; sleep 3")
r("systemctl status rewriter --no-pager | head -3")
print("\n=== Enhanced Health ===")
r("curl -s https://tokenline.top/api/health | python3 -m json.tool")
c.close()
