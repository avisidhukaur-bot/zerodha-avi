import paramiko
import os
import sys

secrets = {}
secrets_path = os.path.join(os.path.dirname(__file__), "secrets.txt")
with open(secrets_path, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            secrets[k.strip()] = v.strip()

VPS_IP       = secrets.get("VPS_IP", "5.75.250.104")
VPS_USER     = secrets.get("VPS_USER", "root")
VPS_PASSWORD = secrets.get("VPS_PASSWORD", "")

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(VPS_IP, username=VPS_USER, password=VPS_PASSWORD, timeout=15)

def run(cmd):
    stdin, stdout, stderr = client.exec_command(cmd)
    return stdout.read().decode(errors='replace')

print("=== RECENT ORDERS / POSITIONS / STRIKES IN VPS DB ===")
py_cmd = '''python3 -c "
import sqlite3, os

db_path = '/root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_trader.db'
if not os.path.exists(db_path):
    print('DB not found at path')
    exit()

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print('--- BLOCKS ---')
for b in cur.execute('SELECT * FROM blocks ORDER BY id DESC LIMIT 5').fetchall():
    print(dict(b))

print('\n--- STRIKES ---')
for s in cur.execute('SELECT * FROM strikes ORDER BY id DESC LIMIT 10').fetchall():
    print(dict(s))

print('\n--- LEGS ---')
for l in cur.execute('SELECT * FROM legs ORDER BY id DESC LIMIT 10').fetchall():
    print(dict(l))
"'''

print(run(py_cmd))

print("\n=== RECENT ENGINE LOGS (LAST 100 LINES) ===")
print(run("tail -n 100 /root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_engine.log"))
