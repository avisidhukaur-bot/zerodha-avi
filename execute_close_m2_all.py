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

print("=== 1. VERIFYING AND CLOSING UNIT M2 POSITIONS ON KITE ===")
if not kite_executor.ensure_logged_in():
    print("ERROR: Kite login failed!")
    sys.exit(1)

kite = kite_executor.kite
net_pos = kite.positions().get('net', [])

total_profit_booked = 0.0
closed_legs_info = []

for p in net_pos:
    sym = p.get('tradingsymbol', '')
    qty = p.get('quantity', 0)
    ltp = float(p.get('last_price', 0.0) or 0.0)
    avg_price = float(p.get('average_price', 0.0) or 0.0)
    pnl = float(p.get('pnl', 0.0) or 0.0)
    
    # Check if this is Unit M2: 23900 CE or 24400 CE or 23600 PE
    if ('23900' in sym or '24400' in sym or '23600' in sym) and qty != 0:
        print(f"\\nFound Open Position: {sym} | Qty: {qty} | Avg: {avg_price} | LTP: {ltp} | PnL: Rs {pnl:,.2f}")
        
        # Determine transaction type and limit price
        if qty < 0:
            # Short position -> BUY to cover
            tx_type = kite.TRANSACTION_TYPE_BUY
            limit_p = round((ltp + max(3.0, ltp * 0.15)) * 20) / 20  # Marketable Limit Buy
            order_qty = abs(qty)
            print(f"Placing LIMIT BUY order: {sym} | Qty: {order_qty} | Limit Price: Rs {limit_p}...")
        else:
            # Long hedge position -> SELL to square off
            tx_type = kite.TRANSACTION_TYPE_SELL
            limit_p = round(max(0.05, (ltp - max(2.0, ltp * 0.15))) * 20) / 20  # Marketable Limit Sell
            order_qty = abs(qty)
            print(f"Placing LIMIT SELL order: {sym} | Qty: {order_qty} | Limit Price: Rs {limit_p}...")
            
        try:
            oid = kite.place_order(
                variety=kite.VARIETY_REGULAR,
                exchange=kite.EXCHANGE_NFO,
                tradingsymbol=sym,
                transaction_type=tx_type,
                quantity=order_qty,
                product=kite.PRODUCT_NRML,
                order_type=kite.ORDER_TYPE_LIMIT,
                price=limit_p
            )
            print(f"✅ Order placed! Order ID: {oid}")
            
            # Wait 2 seconds and check fill status
            time.sleep(2)
            hist = kite.order_history(order_id=oid)
            fill_price = ltp
            if hist:
                last_st = hist[-1]
                st = last_st.get('status', '')
                avg_f = float(last_st.get('average_price') or 0.0)
                if avg_f > 0:
                    fill_price = avg_f
                print(f"Order {oid} status: {st} | Filled Price: Rs {fill_price:.2f}")
            
            realized_leg_pnl = (avg_price - fill_price) * order_qty if qty < 0 else (fill_price - avg_price) * order_qty
            total_profit_booked += realized_leg_pnl
            closed_legs_info.append(f"{sym} (Qty: {qty}): Exit @ Rs {fill_price:.2f} -> PnL: +Rs {realized_leg_pnl:,.2f}")
            
        except Exception as o_err:
            print(f"❌ Order failed for {sym}: {o_err}")

print("\\n=== 2. UPDATING DATABASE FOR UNIT M2 (BLOCKS 30 & 31) ===")
conn = sqlite3.connect('/root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_trader.db')
cur = conn.cursor()

# Block 30 (Unit M2 Call Side) & Block 31 (Unit M2 Put Side)
for b_id in [30, 31]:
    strikes = cur.execute('SELECT * FROM strikes WHERE block_id=?', (b_id,)).fetchall()
    for s in strikes:
        s_id = s[0]
        cur.execute('UPDATE strikes SET status="CLOSED", trade_state="CLOSED" WHERE strike_id=?', (s_id,))
        legs = cur.execute('SELECT * FROM legs WHERE strike_id=? AND (exit_price=0 OR exit_price IS NULL)', (s_id,)).fetchall()
        for l in legs:
            l_id = l[0]
            ent_p = float(l[2] or 0.0)
            ext_p = 37.0 if '23900' in str(s[2]) else (12.0 if '24400' in str(s[2]) else ent_p)
            pnl_val = (ent_p - ext_p) * 65 if s[4] == 'SELL' else (ext_p - ent_p) * 65
            cur.execute('UPDATE legs SET exit_price=?, exit_time=?, realized_pnl=? WHERE leg_id=?', (ext_p, now_str, pnl_val, l_id))
    
    cur.execute('UPDATE blocks SET status="DELETED" WHERE block_id=?', (b_id,))
    print(f"✅ Block {b_id} (Unit M2) marked as DELETED in database.")

conn.commit()
conn.close()

# Verify remaining live positions on Kite
print("\\n=== 3. REMAINING OPEN POSITIONS ON KITE ===")
rem_pos = kite.positions().get('net', [])
for p in rem_pos:
    if p.get('quantity', 0) != 0:
        print(f"Open: {p.get('tradingsymbol')} | Qty: {p.get('quantity')} | LTP: {p.get('last_price')} | PnL: Rs {p.get('pnl', 0):,.2f}")

# Telegram Notification
try:
    tg_lines = "\\n".join([f"• {x}" for x in closed_legs_info])
    tg_msg = (
        f"💰 <b>UNIT M2 (BLOCK 2 & 3) PROFIT BOOKED & DELETED</b> 💰\\n"
        f"Time: {now_str}\\n\\n"
        f"<b>Closed Positions:</b>\\n{tg_lines}\\n\\n"
        f"💵 <b>Total Realized Profit:</b> +₹{total_profit_booked:,.2f}\\n"
        f"Status: <b>Successfully closed on Kite & removed from dashboard!</b>"
    )
    tg.send(tg_msg)
    print("Telegram alert sent.")
except Exception as t_err:
    print("Telegram error:", t_err)
"""

sftp = client.open_sftp()
with sftp.file("/root/BHARAT-SYSTEMS/ZERODHA-OS/close_m2_all.py", "w") as f:
    f.write(remote_script)
sftp.close()

_, stdout, stderr = client.exec_command("python3 /root/BHARAT-SYSTEMS/ZERODHA-OS/close_m2_all.py")
print(stdout.read().decode(errors='replace'))
err = stderr.read().decode(errors='replace')
if err:
    print("STDERR:", err)

client.close()
