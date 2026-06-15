import paramiko
c=paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("47.82.103.247",username="root",password="ROOT_PASSWORD_CHANGED_20260615",timeout=15,look_for_keys=False,allow_agent=False)
def r(cmd,t=10):
    stdin,stdout,stderr=c.exec_command(cmd,timeout=t)
    o=stdout.read().decode(errors='replace').strip()
    e=stderr.read().decode(errors='replace').strip()
    if o: print(o)
    if e: print("E:",e)

# Read nginx config
stdin,stdout,stderr=c.exec_command("cat /etc/nginx/sites-enabled/tokenline",timeout=5)
config=stdout.read().decode()

# Add CSP after the Permissions-Policy line
csp_line='    add_header Content-Security-Policy "default-src \'self\'; script-src \'self\'; style-src \'self\' \'unsafe-inline\'; img-src \'self\' data:; connect-src \'self\'; font-src \'self\'; frame-ancestors \'none\'; base-uri \'self\'; form-action \'self\'" always;'

old='    add_header Permissions-Policy "geolocation=(), microphone=(), camera=()" always;'
new = csp_line + '\n' + old

if csp_line in config:
    print("CSP already present")
else:
    config = config.replace(old, new)
    # Write back
    s=c.open_sftp()
    with s.open("/etc/nginx/sites-enabled/tokenline","w") as f:
        f.write(config)
    s.close()
    print("CSP added")

r("nginx -t 2>&1")
r("systemctl reload nginx")
print("---")
r("curl -skI https://tokenline.top/ 2>&1 | grep -i content-security")
c.close()
