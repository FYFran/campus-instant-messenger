"""TokenLine capacity + bottleneck analysis"""
import paramiko
c=paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("47.82.103.247",username="root",password="ROOT_PASSWORD_CHANGED_20260615",timeout=10,look_for_keys=False,allow_agent=False)
def r(cmd,t=10):
    stdin,stdout,stderr=c.exec_command(cmd,timeout=t)
    return stdout.read().decode(errors='replace').strip()

print("=== Server Specs ===")
print(r("nproc && free -m | grep Mem && df -h / | tail -1 && cat /proc/cpuinfo | grep 'model name' | head -1"))

print("\n=== Current Usage ===")
print(r("ps aux | grep -E 'rewriter|new-api' | grep -v grep | awk '{print $1,$6/1024\"MB\",$4\"%CPU\"}'"))
print(r("free -m | grep Mem"))

print("\n=== SQLite WAL stats ===")
print(r("ls -la /app/new-api/data/tokenline.db*"))

print("\n=== Network ===")
print(r("ss -s"))

print("\n=== Load average ===")
print(r("uptime"))

print("\n=== DB Size & Growth ===")
print(r("sqlite3 /app/new-api/data/tokenline.db 'SELECT COUNT(*) as users FROM users; SELECT COUNT(*) as messages FROM messages; SELECT COUNT(*) as payments FROM payments; SELECT COUNT(*) as conversations FROM conversations;' 2>/dev/null || echo 'sqlite3 not available'"))

print("\n=== Nginx connection capacity ===")
print(r("grep 'worker_connections' /etc/nginx/nginx.conf || echo 'using default 768'"))

print("\n=== DISK IO ===")
print(r("dd if=/dev/zero of=/tmp/test bs=1M count=100 2>&1 | tail -1; rm /tmp/test"))
c.close()
