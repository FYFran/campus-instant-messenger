"""Final verification - no emoji output"""
import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect("47.82.103.247", username="root", password="ROOT_PASSWORD_CHANGED_20260615", timeout=15, look_for_keys=False, allow_agent=False)

def run(cmd, timeout=10):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors='replace')
    err = stderr.read().decode(errors='replace')
    if out: print(out.strip())
    if err: print("ERR:", err.strip())

print("=== Container ===")
run("docker ps --format '{{.Names}} {{.Status}}'")

print("\n=== new-api health ===")
run("curl -s http://127.0.0.1:3100/ | head -c 200")
run("curl -s -o /dev/null -w 'new-api: %{http_code}\n' http://127.0.0.1:3100/")

print("\n=== tokenline db ownership ===")
run("chown tokenline:tokenline /app/new-api/data/tokenline.db /app/new-api/data/tokenline.db-shm /app/new-api/data/tokenline.db-wal 2>/dev/null; stat -c '%U:%G %a %n' /app/new-api/data/tokenline.db")

print("\n=== Public endpoints ===")
run("curl -s -o /dev/null -w 'health: %{http_code}\n' https://tokenline.top/api/health")
run("curl -s -o /dev/null -w 'index: %{http_code}\n' https://tokenline.top/")
run("curl -s -o /dev/null -w 'chat: %{http_code}\n' https://tokenline.top/chat/")
run("curl -s -o /dev/null -w 'admin: %{http_code}\n' https://tokenline.top/admin/")

print("\n=== E2E: auth flow ===")
import secrets
e = f"a{secrets.token_hex(3)}@t.com"
run(f"curl -s -w '\\nregister: %{{http_code}}' -d '{{\"email\":\"{e}\",\"password\":\"Test123!\"}}' https://tokenline.top/api/auth/register | tail -1")
run(f"curl -s -w '\\nlogin: %{{http_code}}' -d '{{\"email\":\"{e}\",\"password\":\"Test123!\"}}' https://tokenline.top/api/auth/login | tail -1")

print("\n=== Server summary ===")
run("free -m | grep Mem")
run("df -h / | tail -1")
run("ps aux | grep -E 'rewriter|new-api' | grep -v grep | awk '{print $1, $6/1024\"MB\", $11}'")

client.close()
