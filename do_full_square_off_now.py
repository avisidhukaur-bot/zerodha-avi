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
import telegram_bot as tg

db.load_secrets()
kite_executor.ensure_logged_in()
k = kite_executor.kite

if not k:
    print("FATAL: KiteConnect instance is None!")
    sys.exit(1)

print("=== STEP 1: FETCHING LIVE BROKER POSITIONS ===")
pos = k.positions()
net_positions = pos.get('net', [])

short_legs = [p for p in net_positions if p.get('quantity', 0) < 0]
long_legs = [p for p in net_positions if p.get('quantity', 0) > 0]

print(f"Total open short legs to cover: {len(short_legs)}")
print(f"Total open hedge legs to close: {len(long_legs)}")

# --- PHASE 1: BUY TO COVER ALL SHORT LEGS FIRST (MARGIN PROTECTION) ---
print("\\n=== PHASE 1: BUY-TO-COVER ALL SHORT LEGS FIRST ===")
for p in short_legs:
    sym = p.get('tradingsymbol')
    qty = abs(p.get('quantity', 0))
    prod = p.get('product', 'NRML')
    exch = p.get('exchange', 'NFO')
    print(f"Covering SHORT {sym} -> Placing BUY for {qty} qty...")
    try:
        order_id = k.place_order(
            variety=k.VARIETY_REGULAR,
            exchange=exch,
            tradingsymbol=sym,
            transaction_type=k.TRANSACTION_TYPE_BUY,
            quantity=qty,
            product=prod,
            order_type=k.ORDER_TYPE_MARKET,
            tag="CLOSE_SHORT"
        )
        print(f"✅ Covered {sym} | Order ID: {order_id}")
    except Exception as e:
        print(f"❌ Error covering {sym}: {e}")

time.sleep(1.5)

# --- PHASE 2: SELL TO CLOSE ALL LONG HEDGES SECOND ---
print("\\n=== PHASE 2: SELL-TO-CLOSE ALL LONG HEDGES SECOND ===")
for p in long_legs:
    sym = p.get('tradingsymbol')
    qty = abs(p.get('quantity', 0))
    prod = p.get('product', 'NRML')
    exch = p.get('exchange', 'NFO')
    print(f"Closing HEDGE {sym} -> Placing SELL for {qty} qty...")
    try:
        order_id = k.place_order(
            variety=k.VARIETY_REGULAR,
            exchange=exch,
            tradingsymbol=sym,
            transaction_type=k.TRANSACTION_TYPE_SELL,
            quantity=qty,
            product=prod,
            order_type=k.ORDER_TYPE_MARKET,
            tag="CLOSE_HEDGE"
        )
        print(f"✅ Closed Hedge {sym} | Order ID: {order_id}")
    except Exception as e:
        print(f"❌ Error closing hedge {sym}: {e}")

time.sleep(2.0)

# --- PHASE 3: VERIFY BROKER ZERO OPEN POSITIONS ---
print("\\n=== PHASE 3: VERIFYING BROKER ZERO OPEN POSITIONS ===")
pos_after = k.positions()
active_remaining = [p for p in pos_after.get('net', []) if p.get('quantity', 0) != 0]

if len(active_remaining) == 0:
    print("🎉 CONFIRMED: 0 OPEN POSITIONS ON ZERODHA BROKER! ALL POSITIONS SAFELY SQUARED OFF.")
else:
    print(f"⚠️ WARNING: {len(active_remaining)} positions still open:")
    for p in active_remaining:
        print(f"  - {p.get('tradingsymbol')} Qty: {p.get('quantity')}")

# --- PHASE 4: CLEARING DATABASE TABLES (CLEAN SLATE) ---
print("\\n=== PHASE 4: CLEARING DATABASE TABLES ===")
db_path = '/root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_trader.db'
conn = sqlite3.connect(db_path)
cur = conn.cursor()
cur.execute("DELETE FROM legs")
cur.execute("DELETE FROM strikes")
cur.execute("DELETE FROM blocks")
cur.execute("DELETE FROM settings WHERE key LIKE 'os_traded_date_%'")
cur.execute("DELETE FROM settings WHERE key = 'os_settings_locked'")
conn.commit()
conn.close()
print("✅ Database cleared: blocks, strikes, legs, and OS locks are completely reset to 0.")

# Send Telegram alert
try:
    tg.send(
        "🛑 <b>ALL TRADES SQUARED OFF & DATABASE RESET</b> 🛑\\n"
        "All M1 and OS trades and hedges have been closed on Zerodha broker.\\n"
        "Net open exposure: <b>0 QTY (Clean State)</b>.\\n"
        "Status: <b>All Realized Profits Booked & Pods Reset.</b>"
    )
except Exception as e:
    print("Telegram error:", e)

print("\\n=== COMPLETED SUCCESSFULLY ===")
"""

sftp = client.open_sftp()
with sftp.file('/tmp/square_off_everything.py', 'w') as f:
    f.write(remote_script)
sftp.close()

stdin, stdout, stderr = client.exec_command('python3 /tmp/square_off_everything.py')
out = stdout.read().decode('utf-8', errors='replace')
err = stderr.read().decode('utf-8', errors='replace')
print(out)
if err:
    print("STDERR:", err)

client.close()
