import paramiko
c=paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("47.82.103.247",username="root",password="ROOT_PASSWORD_CHANGED_20260615",timeout=15,look_for_keys=False,allow_agent=False)
def r(cmd,t=10):
    stdin,stdout,stderr=c.exec_command(cmd,timeout=t)
    o=stdout.read().decode(errors='replace').strip()
    e=stderr.read().decode(errors='replace').strip()
    if o: print(o)
    if e: print("E:",e)

print("=== Check CSP in nginx ===")
r("grep -n 'Content-Security\|add_header' /etc/nginx/sites-enabled/tokenline")

print("\n=== Curl headers ===")
r("curl -skI https://tokenline.top/ 2>&1 | grep -iE 'content-security|x-content|x-frame|referrer|permissions|strict-transport'")

print("\n=== Payment bypass test ===")
r("""curl -sk -w '\nHTTP:%{http_code}' -X POST https://tokenline.top/api/payment/callback -H 'Content-Type: application/json' -d '{"event_type":"payment.succeeded","data":{"metadata":{"invoice_id":"tl-999-999"},"status":"paid"}}'""")

c.close()
