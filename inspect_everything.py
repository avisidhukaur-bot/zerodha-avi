import paramiko
import os
import sys
import json

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
import sqlite3
import json

sys.path.insert(0, '/root/BHARAT-SYSTEMS/ZERODHA-OS')
from kite_executor import kite_executor
import db

db.load_secrets()
kite_executor.ensure_logged_in()
k = kite_executor.kite

print("=================== 1. KITE PROFILE & MARGIN ===================")
if k:
    try:
        prof = k.profile()
        print(f"Logged in as: {prof.get('user_name')} ({prof.get('user_id')}) | Email: {prof.get('email')} | Broker: {prof.get('broker')}")
    except Exception as e:
        print(f"Profile error: {e}")

    try:
        margin = k.margins('equity')
        avail = margin.get('available', {}).get('cash', 0)
        net = margin.get('net', 0)
        utilised = margin.get('utilised', {}).get('debits', 0)
        print(f"Available Cash: Rs {avail:,.2f} | Net Margin: Rs {net:,.2f} | Utilised Margin: Rs {utilised:,.2f}")
    except Exception as e:
        print(f"Margin error: {e}")
else:
    print("Kite instance is None!")

print("\\n=================== 2. KITE LIVE POSITIONS ===================")
if k:
    try:
        positions = k.positions().get('net', [])
        active_pos = [p for p in positions if p.get('quantity') != 0]
        print(f"Total Net Positions: {len(positions)} (Active open: {len(active_pos)})")
        for p in active_pos:
            sym = p.get('tradingsymbol')
            qty = p.get('quantity')
            buy = p.get('buy_price')
            sell = p.get('sell_price')
            ltp = p.get('last_price')
            pnl = p.get('pnl')
            print(f"- {sym} | Qty: {qty} | BuyPrice: {buy} | SellPrice: {sell} | LTP: {ltp} | PnL: Rs {pnl:,.2f}")
    except Exception as e:
        print(f"Positions error: {e}")

print("\\n=================== 3. SQLITE DB STATE ===================")
conn = sqlite3.connect('/root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_trader.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

cur.execute("SELECT * FROM blocks WHERE status != 'DELETED' ORDER BY block_id DESC LIMIT 10")
blocks = [dict(row) for row in cur.fetchall()]
print(f"Blocks in DB: {len(blocks)}")
for b in blocks:
    print(f"Block #{b.get('block_number')} (ID {b.get('block_id')}) | Unit: {b.get('anchor_unit_name')} | Status: {b.get('status')} | Expiry: {b.get('expiry_date')} | Side: {b.get('side_type')} | Master Anchor: {b.get('master_anchor_price')}")

cur.execute("SELECT * FROM strikes WHERE status != 'DELETED' ORDER BY strike_id DESC LIMIT 10")
strikes = [dict(row) for row in cur.fetchall()]
print(f"\\nStrikes in DB: {len(strikes)}")
for s in strikes:
    print(f"Strike ID {s.get('strike_id')} | Block {s.get('block_id')} | {s.get('strike_price')} {s.get('option_type')} ({s.get('leg_type')}) | Status: {s.get('status')} | State: {s.get('trade_state')} | Anchor: Rs {s.get('anchor_price')} | SL: {s.get('sl_pct')}%")

conn.close()

print("\\n=================== 4. ALGO & SETTINGS ===================")
algo = db.get("algo_running", "OFF")
paper = db.get("paper_trading", "NO")
lots = db.get("manual_lot_size", "65")
print(f"Algo Running: {algo} | Paper Trading: {paper} | Lot Size: {lots}")
"""

sftp = client.open_sftp()
with sftp.file("/tmp/inspect_everything.py", "w") as f:
    f.write(remote_script)
sftp.close()

stdin, stdout, stderr = client.exec_command("python3 /tmp/inspect_everything.py")
out = stdout.read().decode('utf-8', errors='replace')
err = stderr.read().decode('utf-8', errors='replace')
print(out)
if err:
    print("STDERR:\n", err)

client.close()
