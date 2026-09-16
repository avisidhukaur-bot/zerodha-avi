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

stdin, stdout, stderr = client.exec_command('journalctl -u zerodha_engine.service -n 80 --no-pager')
print("=== ZERODHA ENGINE LOGS ===")
print(stdout.read().decode(errors='replace'))

remote_db = """# -*- coding: utf-8 -*-
import sqlite3
conn = sqlite3.connect('/root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_trader.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()
print("=== LEGS FOR BLOCK 32 ===")
legs = cur.execute('SELECT * FROM legs WHERE strike_id IN (SELECT strike_id FROM strikes WHERE block_id=32) ORDER BY leg_id DESC').fetchall()
for l in legs:
    print(dict(l))
"""
sftp = client.open_sftp()
with sftp.file("/root/BHARAT-SYSTEMS/ZERODHA-OS/chk_legs.py", "w") as f:
    f.write(remote_db)
sftp.close()

_, stdout2, _ = client.exec_command("python3 /root/BHARAT-SYSTEMS/ZERODHA-OS/chk_legs.py")
print(stdout2.read().decode(errors='replace'))

client.close()
