import paramiko
import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

secrets = {}
secrets_path = os.path.join(os.path.dirname(__file__), "secrets.txt")
with open(secrets_path, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            secrets[k.strip()] = v.strip()

VPS_IP = secrets.get("VPS_IP", "5.75.250.104")
VPS_USER = secrets.get("VPS_USER", "root")
VPS_PASSWORD = secrets.get("VPS_PASSWORD", "")

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(VPS_IP, username=VPS_USER, password=VPS_PASSWORD, timeout=15)

remote_script = """# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, '/root/BHARAT-SYSTEMS/ZERODHA-OS')
import sqlite3
import datetime

conn = sqlite3.connect('/root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_trader.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=== ALL ACTIVE BLOCKS ===")
blocks = cur.execute('SELECT * FROM blocks WHERE status="ACTIVE"').fetchall()
for b in blocks:
    print(dict(b))

print("\\n=== TODAY LEGS / RECENT TRADES ===")
legs = cur.execute('SELECT l.*, s.strike_price, s.option_type, s.leg_type, s.block_id FROM legs l JOIN strikes s ON l.strike_id=s.strike_id ORDER BY l.leg_id DESC LIMIT 15').fetchall()
for l in legs:
    print(dict(l))

print("\\n=== RECENT SYSTEM LOGS ===")
try:
    with open('/root/BHARAT-SYSTEMS/ZERODHA-OS/engine.log', 'r') as f:
        lines = f.readlines()
        for line in lines[-50:]:
            print(line.strip())
except Exception as e:
    print('Engine log read error:', e)

try:
    with open('/root/BHARAT-SYSTEMS/ZERODHA-OS/trader.log', 'r') as f:
        lines = f.readlines()
        for line in lines[-50:]:
            print(line.strip())
except Exception as e:
    print('Trader log read error:', e)
"""

sftp = client.open_sftp()
with sftp.file("/root/BHARAT-SYSTEMS/ZERODHA-OS/inspect_today.py", "w") as f:
    f.write(remote_script)
sftp.close()

_, stdout, stderr = client.exec_command("python3 /root/BHARAT-SYSTEMS/ZERODHA-OS/inspect_today.py")
print(stdout.read().decode(errors='replace'))
err = stderr.read().decode(errors='replace')
if err:
    print("STDERR:", err)

client.close()
