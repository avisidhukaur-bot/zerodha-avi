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
c.connect(secrets['VPS_IP'], username=secrets['VPS_USER'], password=secrets['VPS_PASSWORD'], timeout=10)

cmd = 'journalctl -u zerodha_engine.service --since "2026-10-01 08:18:00" --until "2026-10-01 08:23:00" --no-pager'
stdin, stdout, stderr = c.exec_command(cmd)
print("=== EXACT JOURNALCTL LOGS 08:18 to 08:23 UTC ===")
print(stdout.read().decode('utf-8', errors='replace'))
print(stderr.read().decode('utf-8', errors='replace'))
c.close()
