"""Diagnose new-api crash root cause"""
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

print("=== Check if old image is still cached ===")
run("docker images | grep new-api")

print("\n=== Check data dir permissions ===")
run("ls -la /app/new-api/")
run("ls -la /app/new-api/data/")
run("ls -la /app/new-api/logs/ 2>/dev/null || echo 'no logs dir'")

print("\n=== Who owns the files? ===")
run("stat -c '%U:%G %a %n' /app/new-api/data/*")

print("\n=== Try running new-api with shell to debug ===")
run("docker run --rm -it --entrypoint /bin/sh calciumion/new-api:v0.12.0 -c 'ls -la /data/; ls -la /var/log/; id; ls -la /' 2>&1", timeout=15)

print("\n=== Check if new-api expects specific user ===")
run("docker inspect calciumion/new-api:v0.12.0 --format '{{.Config.User}}' 2>/dev/null || echo 'no user set'")

print("\n=== Full container inspect ===")
run("docker inspect new-api --format '{{json .State}}' 2>/dev/null | python3 -m json.tool 2>/dev/null | head -20")

client.close()
