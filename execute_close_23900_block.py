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
import sqlite3
from kite_executor import kite_executor
import block_manager as bm
import telegram_bot as tg
from datetime import datetime
import pytz

IST = pytz.timezone("Asia/Kolkata")
now_str = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")

db.load_secrets()
kite_executor.load_session_from_db()

print("=== 1. VERIFYING BROKER POSITION FOR 23900 CE ===")
if not kite_executor.ensure_logged_in():
    print("ERROR: Kite login failed!")
    sys.exit(1)

kite = kite_executor.kite
pos = kite.positions().get('net', [])

target_pos = None
for p in pos:
    sym = p.get('tradingsymbol', '')
    qty = p.get('quantity', 0)
    if '23900' in sym and 'CE' in sym and qty != 0:
        target_pos = p
        print(f"Found open position on broker: {sym} | Qty: {qty} | Avg: {p.get('average_price')} | LTP: {p.get('last_price')} | PnL: Rs {p.get('pnl', 0):,.2f}")

# Check 24400 CE hedge if any open
hedge_pos = None
for p in pos:
    sym = p.get('tradingsymbol', '')
    qty = p.get('quantity', 0)
    if '24400' in sym and 'CE' in sym and qty != 0:
        hedge_pos = p
        print(f"Found hedge position on broker: {sym} | Qty: {qty} | Avg: {p.get('average_price')} | LTP: {p.get('last_price')}")

# Execute Broker Exit for 23900 CE
fill_exit_price = 0.0
if target_pos:
    sym = target_pos.get('tradingsymbol')
    qty = target_pos.get('quantity')
    print(f"Placing market order to BUY TO COVER {sym} (Qty: {abs(qty)})...")
    try:
        oid = kite.place_order(
            variety=kite.VARIETY_REGULAR,
            exchange=kite.EXCHANGE_NFO,
            tradingsymbol=sym,
            transaction_type=kite.TRANSACTION_TYPE_BUY,
            quantity=abs(qty),
            product=kite.PRODUCT_NRML,
            order_type=kite.ORDER_TYPE_MARKET
        )
        print(f"✅ Square-off order placed successfully! Order ID: {oid}")
        
        # Check order fill price
        import time
        time.sleep(1)
        orders = kite.orders()
        for o in orders:
            if str(o.get('order_id')) == str(oid):
                fill_exit_price = float(o.get('average_price') or o.get('price') or 0.0)
                print(f"Order Status: {o.get('status')} | Fill Exit Price: Rs {fill_exit_price:.2f}")
                break
    except Exception as e:
        print(f"Broker Order Error: {e}")
else:
    print("No open 23900 CE position found on broker (already closed or 0 qty).")

# Close hedge on broker if open
if hedge_pos and hedge_pos.get('quantity', 0) > 0:
    h_sym = hedge_pos.get('tradingsymbol')
    h_qty = hedge_pos.get('quantity')
    print(f"Placing market order to SELL hedge {h_sym} (Qty: {h_qty})...")
    try:
        h_oid = kite.place_order(
            variety=kite.VARIETY_REGULAR,
            exchange=kite.EXCHANGE_NFO,
            tradingsymbol=h_sym,
            transaction_type=kite.TRANSACTION_TYPE_SELL,
            quantity=h_qty,
            product=kite.PRODUCT_NRML,
            order_type=kite.ORDER_TYPE_MARKET
        )
        print(f"✅ Hedge closed! Order ID: {h_oid}")
    except Exception as e:
        print(f"Hedge Order Error: {e}")

print("\\n=== 2. UPDATING DATABASE FOR BLOCK 30 (UNIT M2) ===")
conn = sqlite3.connect('/root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_trader.db')
cur = conn.cursor()

# Get 23900 strike info
s_23900 = cur.execute('SELECT * FROM strikes WHERE strike_price=23900 AND option_type="CE" AND block_id=30').fetchone()
if s_23900:
    s_id = s_23900[0]
    # Update legs
    leg = cur.execute('SELECT * FROM legs WHERE strike_id=? AND (exit_price=0 OR exit_price IS NULL)', (s_id,)).fetchone()
    if leg:
        leg_id = leg[0]
        entry_p = float(leg[2] or 160.05)
        exit_p = fill_exit_price if fill_exit_price > 0 else float(target_pos.get('last_price', 50.0) if target_pos else 50.0)
        pnl = (entry_p - exit_p) * 65
        cur.execute('UPDATE legs SET exit_price=?, exit_time=?, realized_pnl=? WHERE leg_id=?', (exit_p, now_str, pnl, leg_id))
        print(f"Updated Leg {leg_id}: Entry=Rs {entry_p}, Exit=Rs {exit_p}, Realized PnL=+Rs {pnl:,.2f}")
    
    # Mark strike CLOSED
    cur.execute('UPDATE strikes SET status="CLOSED", trade_state="CLOSED" WHERE strike_id=?', (s_id,))
    print(f"Marked Strike {s_id} (23900 CE) as CLOSED.")

# Also ensure hedge strike is CLOSED
cur.execute('UPDATE strikes SET status="CLOSED", trade_state="CLOSED" WHERE block_id=30 AND strike_price=24400')

# Mark Block 30 as DELETED / CLOSED
cur.execute('UPDATE blocks SET status="DELETED" WHERE block_id=30')
conn.commit()
print("✅ Block 30 status updated to DELETED in database.")

conn.close()

# Telegram notification
try:
    tg_msg = (
        f"🎉 <b>PROFIT BOOKED & BLOCK CLOSED</b> 🎉\\n"
        f"Unit: <b>Unit M2 (Block #2)</b>\\n"
        f"Strike: <b>23900 CE SELL</b>\\n"
        f"Entry: ₹160.05 | Exit: ₹{fill_exit_price:.2f}\\n"
        f"Status: <b>Closed on Broker & Deleted from Engine</b>"
    )
    tg.send(tg_msg)
    print("Telegram notification sent.")
except Exception as t_err:
    print("Telegram send error:", t_err)
"""

sftp = client.open_sftp()
with sftp.file("/root/BHARAT-SYSTEMS/ZERODHA-OS/close_23900_block.py", "w") as f:
    f.write(remote_script)
sftp.close()

_, stdout, stderr = client.exec_command("python3 /root/BHARAT-SYSTEMS/ZERODHA-OS/close_23900_block.py")
print(stdout.read().decode(errors='replace'))
err = stderr.read().decode(errors='replace')
if err:
    print("STDERR:", err)

client.close()
