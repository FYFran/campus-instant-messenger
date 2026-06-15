import paramiko
c=paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("47.82.103.247",username="root",password="ROOT_PASSWORD_CHANGED_20260615",timeout=10,look_for_keys=False,allow_agent=False)
def r(cmd,t=10):
    stdin,stdout,stderr=c.exec_command(cmd,timeout=t)
    return stdout.read().decode(errors='replace').strip()

print("=== Register + test all plans ===")
out=r("TOK=$(curl -s -X POST http://127.0.0.1:9100/api/auth/register -H 'Content-Type: application/json' -d '{\"email\":\"protest@t.com\",\"password\":\"Test123!\"}' | python3 -c 'import sys,json; print(json.load(sys.stdin).get(\"token\",\"\"))' 2>/dev/null); echo TOK=${TOK:0:20}...; for plan in harian mingguan  bulanan pro pro_team pro_enterprise tahunan; do curl -s -w '\n' -X POST http://127.0.0.1:9100/api/payment/create -H 'Content-Type: application/json' -H \"Authorization: Bearer $TOK\" -d \"{\\\"plan\\\":\\\"$plan\\\"}\" | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get(\"plan\",\"?\"),\"amount:\",d.get(\"amount\",0),\"status:\",d.get(\"status\",d.get(\"message\",\"?\")))' 2>/dev/null; done")
print(out)
c.close()
