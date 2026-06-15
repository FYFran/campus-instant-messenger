import paramiko, time
c=paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("47.82.103.247",username="root",password="ROOT_PASSWORD_CHANGED_20260615",timeout=15,look_for_keys=False,allow_agent=False)

print("Uploading...")
s=c.open_sftp()
s.put("f:/ClaudeFiles/_research/rewriter-go/rewriter-linux","/tmp/rewriter-linux")
s.close()
print("OK")

def r(cmd,t=10):
    stdin,stdout,stderr=c.exec_command(cmd,timeout=t)
    o=stdout.read().decode(errors='replace').strip()
    e=stderr.read().decode(errors='replace').strip()
    if o: print(o)
    if e: print("E:",e)

print("Stop+kill+move+start...")
r("systemctl stop rewriter; fuser -k 9100/tcp 2>/dev/null; sleep 2")
r("mv /tmp/rewriter-linux /app/rewriter-go/rewriter-linux && chown tokenline:tokenline /app/rewriter-go/rewriter-linux")
r("systemctl start rewriter")
time.sleep(3)
print("---")
r("systemctl status rewriter --no-pager | head -8")
r("curl -s https://tokenline.top/api/health")
c.close()
