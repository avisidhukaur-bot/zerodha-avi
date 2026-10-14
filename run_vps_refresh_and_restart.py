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
    print("Connected to VPS via SSH!")
except Exception as e:
    print(f"VPS SSH connection failed: {e}")
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

# 1. Run morning refresh on VPS
run("cd /root/BHARAT-SYSTEMS/ZERODHA-OS && /root/BHARAT-SYSTEMS/ZERODHA-OS/venv/bin/python3 morning_refresh.py")

# 2. Restart services
run("systemctl restart zerodha_engine.service zerodha_dashboard.service zerodha_commodity.service")

# 3. Check status
run("systemctl status zerodha_engine.service zerodha_dashboard.service --no-pager")

c.close()
print("VPS Refresh & Restart completed!")
