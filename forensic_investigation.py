import paramiko
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

secrets = {}
with open('secrets.txt', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            secrets[k.strip()] = v.strip()

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(secrets['VPS_IP'], username=secrets['VPS_USER'], password=secrets['VPS_PASSWORD'], timeout=15)

def run(cmd):
    stdin, stdout, stderr = client.exec_command(cmd)
    return stdout.read().decode(errors='replace')

print("=== 1. SEARCH FOR BLOCK CREATION / DEPLOYMENT (09:40 - 09:50) ===")
print(run("journalctl -u zerodha_dashboard.service --since '2026-10-14 09:40:00' --until '2026-10-14 09:50:00' --no-pager"))

print("\n=== 2. ENGINE LOGS AROUND DEPLOYMENT (09:40 - 09:50) ===")
print(run("journalctl -u zerodha_engine.service --since '2026-10-14 09:40:00' --until '2026-10-14 09:50:00' --no-pager"))

print("\n=== 3. SEARCH FOR REGIME & SPOT LOGS TODAY ===")
print(run("journalctl -u zerodha_engine.service --since '2026-10-14 09:40:00' --no-pager | grep -E 'REGIME|Spot|22720|23400' | head -n 30"))

print("\n=== 4. SEARCH FOR 23400 CE OR PENDING WINGS TODAY ===")
print(run("journalctl -u zerodha_engine.service --since '2026-10-14 09:40:00' --no-pager | grep -iE '23400|pending|wing|autonomous' | head -n 30"))

client.close()
