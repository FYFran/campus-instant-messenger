"""Setup V2Ray VMess + WebSocket + TLS behind nginx on port 443"""
import paramiko, time, uuid, json

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("47.82.103.247", username="root", password="ROOT_PASSWORD_CHANGED_20260615", timeout=15, look_for_keys=False, allow_agent=False)

# Generate a random UUID for V2Ray
v2ray_uuid = str(uuid.uuid4())
print(f"UUID: {v2ray_uuid}")

# V2Ray config �?listens on localhost:10000, WebSocket
v2ray_config = {
    "log": {"loglevel": "warning"},
    "inbounds": [{
        "port": 10000,
        "listen": "127.0.0.1",
        "protocol": "vmess",
        "settings": {
            "clients": [{"id": v2ray_uuid, "alterId": 0}]
        },
        "streamSettings": {
            "network": "ws",
            "wsSettings": {"path": "/ws"}
        }
    }],
    "outbounds": [{
        "protocol": "freedom",
        "tag": "direct"
    }]
}

# Write V2Ray config
stdin, stdout, stderr = c.exec_command(
    "cat > /usr/local/etc/v2ray/config.json << 'VEOF'\n" +
    json.dumps(v2ray_config, indent=2) + "\nVEOF",
    timeout=5
)
print("V2Ray config written")

# Start V2Ray
c.exec_command("systemctl enable v2ray; systemctl restart v2ray", timeout=10)
time.sleep(2)
stdin, stdout, stderr = c.exec_command("systemctl is-active v2ray", timeout=5)
print(f"V2Ray: {stdout.read().decode().strip()}")

# Add WebSocket location to nginx config
ws_config = """
# V2Ray WebSocket proxy
location /ws {
    proxy_pass http://127.0.0.1:10000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_read_timeout 86400s;
}
"""

# Read nginx config, insert before last }
stdin, stdout, stderr = c.exec_command("cat /etc/nginx/sites-enabled/tokenline", timeout=5)
config = stdout.read().decode()
lines = config.split("\n")
new_lines = []
for i, line in enumerate(lines):
    if line.strip() == "}" and i == len(lines) - 1:
        new_lines.append(ws_config.strip())
        new_lines.append(line)
    else:
        new_lines.append(line)

new_config = "\n".join(new_lines)
sftp = c.open_sftp()
with sftp.file("/etc/nginx/sites-enabled/tokenline", "w") as f:
    f.write(new_config)
sftp.close()

# Test and reload nginx
stdin, stdout, stderr = c.exec_command("nginx -t 2>&1 && systemctl reload nginx && echo RELOADED", timeout=10)
print(f"Nginx: {stdout.read().decode().strip()} {stderr.read().decode().strip()}")

# Verify WebSocket endpoint
stdin, stdout, stderr = c.exec_command(
    'curl -s --max-time 5 https://tokenline.top/ws -o /dev/null -w "%{http_code}"',
    timeout=10
)
print(f"WS endpoint: {stdout.read().decode().strip()}")

# Print client config
print(f"""
=====================================
VPN已搭�?- V2Ray VMess + WebSocket
=====================================

客户端配�?

地址: tokenline.top
端口: 443
UUID: {v2ray_uuid}
协议: vmess
传输: ws (WebSocket)
路径: /ws
TLS: 开�?=====================================
""")

c.close()
