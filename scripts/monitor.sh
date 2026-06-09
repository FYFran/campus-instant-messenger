#!/bin/bash
# 校园即时通 — 全方位监控
# 检查: API健康 / 数据库 / 磁盘 / 内存 / nginx / 证书过期

HEALTH_URL="${HEALTH_URL:-http://localhost/api/health}"
NTFY_TOPIC="${NTFY_TOPIC:-pete-campus-CHANGEME}"   # 部署时替换
NTFY_TOKEN="${NTFY_TOKEN:-YOUR_NTFY_TOKEN}"
NTFY_HOST="${NTFY_HOST:-https://ntfy.sh}"

# ── Maintenance mode: touch /var/run/campus-monitor.maintenance to silence ──
MAINTENANCE_FILE="/var/run/campus-monitor.maintenance"
if [ -f "$MAINTENANCE_FILE" ]; then
    echo "$(date): maintenance mode active — skipping notifications"
    # Still write checks to log but never notify
    notify() { :; }
else
    notify() {
        curl -s -H "Authorization: Bearer $NTFY_TOKEN" \
            -H "Content-Type: application/json" \
            -d "{\"topic\":\"$NTFY_TOPIC\",\"title\":\"$1\",\"message\":\"$2\",\"priority\":\"high\"}" \
            "$NTFY_HOST" > /dev/null 2>&1
    }
fi

check_endpoint() {
    local name=$1 url=$2 expected=$3
    local resp
    resp=$(curl -s --max-time 5 "$url" 2>/dev/null)
    if echo "$resp" | grep -q "$expected"; then
        return 0
    else
        notify "$name DOWN" "Expected '$expected' in response from $url"
        return 1
    fi
}

# ── API health checks ──
check_endpoint "API" "$HEALTH_URL" '"status": "ok"'
check_endpoint "DB" "$HEALTH_URL" '"database": "ok"'

# ── Disk usage (>85% alert) ──
disk_use=$(df -h / | awk 'NR==2{gsub(/%/,"");print $5}')
[ -z "$disk_use" ] && disk_use=0
if [ "$disk_use" -gt 85 ] 2>/dev/null; then
    notify "Disk ${disk_use}%" "Root partition above 85%"
fi

# ── Memory (<200MB free alert) ──
mem_free=$(free -m | awk 'NR==1{for(i=1;i<=NF;i++) if($i=="available") col=i} NR==2{print $col}')
[ -z "$mem_free" ] && mem_free=9999
if [ "$mem_free" -lt 200 ] 2>/dev/null; then
    notify "Low memory" "${mem_free}MB free"
fi

# ── Nginx ──
nginx_status=$(systemctl is-active nginx 2>/dev/null)
if [ "$nginx_status" != "active" ]; then
    notify "nginx DOWN" "systemctl status: $nginx_status"
fi

# ── SSL certificate expiry (<14d warning) ──
cert_expiry=$(openssl s_client -servername 139.196.50.134 -connect localhost:443 </dev/null 2>/dev/null | openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2)
if [ -n "$cert_expiry" ]; then
    exp_epoch=$(date -d "$cert_expiry" +%s 2>/dev/null)
    now_epoch=$(date +%s)
    days_left=$(( (exp_epoch - now_epoch) / 86400 ))
    if [ "$days_left" -lt 14 ] 2>/dev/null; then
        notify "SSL cert expires in ${days_left}d" "Renew soon: $cert_expiry"
    fi
fi

echo "$(date): checks complete"
