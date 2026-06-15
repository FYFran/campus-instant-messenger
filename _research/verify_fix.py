"""Verify and fix remaining issues"""
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
    return out

print("=== new-api status ===")
run("docker ps --format '{{.Names}} {{.Status}} {{.Ports}}'")
run("sleep 3 && curl -s -o /dev/null -w 'new-api: %{http_code}\n' http://127.0.0.1:3100/")

print("\n=== admin endpoint ===")
run("curl -s -o /dev/null -w 'admin: %{http_code}\n' https://tokenline.top/admin/")

print("\n=== Fix nginx duplicate MIME (proper fix) ===")
# Read the actual line and fix properly
run("head -25 /etc/nginx/nginx.conf | grep -n 'text/html'")
run("sed -i '22d' /etc/nginx/nginx.conf")
run("nginx -t 2>&1")
run("systemctl reload nginx && echo 'nginx reloaded'")

print("\n=== Verify process as tokenline user ===")
run("ps aux | grep rewriter | grep -v grep")

print("\n=== Environment safety check ===")
# Check that /proc/PID/environ is not readable
run("cat /proc/$(pgrep rewriter-linux)/environ 2>&1 | tr '\\0' '\\n' | head -5")

print("\n=== Full endpoint check ===")
run("curl -s -o /dev/null -w 'health: %{http_code}\n' https://tokenline.top/api/health")
run("curl -s -o /dev/null -w 'index: %{http_code}\n' https://tokenline.top/")
run("curl -s -o /dev/null -w 'chat: %{http_code}\n' https://tokenline.top/chat/")
run("curl -s -o /dev/null -w 'register: %{http_code}\n' -d '{}' https://tokenline.top/api/auth/register")
run("curl -s -o /dev/null -w 'admin: %{http_code}\n' https://tokenline.top/admin/")

client.close()
