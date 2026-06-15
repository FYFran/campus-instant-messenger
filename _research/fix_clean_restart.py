"""Kill everything, clean start"""
import paramiko, time

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect("47.82.103.247", username="root", password="ROOT_PASSWORD_CHANGED_20260615", timeout=15, look_for_keys=False, allow_agent=False)

def run(cmd, timeout=10):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors='replace').strip()
    err = stderr.read().decode(errors='replace').strip()
    if out: print(out)
    if err: print("ERR:", err)

print("=== Kill ALL rewriter processes ===")
run("killall -9 rewriter rewriter-linux 2>/dev/null; sleep 1; echo done")
run("fuser -k 9100/tcp 2>/dev/null; sleep 2; echo done")

print("\n=== Verify absolutely nothing on 9100 ===")
run("ss -tlnp | grep 9100 && echo 'PORT STILL USED!' || echo 'port 9100 free'")

print("\n=== Delete old binary to prevent auto-restart ===")
run("rm -f /app/rewriter-go/rewriter")

print("\n=== Start fresh ===")
run("systemctl daemon-reload")
run("systemctl reset-failed rewriter 2>/dev/null; echo done")
run("systemctl start rewriter")
time.sleep(3)

print("\n=== Verify ===")
run("systemctl status rewriter --no-pager | head -10")
run("curl -s https://tokenline.top/api/health")
run("ps aux | grep -E 'rewriter' | grep -v grep")

print("\n=== Verify binary is the new one ===")
run("ls -la /app/rewriter-go/rewriter-linux")
run("stat -c '%Y' /app/rewriter-go/rewriter-linux")  # modification time

client.close()
