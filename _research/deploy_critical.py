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

print("Upload...")
s=c.open_sftp()
s.put("f:/ClaudeFiles/_research/rewriter-go/rewriter-linux","/tmp/rewriter-linux")
s.close()

print("Add CSP to nginx...")
c.exec_command("sed -i '/add_header Permissions-Policy/i\\    add_header Content-Security-Policy \"default-src \\'self\\'; script-src \\'self\\'; style-src \\'self\\' \\'unsafe-inline\\'; img-src \\'self\\' data:; connect-src \\'self\\'; font-src \\'self\\'; frame-ancestors \\'none\\'; base-uri \\'self\\'; form-action \\'self\\'\" always;' /etc/nginx/sites-enabled/tokenline", timeout=10)
r("nginx -t 2>&1")
r("systemctl reload nginx")

print("Stop+deploy+start...")
r("systemctl stop rewriter; fuser -k 9100/tcp 2>/dev/null; sleep 2")
r("mv /tmp/rewriter-linux /app/rewriter-go/rewriter-linux && chown tokenline:tokenline /app/rewriter-go/rewriter-linux && chmod 755 /app/rewriter-go/rewriter-linux")
r("systemctl start rewriter; sleep 3")
r("systemctl status rewriter --no-pager | head -8")
r("curl -s https://tokenline.top/api/health")

print("\n=== Verify CSP ===")
r("curl -skI https://tokenline.top/ 2>&1 | grep -i content-security")

print("\n=== Verify payment bypass fixed ===")
r("""curl -sk -w '\n%{http_code}' -X POST https://tokenline.top/api/payment/callback -H 'Content-Type: application/json' -d '{"event_type":"payment.succeeded","data":{"metadata":{"invoice_id":"tl-999-999999"},"status":"paid"}}'""")
c.close()
