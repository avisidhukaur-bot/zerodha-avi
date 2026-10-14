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

try:
    c.connect(secrets['VPS_IP'], username=secrets['VPS_USER'], password=secrets['VPS_PASSWORD'], timeout=15)
    print("SSH Connected to VPS!")
except Exception as e:
    print(f"SSH failed: {e}")
    sys.exit(1)

def run(cmd):
    print(f"\n=== CMD: {cmd} ===")
    _, out, err = c.exec_command(cmd)
    o = out.read().decode('utf-8', errors='replace')
    e = err.read().decode('utf-8', errors='replace')
    if o:
        print(o.strip())
    if e:
        print("ERR:", e.strip())

run("iptables -L -n -v")
run("iptables -t nat -L -n -v")
run("fail2ban-client status 2>/dev/null || echo 'No fail2ban'")
run("systemctl status zerodha_dashboard.service --no-pager")
run("curl -s http://localhost:9007/ -o /dev/null -w '%{http_code}' && echo ' Localhost 9007 OK'")
run("curl -s http://5.75.250.104:9007/ -o /dev/null -w '%{http_code}' && echo ' Public IP 9007 OK'")

# Also let's check what IP is listening
run("netstat -tlpn | grep 9007 || ss -tlpn | grep 9007")

c.close()
