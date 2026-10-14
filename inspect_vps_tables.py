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
client.connect(secrets['VPS_IP'], username=secrets['VPS_USER'], password=secrets['VPS_PASSWORD'], timeout=10)

def run(cmd):
    stdin, stdout, stderr = client.exec_command(cmd)
    return stdout.read().decode(errors='replace').strip()

print("--- COUNT ROWS IN VPS DB TABLES ---")
for t in ['blocks', 'strikes', 'legs', 'settings', 'trade_logs']:
    print(f"Table {t}:", run(f"sqlite3 /root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_trader.db 'SELECT count(*) FROM {t};'"))

print("\n--- ALL SETTINGS ON VPS ---")
print(run("sqlite3 /root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_trader.db 'SELECT key, value FROM settings;'"))

client.close()
