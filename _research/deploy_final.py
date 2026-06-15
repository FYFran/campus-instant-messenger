"""Final deploy with all fixes"""
import paramiko, time

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect("47.82.103.247", username="root", password="ROOT_PASSWORD_CHANGED_20260615", timeout=15, look_for_keys=False, allow_agent=False)

def run(cmd, timeout=15):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors='replace').strip()
    err = stderr.read().decode(errors='replace').strip()
    if out: print(out)
    if err: print("ERR:", err)

print("=== Upload ===")
sftp = client.open_sftp()
sftp.put("f:/ClaudeFiles/_research/rewriter-go/rewriter-linux", "/tmp/rewriter-linux")
sftp.close()

print("\n=== Stop + kill old + move + start ===")
run("systemctl stop rewriter")
run("fuser -k 9100/tcp 2>/dev/null; sleep 2; echo port_cleared")
run("mv /tmp/rewriter-linux /app/rewriter-go/rewriter-linux && chown tokenline:tokenline /app/rewriter-go/rewriter-linux")
run("cp /app/rewriter-go/sql/schema.sql /app/rewriter-go/sql/schema.sql.bak 2>/dev/null; echo done")
run("systemctl start rewriter")
time.sleep(3)

print("\n=== Status ===")
run("systemctl status rewriter --no-pager | head -8")

print("\n=== Health ===")
run("curl -s https://tokenline.top/api/health")

print("\n=== Verify bug fixes ===")
run("""curl -sk -o /dev/null -w 'bad_email: %{http_code}\n' \
  -d '{"email":"noat","password":"Test123!"}' \
  https://tokenline.top/api/auth/register""")
run("""curl -sk -o /dev/null -w 'good_email: %{http_code}\n' \
  -d '{"email":"real@test.com","password":"Test123!"}' \
  https://tokenline.top/api/auth/register""")

print("\n=== All endpoints ===")
for p in ["/api/health", "/", "/chat/", "/admin/"]:
    run(f"curl -sk -o /dev/null -w '{p}: %{{http_code}}\n' https://tokenline.top{p}")

client.close()
