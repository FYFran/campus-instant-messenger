"""Fix new-api docker crash"""
import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect("47.82.103.247", username="root", password="ROOT_PASSWORD_CHANGED_20260615", timeout=15, look_for_keys=False, allow_agent=False)

def run(cmd, timeout=10):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out: print(out.strip())
    if err: print("ERR:", err.strip())

print("=== Check what's happening ===")
run("docker logs --tail 20 new-api 2>&1")

print("\n=== Fix permissions ===")
# new-api runs as uid 1000 inside container. Let's find the right owner.
# First restore permissions - give write access to everyone for the data dir
run("chmod 777 /app/new-api/data")
run("chmod 666 /app/new-api/data/*.db /app/new-api/data/*.db-shm /app/new-api/data/*.db-wal 2>/dev/null || true")

print("\n=== Restart Docker ===")
run("docker restart new-api")
run("sleep 5")
run("docker ps --format '{{.Names}} {{.Status}}'")
run("curl -s -o /dev/null -w 'new-api: %{http_code}\n' http://127.0.0.1:3100/")

print("\n=== Secure: only tokenline.db owned by tokenline ===")
run("chown tokenline:tokenline /app/new-api/data/tokenline.db /app/new-api/data/tokenline.db-shm /app/new-api/data/tokenline.db-wal 2>/dev/null || true")
# Fix dir permissions
run("chmod 755 /app/new-api/data")

print("\n=== Verify admin ===")
run("curl -s -o /dev/null -w 'admin: %{http_code}\n' https://tokenline.top/admin/")

print("\n=== Verify all ===")
run("curl -s https://tokenline.top/api/health")
run("curl -s -o /dev/null -w 'register: %{http_code}\n' -d '{\"email\":\"z@z.com\",\"password\":\"test123456\"}' https://tokenline.top/api/auth/register")
run("curl -s -o /dev/null -w 'login: %{http_code}\n' -d '{\"email\":\"z@z.com\",\"password\":\"test123456\"}' https://tokenline.top/api/auth/login")

client.close()
