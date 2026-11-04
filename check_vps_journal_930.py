import paramiko
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys_secrets = {}

with open(r'c:\Users\Dell\Desktop\cheenna zerodha\secrets.txt', encoding='utf-8', errors='replace') as f:
    for line in f:
        if '=' in line and not line.startswith('#'):
            k, v = line.split('=', 1)
            sys_secrets[k.strip()] = v.strip()

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(sys_secrets['VPS_IP'], username=sys_secrets['VPS_USER'], password=sys_secrets['VPS_PASSWORD'])
cmd = 'journalctl -u zerodha_engine.service --since "2026-11-03 09:25:00" --until "2026-11-03 10:05:00" --no-pager | grep -iE "close|exit|square|error|block|m1|m2|m3|fail" | head -n 50'
stdin, stdout, stderr = client.exec_command(cmd)
print("Journal Logs (Engine):\n" + stdout.read().decode(errors='replace'))

cmd_dash = 'journalctl -u zerodha_dashboard.service --since "2026-11-03 09:25:00" --until "2026-11-03 10:05:00" --no-pager | grep -iE "close|exit|square|error|block|m1|m2|m3|button|wipe" | head -n 50'
stdin, stdout, stderr = client.exec_command(cmd_dash)
print("Journal Logs (Dashboard):\n" + stdout.read().decode(errors='replace'))

client.close()
