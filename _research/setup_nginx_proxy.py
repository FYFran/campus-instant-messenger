"""Add reverse proxy for Message Central console to nginx"""
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("47.82.103.247", username="root", password="ROOT_PASSWORD_CHANGED_20260615", timeout=15, look_for_keys=False, allow_agent=False)

# Read current config
stdin, stdout, stderr = c.exec_command("cat /etc/nginx/sites-enabled/tokenline", timeout=5)
config = stdout.read().decode()
print(f"Config: {len(config.split(chr(10)))} lines")

# Build reverse proxy block
mc_block = """
# Message Central proxy â€?for admin registration
location /mc/ {
    proxy_pass https://console.messagecentral.com/;
    proxy_set_header Host console.messagecentral.com;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_ssl_server_name on;
    proxy_cookie_domain console.messagecentral.com tokenline.top;
    proxy_cookie_path / /mc/;
    sub_filter_once off;
    sub_filter_types text/html;
    sub_filter "href=/" "href=/mc/";
    sub_filter "src=/" "src=/mc/";
    sub_filter "action=/" "action=/mc/";
}
"""

# Insert before last closing brace
lines = config.split("\n")
new_lines = []
for i, line in enumerate(lines):
    stripped = line.strip()
    if stripped == "}" and i == len(lines) - 1:
        new_lines.append(mc_block.strip())
        new_lines.append(line)
    else:
        new_lines.append(line)

new_config = "\n".join(new_lines)

# Write and test
sftp = c.open_sftp()
with sftp.file("/etc/nginx/sites-enabled/tokenline", "w") as f:
    f.write(new_config)
sftp.close()

stdin, stdout, stderr = c.exec_command("nginx -t 2>&1", timeout=5)
print("Nginx test:", stdout.read().decode(), stderr.read().decode())

stdin, stdout, stderr = c.exec_command("systemctl reload nginx 2>&1", timeout=5)
print("Reload:", stdout.read().decode(), stderr.read().decode())

# Test the proxy
stdin, stdout, stderr = c.exec_command("curl -s --max-time 5 https://tokenline.top/mc/ -o /dev/null -w '%{http_code}'", timeout=10)
print("Proxy status:", stdout.read().decode().strip())

c.close()
print("\nDone! Open https://tokenline.top/mc/ in browser")
