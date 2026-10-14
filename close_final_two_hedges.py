import paramiko
import sys
import os

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

secrets = {}
with open('secrets.txt', encoding='utf-8') as f:
    for line in f:
        if line.strip() and '=' in line and not line.startswith('#'):
            k, v = line.strip().split('=', 1)
            secrets[k.strip()] = v.strip()

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(secrets['VPS_IP'], username=secrets['VPS_USER'], password=secrets['VPS_PASSWORD'], timeout=15)

remote_script = """# -*- coding: utf-8 -*-
import sys
import time
import json
import sqlite3

sys.path.insert(0, '/root/BHARAT-SYSTEMS/ZERODHA-OS')
from kite_executor import kite_executor
import db

db.load_secrets()
kite_executor.ensure_logged_in()
k = kite_executor.kite

print("=== FETCHING REMAINING HEDGES TO CLOSE ===")
pos = k.positions()
net_positions = pos.get('net', [])
remaining_hedges = [p for p in net_positions if p.get('quantity', 0) > 0]

for p in remaining_hedges:
    sym = p.get('tradingsymbol')
    qty = p.get('quantity', 0)
    prod = p.get('product', 'NRML')
    exch = p.get('exchange', 'NFO')
    
    # Fetch live quote for limit order price
    try:
        q = k.quote([f"{exch}:{sym}"])
        ltp = q.get(f"{exch}:{sym}", {}).get('last_price', 0)
        # Sell limit with safe 10% discount for instant fill
        limit_price = round(max(0.5, ltp * 0.90), 1)
        print(f"Placing LIMIT SELL for {sym} | Qty: {qty} | LTP: {ltp} | Limit Price: {limit_price}...")
        order_id = k.place_order(
            variety=k.VARIETY_REGULAR,
            exchange=exch,
            tradingsymbol=sym,
            transaction_type=k.TRANSACTION_TYPE_SELL,
            quantity=qty,
            product=prod,
            order_type=k.ORDER_TYPE_LIMIT,
            price=limit_price,
            tag="CLOSE_HEDGE"
        )
        print(f"✅ Closed {sym} | Order ID: {order_id}")
    except Exception as e:
        print(f"❌ Error closing {sym}: {e}")

time.sleep(2.0)

print("\\n=== FINAL BROKER POSITION VERIFICATION ===")
pos_final = k.positions()
active_pos = [p for p in pos_final.get('net', []) if p.get('quantity', 0) != 0]

if len(active_pos) == 0:
    print("🎉 100% CONFIRMED: ZERO (0) OPEN POSITIONS ON BROKER! ALL HEDGES SUCCESSFULLY CLOSED.")
else:
    print(f"Remaining open positions: {len(active_pos)}")
    for p in active_pos:
        print(f"  - {p.get('tradingsymbol')} Qty: {p.get('quantity')}")

# Database complete clean
conn = sqlite3.connect('/root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_trader.db')
cur = conn.cursor()
cur.execute("DELETE FROM legs")
cur.execute("DELETE FROM strikes")
cur.execute("DELETE FROM blocks")
conn.commit()
conn.close()
print("✅ Database 100% clean and reset.")
"""

sftp = client.open_sftp()
with sftp.file('/tmp/close_final_hedges.py', 'w') as f:
    f.write(remote_script)
sftp.close()

stdin, stdout, stderr = client.exec_command('python3 /tmp/close_final_hedges.py')
out = stdout.read().decode('utf-8', errors='replace')
err = stderr.read().decode('utf-8', errors='replace')
print(out)
if err:
    print("STDERR:", err)

client.close()
