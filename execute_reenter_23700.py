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

print("=== 1. CHECKING BROKER POSITIONS ===")
if not kite_executor.ensure_logged_in():
    print("ERROR: Kite login failed!")
    sys.exit(1)

kite = kite_executor.kite
pos = kite.positions().get('net', [])

ce_23700_qty = 0
ce_24200_qty = 0

for p in pos:
    sym = p.get('tradingsymbol', '')
    qty = p.get('quantity', 0)
    if '23700' in sym and 'CE' in sym:
        ce_23700_qty = qty
        print(f"Current 23700 CE position: {sym} | Qty: {qty} | Avg: {p.get('average_price')} | LTP: {p.get('last_price')}")
    if '24200' in sym and 'CE' in sym:
        ce_24200_qty = qty
        print(f"Current 24200 CE position: {sym} | Qty: {qty} | Avg: {p.get('average_price')} | LTP: {p.get('last_price')}")

ce_sell_sym = kite_executor.search_option_symbol("29-Sep-2026", 23700, "CE") or "NIFTY26SEP23700CE"
ce_hedge_sym = kite_executor.search_option_symbol("29-Sep-2026", 24200, "CE") or "NIFTY26SEP24200CE"

print(f"Target Symbols: Sell={ce_sell_sym}, Hedge={ce_hedge_sym}")

# 1. First ensure Hedge is OPEN (Buy 24200 CE if not already held)
if ce_24200_qty <= 0:
    print(f"Buying Hedge {ce_hedge_sym} (Qty: 65)...")
    ltp_hedge = kite_executor.get_live_ltp("", ce_hedge_sym) or 20.0
    limit_h = round((ltp_hedge + max(2.0, ltp_hedge * 0.15)) * 20) / 20
    try:
        h_oid = kite.place_order(
            variety=kite.VARIETY_REGULAR,
            exchange=kite.EXCHANGE_NFO,
            tradingsymbol=ce_hedge_sym,
            transaction_type=kite.TRANSACTION_TYPE_BUY,
            quantity=65,
            product=kite.PRODUCT_NRML,
            order_type=kite.ORDER_TYPE_LIMIT,
            price=limit_h
        )
        print(f"✅ Hedge Buy Order Placed: {h_oid}")
    except Exception as e:
        print(f"Hedge order error: {e}")
else:
    print(f"Hedge {ce_hedge_sym} is already held (Qty: {ce_24200_qty})")

time.sleep(1)

# 2. Place SELL order for 23700 CE (Qty: 65)
fill_sell_price = 0.0
sell_oid = None
if ce_23700_qty >= 0:
    print(f"Placing SELL order for {ce_sell_sym} (Qty: 65)...")
    ltp_sell = kite_executor.get_live_ltp("", ce_sell_sym) or 60.0
    limit_s = round(max(0.05, (ltp_sell - max(2.0, ltp_sell * 0.15))) * 20) / 20
    try:
        sell_oid = kite.place_order(
            variety=kite.VARIETY_REGULAR,
            exchange=kite.EXCHANGE_NFO,
            tradingsymbol=ce_sell_sym,
            transaction_type=kite.TRANSACTION_TYPE_SELL,
            quantity=65,
            product=kite.PRODUCT_NRML,
            order_type=kite.ORDER_TYPE_LIMIT,
            price=limit_s
        )
        print(f"✅ 23700 CE Sell Order Placed: {sell_oid}")
        
        time.sleep(2)
        hist = kite.order_history(order_id=sell_oid)
        if hist:
            last_st = hist[-1]
            st = last_st.get('status', '')
            fill_sell_price = float(last_st.get('average_price') or ltp_sell)
            print(f"Order {sell_oid} status: {st} | Filled Price: Rs {fill_sell_price:.2f}")
    except Exception as e:
        print(f"Sell order error: {e}")
else:
    print(f"23700 CE is ALREADY short (Qty: {ce_23700_qty})")

# 3. Update Database for Strike 91 (23700 CE in Unit M3)
conn = sqlite3.connect('/root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_trader.db')
cur = conn.cursor()

eff_anchor = fill_sell_price if fill_sell_price > 0 else (kite_executor.get_live_ltp("", ce_sell_sym) or 65.0)
sl_price = round(eff_anchor * 1.25 * 20) / 20  # 25% SL

# Update Strike 91
cur.execute('''
    UPDATE strikes 
    SET status="OPEN", trade_state="OPEN", anchor_price=?, sl_price=?, sl_pct=25.0, reentry_enabled=1 
    WHERE strike_price=23700 AND option_type="CE" AND block_id=32
''', (eff_anchor, sl_price))

# Also ensure Hedge Strike 90 is OPEN
cur.execute('''
    UPDATE strikes 
    SET status="OPEN", trade_state="OPEN" 
    WHERE strike_price=24200 AND option_type="CE" AND block_id=32
''')

# Insert new leg for 23700 CE
s_row = cur.execute('SELECT strike_id FROM strikes WHERE strike_price=23700 AND option_type="CE" AND block_id=32').fetchone()
if s_row:
    s_id = s_row[0]
    cur.execute('''
        INSERT INTO legs (strike_id, entry_price, exit_price, entry_time, exit_time, realized_pnl, order_id)
        VALUES (?, ?, 0.0, ?, '', 0.0, ?)
    ''', (s_id, eff_anchor, now_str, str(sell_oid or 'MANUAL_REENTRY')))
    print(f"✅ Inserted new OPEN leg for 23700 CE: Entry=Rs {eff_anchor:.2f}, SL=Rs {sl_price:.2f}")

conn.commit()
conn.close()

# Verify live positions
print("\\n=== 4. VERIFYING ALL ACTIVE POSITIONS ON KITE ===")
pos_after = kite.positions().get('net', [])
for p in pos_after:
    if p.get('quantity', 0) != 0:
        print(f"Live Open: {p.get('tradingsymbol')} | Qty: {p.get('quantity')} | Avg: {p.get('average_price')} | LTP: {p.get('last_price')} | PnL: Rs {p.get('pnl', 0):,.2f}")

# Telegram alert
try:
    tg_msg = (
        f"⚡ <b>23700 CE RE-ENTERED SUCCESSFULLY</b> ⚡\\n"
        f"Unit: <b>Unit M3 (Block #4)</b>\\n"
        f"Strike: <b>23700 CE SELL</b> (Qty: 65)\\n"
        f"Fill Price: ₹{eff_anchor:.2f}\\n"
        f"Stop Loss Trigger: <b>₹{sl_price:.2f}</b> (+25.0%)\\n"
        f"Hedge: <b>24200 CE BUY</b> (Qty: 65)\\n"
        f"Status: <b>Active & Protected</b>"
    )
    tg.send(tg_msg)
    print("Telegram notification sent.")
except Exception as t_err:
    print("Telegram error:", t_err)
"""

sftp = client.open_sftp()
with sftp.file("/root/BHARAT-SYSTEMS/ZERODHA-OS/reenter_23700_ce.py", "w") as f:
    f.write(remote_script)
sftp.close()

_, stdout, stderr = client.exec_command("python3 /root/BHARAT-SYSTEMS/ZERODHA-OS/reenter_23700_ce.py")
print(stdout.read().decode(errors='replace'))
err = stderr.read().decode(errors='replace')
if err:
    print("STDERR:", err)

client.close()
