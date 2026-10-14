import paramiko
import sys
import sqlite3

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

sftp = client.open_sftp()
sftp.get('/root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_trader.db', 'vps_zerodha_trader.db')
sftp.close()
client.close()

print("Downloaded VPS zerodha_trader.db successfully.")

conn = sqlite3.connect('vps_zerodha_trader.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("--- BLOCKS ---")
for b in cur.execute("SELECT * FROM blocks").fetchall():
    print(dict(b))

print("\n--- STRIKES ---")
for s in cur.execute("SELECT * FROM strikes").fetchall():
    print(dict(s))

print("\n--- SETTINGS ---")
for st in cur.execute("SELECT * FROM settings").fetchall():
    print(f"{st['key']} = {st['value']}")

conn.close()
