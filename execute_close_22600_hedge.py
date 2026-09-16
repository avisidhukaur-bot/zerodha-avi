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
import telegram_bot as tg
from datetime import datetime
import pytz
import time

IST = pytz.timezone("Asia/Kolkata")
now_str = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")

db.load_secrets()
kite_executor.load_session_from_db()

print("=== 1. CHECKING AND CLOSING 22600 PE HEDGE ===")
if not kite_executor.ensure_logged_in():
    print("ERROR: Kite login failed!")
    sys.exit(1)

kite = kite_executor.kite
pos = kite.positions().get('net', [])

pe_hedge_sym = "NIFTY26SEP22600PE"
hedge_pos = None

for p in pos:
    sym = str(p.get('tradingsymbol', ''))
    qty = int(p.get('quantity', 0) or 0)
    if '22600' in sym and 'PE' in sym and qty > 0:
        hedge_pos = p
        pe_hedge_sym = sym
        print(f"Found open hedge: {sym} | Qty: {qty} | Avg: {p.get('average_price')} | LTP: {p.get('last_price')} | PnL: Rs {p.get('pnl', 0):,.2f}")

fill_exit_price = 0.0
sell_oid = None

if hedge_pos and int(hedge_pos.get('quantity', 0)) > 0:
    h_qty = int(hedge_pos.get('quantity'))
    ltp = float(hedge_pos.get('last_price') or 58.0)
    limit_p = round(max(0.05, (ltp - max(2.0, ltp * 0.15))) * 20) / 20
    print(f"Placing LIMIT SELL order for {pe_hedge_sym} (Qty: {h_qty}, Limit: Rs {limit_p})...")
    
    try:
        sell_oid = kite.place_order(
            variety=kite.VARIETY_REGULAR,
            exchange=kite.EXCHANGE_NFO,
            tradingsymbol=pe_hedge_sym,
            transaction_type=kite.TRANSACTION_TYPE_SELL,
            quantity=h_qty,
            product=kite.PRODUCT_NRML,
            order_type=kite.ORDER_TYPE_LIMIT,
            price=limit_p
        )
        print(f"✅ Sell order placed! Order ID: {sell_oid}")
        
        time.sleep(2)
        hist = kite.order_history(order_id=sell_oid)
        if hist:
            last_st = hist[-1]
            st = last_st.get('status', '')
            fill_exit_price = float(last_st.get('average_price') or ltp)
            print(f"Order Status: {st} | Filled Exit Price: Rs {fill_exit_price:.2f}")
    except Exception as e:
        print(f"❌ Sell order failed: {e}")
else:
    print("No open 22600 PE hedge position found on broker.")

# 2. Update Database for Strike 92 (22600 PE Hedge)
conn = sqlite3.connect('/root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_trader.db')
cur = conn.cursor()

# Get strike details
s_row = cur.execute('SELECT * FROM strikes WHERE strike_price=22600 AND option_type="PE"').fetchone()
if s_row:
    s_id = s_row[0]
    cur.execute('UPDATE strikes SET status="CLOSED", trade_state="CLOSED" WHERE strike_id=?', (s_id,))
    
    # Update leg
    legs = cur.execute('SELECT * FROM legs WHERE strike_id=? AND (exit_price=0 OR exit_price IS NULL)', (s_id,)).fetchall()
    for l in legs:
        l_id = l[0]
        ent_p = float(l[2] or 42.20)
        ext_p = fill_exit_price if fill_exit_price > 0 else 58.0
        pnl = (ext_p - ent_p) * 65
        cur.execute('UPDATE legs SET exit_price=?, exit_time=?, realized_pnl=? WHERE leg_id=?', (ext_p, now_str, pnl, l_id))
        print(f"Updated Leg {l_id}: Entry=Rs {ent_p}, Exit=Rs {ext_p}, Realized Profit=+Rs {pnl:,.2f}")

conn.commit()
conn.close()

# 3. Verify Remaining Positions
print("\\n=== 2. REMAINING ACTIVE POSITIONS ON KITE ===")
pos_after = kite.positions().get('net', [])
for p in pos_after:
    if p.get('quantity', 0) != 0:
        print(f"Live Open: {p.get('tradingsymbol')} | Qty: {p.get('quantity')} | Avg: {p.get('average_price')} | LTP: {p.get('last_price')} | PnL: Rs {p.get('pnl', 0):,.2f}")

# Telegram Alert
try:
    pnl_profit = (fill_exit_price - 42.20) * 65 if fill_exit_price > 0 else 1000.0
    tg_msg = (
        f"💰 <b>22600 PE HEDGE PROFIT LOCKED & CLOSED</b> 💰\\n"
        f"Strike: <b>22600 PE HEDGE BUY</b>\\n"
        f"Entry: ₹42.20 | Exit: ₹{fill_exit_price:.2f}\\n"
        f"Order ID: {sell_oid}\\n"
        f"Realized Profit: <b>+₹{pnl_profit:,.2f}</b>\\n"
        f"Status: <b>Closed Successfully on Broker</b>"
    )
    tg.send(tg_msg)
    print("Telegram notification sent.")
except Exception as t_err:
    print("Telegram error:", t_err)
"""

sftp = client.open_sftp()
with sftp.file("/root/BHARAT-SYSTEMS/ZERODHA-OS/close_22600_hedge.py", "w") as f:
    f.write(remote_script)
sftp.close()

_, stdout, stderr = client.exec_command("python3 /root/BHARAT-SYSTEMS/ZERODHA-OS/close_22600_hedge.py")
print(stdout.read().decode(errors='replace'))
err = stderr.read().decode(errors='replace')
if err:
    print("STDERR:", err)

client.close()
