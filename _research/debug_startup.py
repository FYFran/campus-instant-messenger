"""Debug startup failure"""
import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect("47.82.103.247", username="root", password="ROOT_PASSWORD_CHANGED_20260615", timeout=15, look_for_keys=False, allow_agent=False)

def run(cmd, timeout=10):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors='replace').strip()
    err = stderr.read().decode(errors='replace').strip()
    if out: print(out)
    if err: print("ERR:", err)

print("=== Logs ===")
run("journalctl -u rewriter --no-pager -n 20 2>&1")

print("\n=== Try running directly ===")
run("sudo -u tokenline /app/rewriter-go/rewriter-linux 2>&1", timeout=5)

print("\n=== Check binary ===")
run("file /app/rewriter-go/rewriter-linux")
run("ldd /app/rewriter-go/rewriter-linux 2>&1 || echo 'static binary'")

print("\n=== Check .env readable ===")
run("sudo -u tokenline cat /app/rewriter-go/.env 2>&1")

print("\n=== Check DB access ===")
run("sudo -u tokenline cat /app/new-api/data/tokenline.db > /dev/null 2>&1 && echo 'DB readable' || echo 'DB NOT READABLE'")
run("sudo -u tokenline ls -la /app/new-api/data/tokenline.db")

client.close()
