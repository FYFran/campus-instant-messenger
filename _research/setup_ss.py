"""Setup Shadowsocks VPN on HK server"""
import paramiko, time

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("47.82.103.247", username="root", password="ROOT_PASSWORD_CHANGED_20260615", timeout=15, look_for_keys=False, allow_agent=False)

# Kill any existing ss-server
c.exec_command("pkill ss-server 2>/dev/null; sleep 1", timeout=5)
time.sleep(1)

# Start with command-line args directly
print("Starting Shadowsocks...")
stdin, stdout, stderr = c.exec_command(
    "nohup ss-server -s 0.0.0.0 -p 8388 -k 'TokenLine@2026' -m aes-256-gcm -u --fast-open > /tmp/ss.log 2>&1 &",
    timeout=5
)
time.sleep(3)

# Check binding
stdin, stdout, stderr = c.exec_command("ss -tlnp | grep 8388", timeout=5)
print("Binding:", stdout.read().decode().strip())

# Check log
stdin, stdout, stderr = c.exec_command("cat /tmp/ss.log", timeout=5)
print("Log:", stdout.read().decode().strip())

# Test SOCKS5
stdin, stdout, stderr = c.exec_command(
    'curl -s --max-time 5 --socks5-hostname 127.0.0.1:8388 https://developers.facebook.com -o /dev/null -w "%{http_code}"',
    timeout=15
)
print("SOCKS5 test:", stdout.read().decode().strip())

c.close()
