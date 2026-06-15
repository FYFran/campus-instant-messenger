import paramiko, socket, traceback
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    client.connect(
        hostname="47.82.103.247",
        port=22,
        username="root",
        password="ROOT_PASSWORD_CHANGED_20260615",
        timeout=15,
        look_for_keys=False,
        allow_agent=False,
        auth_timeout=10,
        banner_timeout=10,
    )
    stdin, stdout, stderr = client.exec_command("echo HELLO; hostname; whoami")
    print("STDOUT:", stdout.read().decode())
    print("STDERR:", stderr.read().decode())
    client.close()
except paramiko.AuthenticationException as e:
    print("Auth failed:", e)
except socket.timeout as e:
    print("Timeout:", e)
except Exception as e:
    traceback.print_exc()
