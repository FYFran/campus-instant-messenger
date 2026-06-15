import paramiko
c=paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("47.82.103.247",username="root",password="ROOT_PASSWORD_CHANGED_20260615",timeout=10,look_for_keys=False,allow_agent=False)
def r(cmd,t=15):
    stdin,stdout,stderr=c.exec_command(cmd,timeout=t)
    return stdout.read().decode(errors='replace').strip()

# Test directly against localhost
print("=== Direct to rewriter (localhost:9100) ===")
print(r("curl -s -w '\nHTTP:%{http_code}' -X POST http://127.0.0.1:9100/api/auth/request-reset -H 'Content-Type: application/json' -d '{\"phone\":\"6281234567890\"}'"))
print("---")
print(r("curl -s -w '\nHTTP:%{http_code}' -X POST http://127.0.0.1:9100/api/auth/reset-password -H 'Content-Type: application/json' -d '{\"phone\":\"6281234567890\",\"otp\":\"123456\",\"new_password\":\"Test1234\"}'"))
print("---")
print(r("curl -s -w '\nHTTP:%{http_code}' -X POST http://127.0.0.1:9100/api/auth/register -H 'Content-Type: application/json' -d '{\"email\":\"livechk@t.com\",\"password\":\"Test123!\"}'"))

print("\n=== Via nginx ===")
print(r("curl -sk -w '\nHTTP:%{http_code}' -X POST https://tokenline.top/api/auth/request-reset -H 'Content-Type: application/json' -d '{\"phone\":\"6281234567890\"}'"))
c.close()
