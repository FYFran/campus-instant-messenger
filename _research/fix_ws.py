"""Add V2Ray WebSocket location to nginx config"""
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("47.82.103.247", username="root", password="ROOT_PASSWORD_CHANGED_20260615", timeout=15, look_for_keys=False, allow_agent=False)

# Read config
stdin, stdout, stderr = c.exec_command("cat /etc/nginx/sites-enabled/tokenline", timeout=5)
config = stdout.read().decode()

# Find insertion point - between /api/ block and /chat/ block
marker = "    }\n\n    location /chat/"
ws_block = """    }

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

    location /chat/"""

if marker in config:
    config = config.replace(marker, ws_block)
    print("Found marker, replacing...")
else:
    print("Marker not found, looking for alternatives...")
    print("Config ending:", config[-500:])

# Write back
sftp = c.open_sftp()
with sftp.file("/etc/nginx/sites-enabled/tokenline", "w") as f:
    f.write(config)
sftp.close()

# Test
stdin, stdout, stderr = c.exec_command("nginx -t 2>&1", timeout=5)
out = stdout.read().decode()
err = stderr.read().decode()
print("Nginx:", out, err)

if "successful" in out or "successful" in err:
    c.exec_command("systemctl reload nginx", timeout=5)
    print("Reloaded OK")

    # Verify
    stdin, stdout, stderr = c.exec_command(
        "curl -s -o /dev/null --max-time 5 -H 'Upgrade: websocket' -H 'Connection: Upgrade' -w '%{http_code}' https://tokenline.top/ws",
        timeout=10
    )
    print("WS code:", stdout.read().decode().strip())

c.close()
