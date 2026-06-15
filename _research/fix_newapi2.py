"""Fix new-api docker: add writable log dir"""
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

print("=== Create log dir on host ===")
run("mkdir -p /app/new-api/logs && chmod 777 /app/new-api/logs")

print("\n=== Recreate container with writable /var/log or /new-api/logs ===")
run("docker stop new-api 2>/dev/null || true")
run("docker rm new-api 2>/dev/null || true")

# Try both common log paths
run("""docker run -d --name new-api --restart always \
  --read-only \
  --cap-drop ALL \
  --security-opt no-new-privileges:true \
  --memory=512m --cpus=1 --pids-limit=256 \
  --log-opt max-size=10m --log-opt max-file=3 \
  -p 127.0.0.1:3100:3000 \
  -e TZ=Asia/Hong_Kong \
  -v /app/new-api/data:/data:rw \
  -v /app/new-api/logs:/var/log:rw \
  calciumion/new-api:v0.12.0""", timeout=30)

run("sleep 5")
run("docker ps --format '{{.Names}} {{.Status}}'")
run("docker logs --tail 5 new-api 2>&1")

if "Restarting" in run("docker ps --format '{{.Names}} {{.Status}}'", timeout=5):
    print("\n=== Still crashing. Try without --read-only ===")
    run("docker stop new-api; docker rm new-api")
    run("""docker run -d --name new-api --restart always \
      --cap-drop ALL \
      --security-opt no-new-privileges:true \
      --memory=512m --cpus=1 --pids-limit=256 \
      --log-opt max-size=10m --log-opt max-file=3 \
      -p 127.0.0.1:3100:3000 \
      -e TZ=Asia/Hong_Kong \
      -v /app/new-api/data:/data:rw \
      -v /app/new-api/logs:/var/log:rw \
      calciumion/new-api:v0.12.0""", timeout=30)
    run("sleep 5")
    run("docker ps --format '{{.Names}} {{.Status}}'")
    run("docker logs --tail 10 new-api 2>&1")

print("\n=== Check data dir ===")
run("ls -la /app/new-api/data/")
run("ls -la /app/new-api/logs/")

print("\n=== Verify admin ===")
run("curl -s -o /dev/null -w 'admin: %{http_code}\n' https://tokenline.top/admin/")
run("curl -s -o /dev/null -w 'new-api: %{http_code}\n' http://127.0.0.1:3100/")

client.close()
