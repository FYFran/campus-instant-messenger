import paramiko, time
c=paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("47.82.103.247",username="root",password="ROOT_PASSWORD_CHANGED_20260615",timeout=15,look_for_keys=False,allow_agent=False)
def r(cmd,t=10):
    stdin,stdout,stderr=c.exec_command(cmd,timeout=t)
    o=stdout.read().decode(errors='replace').strip()
    e=stderr.read().decode(errors='replace').strip()
    if o: print(o)
    if e: print("E:",e)

print("=== Check binary ===")
r("file /app/rewriter-go/rewriter-linux")
r("ls -la /app/rewriter-go/rewriter-linux")
r("md5sum /app/rewriter-go/rewriter-linux")

print("\n=== Fix + restart ===")
r("chmod 755 /app/rewriter-go/rewriter-linux; chown tokenline:tokenline /app/rewriter-go/rewriter-linux")
r("systemctl stop rewriter; fuser -k 9100/tcp 2>/dev/null; sleep 1")
r("systemctl start rewriter; sleep 3")
r("systemctl status rewriter --no-pager | head -10")

print("\n=== Health ===")
r("curl -s https://tokenline.top/api/health")
c.close()
