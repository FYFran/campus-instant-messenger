"""Setup Postfix and test email delivery"""
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("47.82.103.247", username="root", password="ROOT_PASSWORD_CHANGED_20260615", timeout=15, look_for_keys=False, allow_agent=False)

def run(cmd, t=15):
    stdin, stdout, stderr = c.exec_command(cmd, timeout=t)
    out = stdout.read().decode(errors='replace').strip()
    err = stderr.read().decode(errors='replace').strip()
    if out: print("OUT:", out)
    if err: print("ERR:", err)
    return out

print("=== Config Postfix ===")
run("postconf -e 'myhostname=tokenline.top'")
run("postconf -e 'inet_interfaces=loopback-only'")
run("postconf -e 'mydestination=localhost'")
run("postconf -e 'myorigin=tokenline.top'")
run("systemctl restart postfix")
run("sleep 2")
run("systemctl status postfix | head -5")

print("\n=== Test email ===")
run("echo -e 'Subject: TokenLine OTP Test\n\nYour OTP is 123456\nSent from TokenLine server.' | sendmail -f noreply@tokenline.top fyfran@qq.com")
print("Check your QQ email: fyfran@qq.com")

c.close()
