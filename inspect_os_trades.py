import paramiko
import sys
import sqlite3

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

sftp = client.open_sftp()
sftp.get('/root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_trader.db', 'vps_zerodha_trader.db')
sftp.close()
client.close()

conn = sqlite3.connect('vps_zerodha_trader.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=== ALL BLOCKS ===")
for b in cur.execute("SELECT * FROM blocks").fetchall():
    print(dict(b))

print("\n=== ALL STRIKES ===")
for s in cur.execute("SELECT * FROM strikes").fetchall():
    print(dict(s))

print("\n=== OS SETTINGS ===")
for st in cur.execute("SELECT * FROM settings WHERE key LIKE 'os_%'").fetchall():
    print(f"{st['key']} = {st['value']}")

print("\n=== LEGS ===")
for l in cur.execute("SELECT * FROM legs").fetchall():
    print(dict(l))

conn.close()
