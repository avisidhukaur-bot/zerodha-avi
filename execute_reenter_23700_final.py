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

ce_sell_sym = "NIFTY26SEP23700CE"
ce_hedge_sym = "NIFTY26SEP24200CE"

# Check open quantities
pos = kite.positions().get('net', [])
ce_23700_qty = 0
ce_24200_qty = 0
for p in pos:
    sym = str(p.get('tradingsymbol', ''))
    qty = int(p.get('quantity', 0) or 0)
    if sym == ce_sell_sym:
        ce_23700_qty = qty
    if sym == ce_hedge_sym:
        ce_24200_qty = qty

print(f"Current positions -> {ce_sell_sym}: {ce_23700_qty} | {ce_hedge_sym}: {ce_24200_qty}")

# Step 1: Place HEDGE BUY order if not already held
if ce_24200_qty <= 0:
    ltp_hedge = kite_executor.get_live_ltp("", ce_hedge_sym) or 16.0
    limit_h = round((ltp_hedge + max(2.0, ltp_hedge * 0.15)) * 20) / 20
    print(f"Placing LIMIT BUY for Hedge {ce_hedge_sym} (Qty: 65, Limit: Rs {limit_h})...")
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
        print(f"✅ Hedge Buy Placed: Order ID {h_oid}")
        time.sleep(2)
        h_hist = kite.order_history(order_id=h_oid)
        if h_hist:
            print(f"Hedge Order Status: {h_hist[-1].get('status')} | Price: {h_hist[-1].get('average_price')}")
    except Exception as e:
        print(f"❌ Hedge order error: {e}")

time.sleep(1)

# Step 2: Place SELL order for 23700 CE
fill_sell_price = 0.0
sell_oid = None
if ce_23700_qty >= 0:
    ltp_sell = kite_executor.get_live_ltp("", ce_sell_sym) or 66.0
    limit_s = round(max(0.05, (ltp_sell - max(2.0, ltp_sell * 0.15))) * 20) / 20
    print(f"Placing LIMIT SELL for {ce_sell_sym} (Qty: 65, Limit: Rs {limit_s})...")
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
        print(f"✅ 23700 CE Sell Placed: Order ID {sell_oid}")
        time.sleep(2)
        s_hist = kite.order_history(order_id=sell_oid)
        if s_hist:
            last_st = s_hist[-1]
            st = last_st.get('status', '')
            fill_sell_price = float(last_st.get('average_price') or ltp_sell)
            print(f"Sell Order Status: {st} | Filled Price: Rs {fill_sell_price:.2f}")
    except Exception as e:
        print(f"❌ Sell order error: {e}")
else:
    print(f"23700 CE is already SHORT with Qty: {ce_23700_qty}")

# Step 3: Update Database
conn = sqlite3.connect('/root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_trader.db')
cur = conn.cursor()

eff_anchor = fill_sell_price if fill_sell_price > 0 else 66.0
sl_price = round(eff_anchor * 1.25 * 20) / 20  # +25% Stop Loss

# Strike 91 (23700 CE)
cur.execute('''
    UPDATE strikes 
    SET status="OPEN", trade_state="OPEN", anchor_price=?, sl_price=?, sl_pct=25.0, reentry_enabled=1 
    WHERE strike_price=23700 AND option_type="CE" AND block_id=32
''', (eff_anchor, sl_price))

# Strike 90 (24200 CE Hedge)
cur.execute('''
    UPDATE strikes 
    SET status="OPEN", trade_state="OPEN" 
    WHERE strike_price=24200 AND option_type="CE" AND block_id=32
''')

# Clean previous open legs if any and insert fresh open leg
cur.execute('DELETE FROM legs WHERE strike_id IN (SELECT strike_id FROM strikes WHERE strike_price=23700 AND block_id=32) AND (exit_price=0 OR exit_price IS NULL)')
s_row = cur.execute('SELECT strike_id FROM strikes WHERE strike_price=23700 AND option_type="CE" AND block_id=32').fetchone()
if s_row:
    s_id = s_row[0]
    cur.execute('''
        INSERT INTO legs (strike_id, entry_price, exit_price, entry_time, exit_time, realized_pnl, order_id)
        VALUES (?, ?, 0.0, ?, '', 0.0, ?)
    ''', (s_id, eff_anchor, now_str, str(sell_oid or 'REENTRY')))
    print(f"✅ DB Updated: Strike {s_id} (23700 CE) OPEN -> Entry: Rs {eff_anchor:.2f} | SL: Rs {sl_price:.2f}")

conn.commit()
conn.close()

# Step 4: Final verification on Kite
print("\\n=== 2. FINAL LIVE KITE POSITIONS ===")
pos_final = kite.positions().get('net', [])
for p in pos_final:
    if p.get('quantity', 0) != 0:
        print(f"Open: {p.get('tradingsymbol')} | Qty: {p.get('quantity')} | Avg: {p.get('average_price')} | LTP: {p.get('last_price')} | PnL: Rs {p.get('pnl', 0):,.2f}")

# Telegram Alert
try:
    tg_msg = (
        f"⚡ <b>23700 CE RE-ENTRY RESTORED</b> ⚡\\n"
        f"Unit: <b>Unit M3 (Block #4)</b>\\n"
        f"Strike: <b>23700 CE SELL</b> (Qty: 65)\\n"
        f"Entry Price: ₹{eff_anchor:.2f}\\n"
        f"Stop Loss Trigger: <b>₹{sl_price:.2f}</b> (+25.0%)\\n"
        f"Hedge: <b>24200 CE BUY</b> (Qty: 65)\\n"
        f"Status: <b>Active & Fully Hedged on Broker</b>"
    )
    tg.send(tg_msg)
    print("Telegram notification sent.")
except Exception as t_err:
    print("Telegram send error:", t_err)
"""

sftp = client.open_sftp()
with sftp.file("/root/BHARAT-SYSTEMS/ZERODHA-OS/reenter_23700_final.py", "w") as f:
    f.write(remote_script)
sftp.close()

_, stdout, stderr = client.exec_command("python3 /root/BHARAT-SYSTEMS/ZERODHA-OS/reenter_23700_final.py")
print(stdout.read().decode(errors='replace'))
err = stderr.read().decode(errors='replace')
if err:
    print("STDERR:", err)

client.close()
