import paramiko
import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

secrets = {}
with open('secrets.txt', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            secrets[k.strip()] = v.strip()

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(secrets['VPS_IP'], username=secrets['VPS_USER'], password=secrets['VPS_PASSWORD'], timeout=15)

remote_script = """# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, '/root/BHARAT-SYSTEMS/ZERODHA-OS')
import db
import sqlite3
import time
from kite_executor import kite_executor
import telegram_bot as tg
from datetime import datetime
import pytz

IST = pytz.timezone("Asia/Kolkata")
now_str = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")

db.load_secrets()
kite_executor.load_session_from_db()

print("=== 1. VERIFYING LIVE BROKER POSITION FOR 22200 PE ===")
if not kite_executor.ensure_logged_in():
    print("ERROR: Kite login failed!")
    sys.exit(1)

kite = kite_executor.kite
pos = kite.positions().get('net', [])

target_pos = None
for p in pos:
    sym = p.get('tradingsymbol', '')
    qty = p.get('quantity', 0)
    if '22200' in sym and 'PE' in sym and qty < 0:
        target_pos = p
        print(f"Found active short position: {sym} | Qty: {qty} | Avg: {p.get('sell_price')} | LTP: {p.get('last_price')}")

if not target_pos:
    print("No open short position found for 22200 PE on broker!")
    sys.exit(0)

sym = target_pos.get('tradingsymbol')
qty_to_cover = abs(target_pos.get('quantity'))

print(f"\nPlacing BUY order to cover short leg {sym} (Qty: {qty_to_cover})...")
try:
    oid = kite.place_order(
        variety=kite.VARIETY_REGULAR,
        exchange=kite.EXCHANGE_NFO,
        tradingsymbol=sym,
        transaction_type=kite.TRANSACTION_TYPE_BUY,
        quantity=qty_to_cover,
        product=kite.PRODUCT_NRML,
        order_type=kite.ORDER_TYPE_MARKET
    )
    print(f"✅ Square-off order placed! Order ID: {oid}")
    
    time.sleep(1.5)
    orders = kite.orders()
    fill_exit_price = 0.0
    for o in orders:
        if str(o.get('order_id')) == str(oid):
            fill_exit_price = float(o.get('average_price') or o.get('price') or 0.0)
            print(f"Order Status: {o.get('status')} | Fill Price: Rs {fill_exit_price:.2f}")
            break
except Exception as e:
    print(f"❌ Error placing order: {e}")
    sys.exit(1)

print("\n=== 2. UPDATING DATABASE FOR STRIKE 22200 PE ===")
conn = sqlite3.connect('/root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_trader.db')
cur = conn.cursor()

# Update strike 219 (22200 PE) to CLOSED / SL_HIT
cur.execute('UPDATE strikes SET status="CLOSED", trade_state="SL_HIT" WHERE strike_price=22200 AND option_type="PE" AND leg_type="SELL"')

# Update legs table
leg = cur.execute('SELECT leg_id, entry_price FROM legs WHERE strike_id=219 AND (exit_price=0 OR exit_price IS NULL)').fetchone()
if leg:
    leg_id, entry_p = leg[0], float(leg[1] or 178.60)
    exit_p = fill_exit_price if fill_exit_price > 0 else 230.0
    pnl = (entry_p - exit_p) * qty_to_cover
    cur.execute('UPDATE legs SET exit_price=?, exit_time=?, realized_pnl=? WHERE leg_id=?', (exit_p, now_str, pnl, leg_id))
    print(f"Updated Leg {leg_id}: Entry=Rs {entry_p}, Exit=Rs {exit_p}, Realized PnL=Rs {pnl:,.2f}")

# Update hedge strike 218 to ORPHAN
cur.execute('UPDATE strikes SET trade_state="ORPHAN" WHERE strike_price=21700 AND option_type="PE" AND leg_type="HEDGE_BUY"')
conn.commit()
conn.close()
print("✅ Database updated: 22200 PE marked CLOSED, 21700 PE marked ORPHAN.")

# Check broker net positions after exit
time.sleep(1)
pos_after = kite.positions().get('net', [])
print("\n=== 3. BROKER POSITIONS AFTER EXIT ===")
for p in pos_after:
    if p.get('quantity') != 0:
        print(f"Open: {p.get('tradingsymbol')} | Qty: {p.get('quantity')} | LTP: {p.get('last_price')} | PnL: Rs {p.get('pnl')}")

# Telegram Alert
try:
    tg_msg = (
        f"🚨 <b>MANUAL STOP LOSS EXECUTED</b> 🚨\\n"
        f"Strike: <b>{sym}</b>\\n"
        f"Quantity: <b>{qty_to_cover}</b>\\n"
        f"Fill Exit Price: <b>₹{fill_exit_price:.2f}</b>\\n"
        f"Status: <b>Short leg CLOSED on Zerodha</b>\\n"
        f"🛡️ <b>21700 PE Hedge left active as ORPHAN capital shield</b>"
    )
    tg.send(tg_msg)
    print("Telegram alert sent.")
except Exception as t_err:
    print("Telegram error:", t_err)
"""

sftp = client.open_sftp()
with sftp.file('/root/BHARAT-SYSTEMS/ZERODHA-OS/close_22200_pe.py', 'w') as f:
    f.write(remote_script)
sftp.close()

_, stdout, stderr = client.exec_command('python3 /root/BHARAT-SYSTEMS/ZERODHA-OS/close_22200_pe.py')
out = stdout.read().decode(errors='replace')
err = stderr.read().decode(errors='replace')
print(out)
if err:
    print("STDERR:", err)

client.close()
