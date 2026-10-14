import paramiko
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

secrets = {}
with open('secrets.txt', encoding='utf-8') as f:
    for l in f:
        if '=' in l and not l.startswith('#'):
            k, v = l.strip().split('=', 1)
            secrets[k.strip()] = v.strip()

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
connected = False
for attempt in range(5):
    try:
        print(f"Connecting attempt {attempt+1}...")
        c.connect(secrets['VPS_IP'], username=secrets['VPS_USER'], password=secrets['VPS_PASSWORD'], timeout=10)
        connected = True
        print("Connected!")
        break
    except Exception as e:
        print(f"Attempt {attempt+1} failed: {e}")

if not connected:
    sys.exit(1)

def run(cmd):
    print(f"\n=== CMD: {cmd} ===")
    _, out, err = c.exec_command(cmd)
    o = out.read().decode('utf-8', errors='replace')
    e = err.read().decode('utf-8', errors='replace')
    if o:
        print(o)
    if e:
        print("ERR:", e)

run("ufw status verbose")
run("iptables -L INPUT -v -n")
run("ss -tlnp")
run("ufw allow 9007/tcp")
run("ufw status")

c.close()
