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

for i in range(3):
    try:
        c.connect(secrets['VPS_IP'], username=secrets['VPS_USER'], password=secrets['VPS_PASSWORD'], timeout=10)
        break
    except Exception:
        pass

sftp = c.open_sftp()
sftp.put('zerodha_trader.db', '/root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_trader.db')
sftp.close()

c.exec_command('systemctl restart zerodha_dashboard.service zerodha_engine.service')
c.close()
print("VPS DB synchronized with new executed trade!")
