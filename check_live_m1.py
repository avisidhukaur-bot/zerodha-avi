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
import block_manager as bm

db.load_secrets()
kite_executor.load_session_from_db()

print("=== 1. CURRENT BLOCKS IN DB ===")
blocks = db.get_all_blocks()
for b in blocks:
    print(f"Block #{b['block_number']} (ID {b['block_id']}) Unit: {b.get('anchor_unit_name')} Status: {b['status']}")
    strikes = db.get_strikes_by_block(b['block_id'])
    for s in strikes:
        print(f"   StrikeID {s['strike_id']} | {s['strike_price']} {s['option_type']} ({s['leg_type']}) | Status: {s['status']} | State: {s.get('trade_state')} | Reentry: {s.get('reentry_enabled')}")

print("\\n=== 2. KITE LIVE POSITIONS ===")
if kite_executor.ensure_logged_in():
    pos_data = kite_executor.get_positions()
    pos_list = pos_data if isinstance(pos_data, list) else pos_data.get('net', [])
    for p in pos_list:
        if p.get('quantity', 0) != 0 or '24300' in p.get('tradingsymbol','') or '24800' in p.get('tradingsymbol',''):
            print(f"- {p.get('tradingsymbol')} | NetQty: {p.get('quantity')} | BuyAvg: {p.get('buy_price')} | SellAvg: {p.get('sell_price')} | LTP: {p.get('last_price')} | PnL: Rs {p.get('pnl', 0):,.2f}")

print("\\n=== 3. KITE RECENT ORDERS (LAST 10) ===")
if kite_executor.ensure_logged_in():
    orders = kite_executor.get_orders() if hasattr(kite_executor, 'get_orders') else []
    for o in orders[-10:]:
        print(f"- {o.get('order_timestamp')} | {o.get('tradingsymbol')} | {o.get('transaction_type')} | Qty: {o.get('quantity')} | Status: {o.get('status')} | Price: {o.get('price')}")
"""

sftp = client.open_sftp()
with sftp.file("/root/BHARAT-SYSTEMS/ZERODHA-OS/check_live_reentry.py", "w") as f:
    f.write(remote_script)
sftp.close()

_, stdout, stderr = client.exec_command("python3 /root/BHARAT-SYSTEMS/ZERODHA-OS/check_live_reentry.py")
print(stdout.read().decode(errors='replace'))
err = stderr.read().decode(errors='replace')
if err:
    print("STDERR:", err)

client.close()
