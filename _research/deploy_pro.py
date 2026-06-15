import paramiko,time
c=paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("47.82.103.247",username="root",password="ROOT_PASSWORD_CHANGED_20260615",timeout=15,look_for_keys=False,allow_agent=False)
def r(cmd,t=10):
    stdin,stdout,stderr=c.exec_command(cmd,timeout=t)
    o=stdout.read().decode(errors='replace').strip()
    e=stderr.read().decode(errors='replace').strip()
    if o:print(o)
    if e:print("E:",e)

# Upload binary
s=c.open_sftp()
s.put("f:/ClaudeFiles/_research/rewriter-go/rewriter-linux","/tmp/rewriter-linux")
s.close()

# Update landing page pricing
r("sed -i 's/Rp 129.000/Rp 249.000/g; s/Pro Bulanan/Pro Individu/g' /app/static/index.html")
r("sed -i 's/Model paling cangguh/Model V4 Pro Unlimited. 500 pesan\\/hari. Prioritas support. Untuk profesional dan tim./g' /app/static/index.html")

# Deploy
r("systemctl stop rewriter; fuser -k 9100/tcp 2>/dev/null; sleep 2")
r("mv /tmp/rewriter-linux /app/rewriter-go/rewriter-linux && chown tokenline:tokenline /app/rewriter-go/rewriter-linux && chmod 755 /app/rewriter-go/rewriter-linux")
r("systemctl start rewriter; sleep 3")

print("---")
r("systemctl status rewriter --no-pager | head -5")
r("curl -s https://tokenline.top/api/health")

# Test new plan
print("\n=== New Pro pricing test ===")
r("curl -s -w '\nHTTP:%{http_code}' -X POST http://127.0.0.1:9100/api/payment/create -H 'Content-Type: application/json' -d '{\"plan\":\"pro\"}'")
print("---")
r("curl -s -w '\nHTTP:%{http_code}' -X POST http://127.0.0.1:9100/api/payment/create -H 'Content-Type: application/json' -d '{\"plan\":\"pro_team\"}'")
print("---")
r("curl -s -w '\nHTTP:%{http_code}' -X POST http://127.0.0.1:9100/api/payment/create -H 'Content-Type: application/json' -d '{\"plan\":\"pro_enterprise\"}'")
c.close()
