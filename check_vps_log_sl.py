import paramiko
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

secrets = {}
with open('secrets.txt', encoding='utf-8') as f:
    for line in f:
        if line.strip() and '=' in line and not line.startswith('#'):
            k, v = line.strip().split('=', 1)
            secrets[k.strip()] = v.strip()

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(secrets['VPS_IP'], username=secrets['VPS_USER'], password=secrets['VPS_PASSWORD'], timeout=10)

stdin, stdout, stderr = client.exec_command('grep -E "22200|V5-SL" /root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_engine.log | tail -n 25')
print(stdout.read().decode())
client.close()
