"""部署脚本 — 上传代码+APK到服务器并重启"""
import paramiko
import sys
import os

HOST = "139.196.50.134"
USER = "root"
PASS = os.environ.get("SSH_PASSWORD", "")
if not PASS:
    print("ERROR: Set SSH_PASSWORD environment variable before deploying")
    print("  PowerShell: $env:SSH_PASSWORD='your_password'")
    sys.exit(1)
SERVICE = "campus-app"  # 服务器上的systemd服务名

# 本地文件 → 服务器路径
FILES = {
    "f:/ClaudeFiles/campus_app/server/main.py": "/app/main.py",
    "f:/ClaudeFiles/campus_app/server/db.py": "/app/db.py",
    "f:/ClaudeFiles/campus_app/server/migrate.py": "/app/migrate.py",
    "f:/ClaudeFiles/nginx-campus.conf": "/etc/nginx/sites-enabled/campus",
    "f:/ClaudeFiles/campus_app/build/app/outputs/flutter-apk/app-release.apk": "/app/static/app-release.apk",
}

# migrations目录的SQL文件
MIGRATIONS_DIR = "f:/ClaudeFiles/campus_app/server/migrations"
MIGRATIONS_REMOTE = "/app/migrations"

def ssh_cmd(ssh, cmd):
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if err: print(f"  [stderr] {err.strip()}")
    return out.strip()

def deploy():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    print(f"连接 {HOST}...")
    ssh.connect(HOST, username=USER, password=PASS)
    print("已连接\n")

    sftp = ssh.open_sftp()

    # 1. 上传所有代码文件
    for local, remote in FILES.items():
        if not os.path.exists(local):
            print(f"  [跳过] {local} (文件不存在)")
            continue
        print(f"上传 {local} → {remote}")
        sftp.put(local, remote)

    sftp.close()

    # 1.5. 上传migrations SQL文件
    print("\n同步数据库迁移文件...")
    ssh_cmd(ssh, f"mkdir -p {MIGRATIONS_REMOTE}")
    if os.path.isdir(MIGRATIONS_DIR):
        for fname in sorted(os.listdir(MIGRATIONS_DIR)):
            if fname.endswith('.sql'):
                local_path = os.path.join(MIGRATIONS_DIR, fname)
                remote_path = f"{MIGRATIONS_REMOTE}/{fname}"
                print(f"  {fname} → {remote_path}")
                sftp2 = ssh.open_sftp()
                sftp2.put(local_path, remote_path)
                sftp2.close()

    # 2. 运行数据库迁移
    print("\n运行数据库迁移...")

    # Pre-flight: backup freshness check (布阵 Iron Law: NO DEPLOY WITHOUT FRESH BACKUP)
    print("  检查备份新鲜度...")
    backup_check = ssh_cmd(ssh,
        "latest=$(find /app/backups -name '*.sql.gz' -mmin -60 2>/dev/null | sort | tail -1); "
        "if [ -z \"$latest\" ]; then echo 'NO_FRESH_BACKUP'; else echo \"$latest\"; fi")
    if backup_check == "NO_FRESH_BACKUP":
        print("  ABORT: No backup fresher than 1 hour found.")
        print("  Run: ssh root@139.196.50.134 'bash /app/backup.sh' first.")
        ssh.close()
        sys.exit(1)
    print(f"  Latest fresh backup: {backup_check}")

    result = ssh_cmd(ssh, "cd /app && python3 migrate.py 2>&1")
    print(f"  {result}")

    # 2. 如果是首次部署，运行server_setup.sh
    check = ssh_cmd(ssh, f"systemctl is-active {SERVICE} 2>/dev/null || echo 'not_found'")
    if check == "not_found":
        print("\n⚠️  服务未运行，可能需要先执行 server_setup.sh")
        print("   scp server_setup.sh root@{HOST}:/root/")
        print("   ssh root@{HOST} 'bash /root/server_setup.sh'")

    # 3. 重载nginx（新配置生效）
    print("\n重载nginx...")
    nginx_test = ssh_cmd(ssh, "nginx -t 2>&1")
    if "ok" in nginx_test.lower() or "successful" in nginx_test.lower():
        ssh_cmd(ssh, "systemctl reload nginx")
        print("  nginx 已重载")
    else:
        print(f"  nginx配置有误: {nginx_test}")

    # 4. 重启应用
    print(f"\n重启 {SERVICE}...")
    result = ssh_cmd(ssh, f"systemctl restart {SERVICE} && sleep 2 && systemctl status {SERVICE} --no-pager | head -5")
    print(f"  {result}")

    # 5. 验证API
    print("\n验证API...")
    test = ssh_cmd(ssh, "curl -s http://localhost/api/health 2>/dev/null")
    print(f"  健康检查: {test}")

    ssh.close()
    print("\n部署完成")

if __name__ == "__main__":
    deploy()
