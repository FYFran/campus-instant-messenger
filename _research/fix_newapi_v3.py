"""Fix new-api: restore data dir ownership + use working image"""
import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect("47.82.103.247", username="root", password="ROOT_PASSWORD_CHANGED_20260615", timeout=15, look_for_keys=False, allow_agent=False)

def run(cmd, timeout=15):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out: print(out.strip())
    if err: print("ERR:", err.strip())

print("=== Fix data dir ownership (Docker runs as root) ===")
run("chown -R root:root /app/new-api/data")
run("chmod 755 /app/new-api/data")
run("chmod 644 /app/new-api/data/*.db /app/new-api/data/*.db-shm 2>/dev/null || true")
run("chmod 755 /app/new-api/data/logs 2>/dev/null || true")

print("\n=== Stop broken container ===")
run("docker stop new-api 2>/dev/null; docker rm new-api 2>/dev/null; echo done")

print("\n=== Create container with :latest (previously working image) ===")
run("""docker run -d --name new-api --restart always \
  --cap-drop ALL \
  --security-opt no-new-privileges:true \
  --memory=512m --cpus=1 --pids-limit=256 \
  --log-opt max-size=10m --log-opt max-file=3 \
  -p 127.0.0.1:3100:3000 \
  -e TZ=Asia/Hong_Kong \
  -v /app/new-api/data:/data:rw \
  calciumion/new-api:latest""")

print("\n=== Wait for startup ===")
import time
time.sleep(10)
run("docker ps --format '{{.Names}} {{.Status}}'")
run("docker logs --tail 10 new-api 2>&1")

print("\n=== Verify ===")
run("curl -s -o /dev/null -w 'new-api: %{http_code}\n' http://127.0.0.1:3100/")
run("curl -s -o /dev/null -w 'admin: %{http_code}\n' https://tokenline.top/admin/")

print("\n=== Restore tokenline db ownership ===")
# TokenLine Go process needs write access to tokenline.db, but not one-api.db
run("chown tokenline:tokenline /app/new-api/data/tokenline.db /app/new-api/data/tokenline.db-shm /app/new-api/data/tokenline.db-wal 2>/dev/null || true")
run("stat -c '%U:%G %a %n' /app/new-api/data/tokenline.db")

print("\n=== Final check ===")
run("curl -s https://tokenline.top/api/health")
run("systemctl status rewriter --no-pager | head -8")

client.close()
