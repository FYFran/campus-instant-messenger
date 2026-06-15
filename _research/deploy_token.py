"""TokenLine token-only deploy â€?binary + all updated frontend pages"""
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
    return out

print("=== 1. Upload binary ===")
sftp = client.open_sftp()
sftp.put("f:/ClaudeFiles/_research/rewriter-go/rewriter-linux", "/tmp/rewriter-linux")
sftp.close()
print("Binary uploaded")

print("\n=== 2. Upload frontend ===")
sftp = client.open_sftp()
sftp.put("f:/ClaudeFiles/_research/index-final.html", "/tmp/index.html")
sftp.put("f:/ClaudeFiles/_research/chat.html", "/tmp/chat.html")
sftp.put("f:/ClaudeFiles/_research/topup.html", "/tmp/topup.html")
sftp.put("f:/ClaudeFiles/_research/compare-v2.html", "/tmp/compare.html")
sftp.close()
print("Frontend uploaded")

print("\n=== 3. Stop service + move files ===")
run("systemctl stop rewriter")
run("fuser -k 9100/tcp 2>/dev/null; sleep 1; echo ok")

# Move binary
run("mv /tmp/rewriter-linux /app/rewriter-go/rewriter-linux && chown tokenline:tokenline /app/rewriter-go/rewriter-linux && chmod 755 /app/rewriter-go/rewriter-linux")
print("Binary deployed")

# Move HTML
run("mv /tmp/index.html /app/static/index.html")
run("mv /tmp/chat.html /app/static/chat/index.html")
run("mv /tmp/topup.html /app/static/topup.html")
run("mv /tmp/compare.html /app/static/compare.html")
print("Frontend deployed")

print("\n=== 4. Start service ===")
run("systemctl start rewriter")
time.sleep(3)

print("\n=== 5. Status ===")
run("systemctl status rewriter --no-pager | head -8")

print("\n=== 6. Health ===")
run("curl -s https://tokenline.top/api/health")

print("\n=== 7. Packs endpoint ===")
run("curl -s https://tokenline.top/api/packs")

print("\n=== 8. Verify pages ===")
for p in ["/", "/chat/", "/topup.html", "/compare.html"]:
    code = run(f"curl -sk -o /dev/null -w '%{{http_code}}' https://tokenline.top{p}")
    print(f"  {p}: {code}")

client.close()
print("\nDONE.")
