"""Deploy v2 with bug fixes + verify"""
import paramiko, time, os

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect("47.82.103.247", username="root", password="ROOT_PASSWORD_CHANGED_20260615", timeout=15, look_for_keys=False, allow_agent=False)

def run(cmd, timeout=10):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors='replace').strip()
    err = stderr.read().decode(errors='replace').strip()
    if out: print(out)
    if err: print("ERR:", err)

# 1. Upload new binary
print("=== Upload binary ===")
sftp = client.open_sftp()
sftp.put("f:/ClaudeFiles/_research/rewriter-go/rewriter-linux", "/app/rewriter-go/rewriter-linux")
sftp.chmod("/app/rewriter-go/rewriter-linux", 0o755)
sftp.close()
print(f"Uploaded ({os.path.getsize('f:/ClaudeFiles/_research/rewriter-go/rewriter-linux')} bytes)")

# 2. Restart
print("\n=== Restart rewriter ===")
run("systemctl restart rewriter")
time.sleep(3)
run("systemctl status rewriter --no-pager | head -8")

# 3. Verify fixes
print("\n=== Verify IDOR fix ===")
run("""curl -sk -o /dev/null -w 'idor_test: %{http_code}\n' \
  "https://tokenline.top/api/chat/history?conversation_id=99999" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoxfQ.fake""" )

print("\n=== Verify email validation ===")
run("""curl -sk -w '\nemail_test: %{http_code}' \
  -d '{"email":"bademail","password":"Test123!"}' \
  https://tokenline.top/api/auth/register""")
run("""curl -sk -w '\nvalid_email: %{http_code}' \
  -d '{"email":"good@email.com","password":"Test123!"}' \
  https://tokenline.top/api/auth/register""")

print("\n=== Verify health ===")
run("curl -sk https://tokenline.top/api/health")

client.close()
