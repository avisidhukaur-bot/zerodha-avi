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

stdin, stdout, stderr = c.exec_command("grep -E '2026-09-17 09:(1[5-9]|2[0-5])' /root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_engine.log")
print("=== LOGS FROM 09:15 TO 09:25 TODAY ===")
out = stdout.read().decode('utf-8', errors='replace')
print(out if out else "No matching logs in zerodha_engine.log")

c.close()
