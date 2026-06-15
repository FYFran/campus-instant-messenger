"""TokenLine full audit â€?read-only, no changes"""
import paramiko, json

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect("47.82.103.247", username="root", password="ROOT_PASSWORD_CHANGED_20260615", timeout=15, look_for_keys=False, allow_agent=False)

def run(cmd, timeout=10):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    return stdout.read().decode() + "\n" + stderr.read().decode()

print("=== 1. systemd rewriter service ===")
print(run("cat /etc/systemd/system/rewriter.service"))
print(run("cat /etc/systemd/system/rewriter.service.d/env.conf 2>/dev/null || echo 'no env.conf'"))

print("=== 2. Nginx config ===")
print(run("cat /etc/nginx/nginx.conf"))
print(run("cat /etc/nginx/sites-enabled/tokenline 2>/dev/null || cat /etc/nginx/conf.d/*.conf 2>/dev/null"))
print(run("ls /etc/nginx/sites-enabled/ 2>/dev/null; ls /etc/nginx/conf.d/ 2>/dev/null"))

print("=== 3. Docker config ===")
print(run("docker inspect new-api --format '{{json .HostConfig}}' 2>/dev/null | python3 -m json.tool 2>/dev/null || docker inspect new-api 2>/dev/null | head -50"))
print(run("docker ps --no-trunc --format '{{.Names}} {{.Command}} {{.Ports}} {{.Mounts}}'"))

print("=== 4. Firewall ===")
print(run("iptables -L -n 2>/dev/null | head -30"))
print(run("ufw status 2>/dev/null || echo 'ufw not installed'"))
print(run("fail2ban-client status sshd 2>/dev/null || echo 'fail2ban not installed or not running'"))

print("=== 5. SSL cert ===")
print(run("certbot certificates 2>/dev/null || echo 'no certbot'"))

print("=== 6. File permissions ===")
print(run("ls -la /app/rewriter-go/"))
print(run("ls -la /app/static/ | head -20"))
print(run("ls -la /app/new-api/data/"))

print("=== 7. Process/env ===")
print(run("ps aux | grep -E 'rewriter|new-api' | grep -v grep"))
print(run("cat /proc/$(pgrep rewriter)/environ 2>/dev/null | tr '\\0' '\\n' || echo 'cannot read env'"))

print("=== 8. Logs ===")
print(run("journalctl -u rewriter --no-pager -n 50 2>/dev/null"))
print(run("tail -50 /var/log/nginx/error.log 2>/dev/null || echo 'no nginx error log'"))
print(run("tail -20 /var/log/nginx/access.log 2>/dev/null || echo 'no nginx access log'"))

print("=== 9. Cron ===")
print(run("crontab -l 2>/dev/null || echo 'no crontab'"))

print("=== 10. SSH config ===")
print(run("cat /etc/ssh/sshd_config | grep -v '^#' | grep -v '^$'"))

print("=== 11. Disk/Backups ===")
print(run("ls -la /app/backups/ 2>/dev/null || echo 'no backups dir'"))

client.close()
