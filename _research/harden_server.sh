#!/bin/bash
# TokenLine hardening script
set -e

echo "=== 1. Create tokenline user ==="
id -u tokenline &>/dev/null || useradd -r -s /bin/false tokenline

echo "=== 2. Replace binary ==="
cp /app/rewriter-go/rewriter-linux /app/rewriter-go/rewriter.bak 2>/dev/null || true
chown tokenline:tokenline /app/rewriter-go/rewriter-linux
chmod 755 /app/rewriter-go/rewriter-linux
chown -R tokenline:tokenline /app/rewriter-go

echo "=== 3. Write new .env ==="
# Secrets loaded from deployment environment — NEVER hardcode in git
cat > /app/rewriter-go/.env << 'ENVEOF'
PORT=9100
JWT_SECRET=${JWT_SECRET}
DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY}
DEEPSEEK_BASE_URL=http://127.0.0.1:3100/v1
DB_PATH=/app/new-api/data/tokenline.db
XENDIT_API_KEY=
XENDIT_WEBHOOK_TOKEN=
DODO_API_KEY=${DODO_API_KEY}
DODO_PRODUCT_ID=${DODO_PRODUCT_ID}
DODO_WEBHOOK_SECRET=${DODO_WEBHOOK_SECRET}
DODO_BASE_URL=https://test.dodopayments.com
ENVEOF
chmod 600 /app/rewriter-go/.env

echo "=== 4. Update systemd (run as tokenline + lockdown) ==="
cat > /etc/systemd/system/rewriter.service << 'SVCEND'
[Unit]
Description=TokenLine Go Backend
After=network.target

[Service]
Type=simple
User=tokenline
Group=tokenline
WorkingDirectory=/app/rewriter-go
EnvironmentFile=/app/rewriter-go/.env
ExecStartPre=/bin/bash -c "fuser -k 9100/tcp 2>/dev/null || true"
ExecStartPre=/bin/sleep 1
ExecStart=/app/rewriter-go/rewriter-linux
Restart=always
RestartSec=5
ProtectSystem=full
ProtectHome=true
PrivateTmp=true
NoNewPrivileges=true
ReadWritePaths=/app/new-api/data /app/rewriter-go

[Install]
WantedBy=multi-user.target
SVCEND

echo "=== 5. Fix nginx ==="
# Fix duplicate MIME type warning
sed -i '/^[[:space:]]*text\/html/d' /etc/nginx/nginx.conf

cat > /etc/nginx/sites-enabled/tokenline << 'NGXEND'
server {
    listen 80;
    server_name tokenline.top www.tokenline.top;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name tokenline.top www.tokenline.top;
    server_tokens off;

    ssl_certificate /etc/letsencrypt/live/tokenline.top/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/tokenline.top/privkey.pem;

    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options nosniff always;
    add_header X-Frame-Options DENY always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Permissions-Policy "geolocation=(), microphone=(), camera=()" always;

    client_max_body_size 10M;

    location /admin/ {
        limit_req zone=login burst=5 nodelay;
        proxy_pass http://127.0.0.1:3100/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 120s;
    }

    location /api/ {
        limit_req zone=api burst=20 nodelay;
        proxy_pass http://127.0.0.1:9100;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 120s;
        proxy_send_timeout 120s;
        proxy_buffering off;
    }

    location /chat/ {
        alias /app/static/chat/;
        index index.html;
        try_files $uri $uri/ =404;
    }

    location / {
        root /app/static;
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    error_page 404 /404.html;
    error_page 500 502 503 504 /500.html;
}
NGXEND

echo "=== 6. Fix Docker (remove CapAdd) ==="
docker stop new-api || true
docker rm new-api || true
docker run -d --name new-api --restart always \
  --read-only \
  --cap-drop ALL \
  --security-opt no-new-privileges:true \
  --memory=512m --cpus=1 --pids-limit=256 \
  --log-opt max-size=10m --log-opt max-file=3 \
  -p 127.0.0.1:3100:3000 \
  -e TZ=Asia/Hong_Kong \
  -v /app/new-api/data:/data:rw \
  calciumion/new-api:v0.12.0

echo "=== 7. Set DB permissions ==="
chown -R tokenline:tokenline /app/new-api/data 2>/dev/null || true

echo "=== 8. Reload all ==="
nginx -t && systemctl reload nginx
systemctl daemon-reload
systemctl restart rewriter
sleep 3

echo "=== 9. Verify ==="
systemctl status rewriter --no-pager -l | head -10
echo "---"
curl -s https://tokenline.top/api/health
echo ""
curl -s -o /dev/null -w "index: %{http_code}\n" https://tokenline.top/
curl -s -o /dev/null -w "chat:  %{http_code}\n" https://tokenline.top/chat/
curl -s -o /dev/null -w "admin: %{http_code}\n" https://tokenline.top/admin/

echo "=== DONE ==="
