import paramiko
import sys
import os

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

stdin, stdout, stderr = c.exec_command('grep -A 10 -B 5 "11:45:" /root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_engine.log')
print("=== 11:45 LOGS ===")
print(stdout.read().decode('utf-8', errors='replace'))
c.close()
