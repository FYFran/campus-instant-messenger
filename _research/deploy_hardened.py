"""Deploy hardened TokenLine"""
import paramiko, os, time

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect("47.82.103.247", username="root", password="ROOT_PASSWORD_CHANGED_20260615", timeout=15, look_for_keys=False, allow_agent=False)

def run(cmd, timeout=30):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out: print(out.strip())
    if err: print("ERR:", err.strip())
    return out + err

print("=== Upload binary ===")
sftp = client.open_sftp()
sftp.put("f:/ClaudeFiles/_research/rewriter-go/rewriter-linux", "/app/rewriter-go/rewriter-linux")
sftp.put("f:/ClaudeFiles/_research/harden_server.sh", "/app/rewriter-go/harden_server.sh")
sftp.chmod("/app/rewriter-go/harden_server.sh", 0o755)
sftp.close()
print("Upload done. Binary size:", os.path.getsize("f:/ClaudeFiles/_research/rewriter-go/rewriter-linux"), "bytes")

print("\n=== Run hardening script ===")
run("bash /app/rewriter-go/harden_server.sh 2>&1", timeout=120)

print("\n=== Final health check ===")
time.sleep(2)
run("curl -s https://tokenline.top/api/health")
run("curl -s -o /dev/null -w 'login: %{http_code}\n' -d '{\"email\":\"test@test.com\",\"password\":\"test123\"}' https://tokenline.top/api/auth/login")
run("systemctl status rewriter --no-pager | head -15")

client.close()
print("\n=== DONE ===")
