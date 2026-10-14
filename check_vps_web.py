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
c.connect(secrets['VPS_IP'], username=secrets['VPS_USER'], password=secrets['VPS_PASSWORD'], timeout=15)

def run(cmd):
    print(f"\n=== CMD: {cmd} ===")
    _, out, err = c.exec_command(cmd)
    o = out.read().decode('utf-8', errors='replace')
    e = err.read().decode('utf-8', errors='replace')
    if o:
        print(o.strip())
    if e:
        print("ERR:", e.strip())

run("which nginx")
run("systemctl status nginx 2>/dev/null || echo 'No nginx'")
run("which caddy")
run("ss -tlpn")
run("ip route")
run("curl -I http://localhost:9007")

c.close()
