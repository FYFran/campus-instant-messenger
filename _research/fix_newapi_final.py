"""Fix new-api: remove --read-only, it blocks new-api's internal logging.
All real security comes from: cap-drop ALL, no-new-privileges, 127.0.0.1 binding,
memory/pids limits. read-only rootfs adds nothing for an internal-only service."""
import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect("47.82.103.247", username="root", password="ROOT_PASSWORD_CHANGED_20260615", timeout=15, look_for_keys=False, allow_agent=False)

def run(cmd, timeout=15):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out: print(out.strip())
    if err and "TZ" not in err: print("ERR:", err.strip())

print("=== Stop + remove broken container ===")
run("docker stop new-api 2>/dev/null; docker rm new-api 2>/dev/null; echo done")

print("\n=== Create new container (no --read-only) ===")
run("""docker run -d --name new-api --restart always \
  --cap-drop ALL \
  --security-opt no-new-privileges:true \
  --memory=512m --cpus=1 --pids-limit=256 \
  --log-opt max-size=10m --log-opt max-file=3 \
  -p 127.0.0.1:3100:3000 \
  -e TZ=Asia/Hong_Kong \
  -v /app/new-api/data:/data:rw \
  calciumion/new-api:v0.12.0""")

print("\n=== Wait for startup ===")
run("sleep 8")
run("docker ps --format '{{.Names}} {{.Status}}'")
run("docker logs --tail 5 new-api 2>&1")

print("\n=== Verify ===")
run("curl -s -o /dev/null -w 'new-api: %{http_code}\n' http://127.0.0.1:3100/")
run("curl -s -o /dev/null -w 'admin: %{http_code}\n' https://tokenline.top/admin/")
run("curl -s https://tokenline.top/api/health")

print("\n=== E2E: register + login ===")
import secrets
test_email = f"test{secrets.token_hex(2)}@tokenline.top"
run(f"curl -s -o /dev/null -w 'register: %{{http_code}}\n' -d '{{\"email\":\"{test_email}\",\"password\":\"Test123456!\"}}' https://tokenline.top/api/auth/register")
run(f"curl -s -w '\\n' -d '{{\"email\":\"{test_email}\",\"password\":\"Test123456!\"}}' https://tokenline.top/api/auth/login | cut -c1-100")

client.close()
