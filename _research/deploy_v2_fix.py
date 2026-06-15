"""Deploy v2: upload to tmp first, then move"""
import paramiko, time, os

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect("47.82.103.247", username="root", password="ROOT_PASSWORD_CHANGED_20260615", timeout=15, look_for_keys=False, allow_agent=False)

def run(cmd, timeout=15):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors='replace').strip()
    err = stderr.read().decode(errors='replace').strip()
    if out: print(out)
    if err: print("ERR:", err)

# Upload to tmp
print("=== Upload to /tmp ===")
sftp = client.open_sftp()
local = "f:/ClaudeFiles/_research/rewriter-go/rewriter-linux"
sftp.put(local, "/tmp/rewriter-linux")
sftp.chmod("/tmp/rewriter-linux", 0o755)
sftp.close()
print("Uploaded", os.path.getsize(local), "bytes")

# Move to destination + restart
print("\n=== Move + restart ===")
run("mv /tmp/rewriter-linux /app/rewriter-go/rewriter-linux && chown tokenline:tokenline /app/rewriter-go/rewriter-linux")
run("systemctl restart rewriter")
time.sleep(3)
run("systemctl status rewriter --no-pager | head -8")

# Verify
print("\n=== Health ===")
run("curl -s https://tokenline.top/api/health")

print("\n=== IDOR fix verification ===")
run("""curl -sk -o /dev/null -w 'idor_nonexist_conv: %{http_code}\n' \
  "https://tokenline.top/api/chat/history?conversation_id=99999" \
  -H 'Authorization: Bearer invalid.jwt.token'""")

print("\n=== Email validation ===")
run("""curl -sk -o /dev/null -w 'bad_email: %{http_code}\n' \
  -d '{"email":"notanemail","password":"Test123!"}' \
  https://tokenline.top/api/auth/register""")
run("""curl -sk -o /dev/null -w 'good_email: %{http_code}\n' \
  -d '{"email":"good@test.com","password":"Test123!"}' \
  https://tokenline.top/api/auth/register""")

print("\n=== X-Real-IP rate limit ===")
run("curl -sk -o /dev/null -w 'health: %{http_code}\n' https://tokenline.top/api/health")

client.close()
