"""Check TokenLine server status"""
import paramiko

def run(cmd, timeout=10):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    return stdout.read().decode() + stderr.read().decode()

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect("47.82.103.247", username="root", password="ROOT_PASSWORD_CHANGED_20260615", timeout=15, look_for_keys=False, allow_agent=False)

print("=== systemctl status rewriter ===")
print(run("systemctl status rewriter --no-pager -l 2>&1"))

print("\n=== docker ps ===")
print(run("docker ps --format '{{.Names}} {{.Status}} {{.Ports}}'"))

print("\n=== memory ===")
print(run("free -m"))

print("\n=== disk ===")
print(run("df -h /"))

print("\n=== Go API health ===")
print(run("curl -s localhost:9100/api/health"))

print("\n=== Go process ===")
print(run("ps aux | grep -E 'rewriter|new-api' | grep -v grep"))

print("\n=== env vars ===")
print(run("cat /etc/systemd/system/rewriter.service.d/env.conf 2>/dev/null || cat /app/rewriter-go/.env 2>/dev/null || echo 'no env file found'; echo '---'; systemctl show rewriter --property=Environment 2>/dev/null"))

print("\n=== nginx check ===")
print(run("nginx -t 2>&1; curl -s -o /dev/null -w '%{http_code}' https://tokenline.top/api/health"))

client.close()
