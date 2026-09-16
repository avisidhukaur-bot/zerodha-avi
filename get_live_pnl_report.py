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
import db
from kite_executor import kite_executor
import sqlite3

db.load_secrets()
kite_executor.load_session_from_db()

if not kite_executor.ensure_logged_in():
    print("ERROR: Kite login failed!")
    sys.exit(1)

kite = kite_executor.kite
pos = kite.positions()
net_pos = pos.get('net', [])
day_pos = pos.get('day', [])

print("=== ALL POSITIONS ON ZERODHA ===")
total_net_pnl = 0.0
total_realized_pnl = 0.0
total_unrealized_pnl = 0.0

for p in net_pos:
    sym = p.get('tradingsymbol')
    qty = p.get('quantity', 0)
    pnl = float(p.get('pnl', 0.0) or 0.0)
    m2m = float(p.get('m2m', 0.0) or 0.0)
    r_pnl = float(p.get('realised', 0.0) or 0.0)
    un_pnl = float(p.get('unrealised', 0.0) or 0.0)
    total_net_pnl += pnl
    total_realized_pnl += r_pnl
    total_unrealized_pnl += un_pnl
    
    st_label = "OPEN" if qty != 0 else "CLOSED"
    print(f"- {sym:20} | Status: {st_label:6} | Qty: {qty:4} | Buy Avg: {p.get('buy_price', 0):6.2f} | Sell Avg: {p.get('sell_price', 0):6.2f} | LTP: {p.get('last_price', 0):6.2f} | Total PnL: Rs {pnl:10,.2f} | Realised: Rs {r_pnl:9,.2f} | M2M: Rs {m2m:9,.2f}")

print("\\n=== SUMMARY ===")
print(f"Total Portfolio P&L: Rs {total_net_pnl:,.2f}")
print(f"Total Realised P&L : Rs {total_realized_pnl:,.2f}")
print(f"Total Unrealised P&L: Rs {total_unrealized_pnl:,.2f}")
"""

sftp = client.open_sftp()
with sftp.file("/root/BHARAT-SYSTEMS/ZERODHA-OS/get_pnl_live.py", "w") as f:
    f.write(remote_script)
sftp.close()

_, stdout, stderr = client.exec_command("python3 /root/BHARAT-SYSTEMS/ZERODHA-OS/get_pnl_live.py")
print(stdout.read().decode(errors='replace'))
err = stderr.read().decode(errors='replace')
if err:
    print("STDERR:", err)

client.close()
