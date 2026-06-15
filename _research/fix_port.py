"""Fix port conflict and restart"""
import paramiko, time

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect("47.82.103.247", username="root", password="ROOT_PASSWORD_CHANGED_20260615", timeout=15, look_for_keys=False, allow_agent=False)

def run(cmd, timeout=10):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors='replace').strip()
    err = stderr.read().decode(errors='replace').strip()
    if out: print(out)
    if err: print("ERR:", err)

print("=== Kill everything on port 9100 ===")
run("fuser -k 9100/tcp 2>/dev/null; sleep 2; echo done")

print("\n=== Verify port free ===")
run("ss -tlnp | grep 9100 || echo 'port 9100 free'")

print("\n=== Start service ===")
run("systemctl start rewriter")
time.sleep(3)

print("\n=== Status ===")
run("systemctl status rewriter --no-pager | head -12")

print("\n=== Verify ===")
run("curl -s https://tokenline.top/api/health")
run("ss -tlnp | grep 9100")

client.close()
