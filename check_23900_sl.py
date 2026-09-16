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
import kite_executor as ke
import db

conn = sqlite3.connect('/root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_trader.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=== ACTIVE BLOCKS & ALL STRIKES ===")
blocks = cur.execute('SELECT * FROM blocks WHERE status="ACTIVE"').fetchall()
for b in blocks:
    print("Block:", dict(b))
    strikes = cur.execute('SELECT * FROM strikes WHERE block_id=?', (b['block_id'],)).fetchall()
    for s in strikes:
        print("  Strike:", dict(s))
        legs = cur.execute('SELECT * FROM legs WHERE strike_id=?', (s['strike_id'],)).fetchall()
        for l in legs:
            print("    Leg:", dict(l))

print("\\n=== 23900 CE SPECIFIC DETAILS ===")
s_23900 = cur.execute('SELECT * FROM strikes WHERE strike_price=23900').fetchall()
for s in s_23900:
    print("23900 Strike:", dict(s))
    legs = cur.execute('SELECT * FROM legs WHERE strike_id=?', (s['strike_id'],)).fetchall()
    for l in legs:
        print("  Leg:", dict(l))

print("\\n=== LIVE KITE POSITIONS & ORDERS ===")
kite = None
try:
    kite = ke.get_kite()
    if kite:
        pos = kite.positions().get('net', [])
        for p in pos:
            if p.get('quantity', 0) != 0 or '23900' in p.get('tradingsymbol', ''):
                print("Position:", p.get('tradingsymbol'), "Qty:", p.get('quantity'), "Buy/Sell Avg:", p.get('average_price'), "LTP:", p.get('last_price'), "PnL:", p.get('pnl'))
        
        orders = kite.orders()
        for o in orders:
            if o.get('status') in ['OPEN', 'TRIGGER PENDING']:
                print("Open SL/Trigger Order:", o.get('tradingsymbol'), o.get('order_type'), "Price:", o.get('price'), "Trigger:", o.get('trigger_price'), "Qty:", o.get('quantity'), "Status:", o.get('status'))
except Exception as e:
    print("Kite fetch error:", e)
"""

sftp = client.open_sftp()
with sftp.file("/root/BHARAT-SYSTEMS/ZERODHA-OS/chk_23900_sl.py", "w") as f:
    f.write(remote_script)
sftp.close()

_, stdout, stderr = client.exec_command("python3 /root/BHARAT-SYSTEMS/ZERODHA-OS/chk_23900_sl.py")
print(stdout.read().decode(errors='replace'))
err = stderr.read().decode(errors='replace')
if err:
    print("STDERR:", err)

client.close()
