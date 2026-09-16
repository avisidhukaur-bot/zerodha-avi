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

db.load_secrets()
kite_executor.load_session_from_db()

if not kite_executor.ensure_logged_in():
    print("ERROR: Kite login failed!")
    sys.exit(1)

kite = kite_executor.kite
trades = kite.trades()

print("=== TODAY'S EXECUTED TRADES (15-SEP-2026) ===")
total_buy_val = 0.0
total_sell_val = 0.0
orders_set = set()

for t in trades:
    sym = t.get('tradingsymbol')
    qty = int(t.get('quantity', 0))
    price = float(t.get('average_price', 0.0))
    tx_type = t.get('transaction_type')
    order_id = t.get('order_id')
    val = qty * price
    orders_set.add(order_id)
    
    if tx_type == "BUY":
        total_buy_val += val
    else:
        total_sell_val += val
        
    print(f"- {tx_type:4} | {sym:20} | Qty: {qty:3} | Price: Rs {price:6.2f} | Value: Rs {val:8.2f} | Order ID: {order_id}")

orders_count = len(orders_set)
trades_count = len(trades)

# Zerodha F&O Option Taxation Breakdown
brokerage = orders_count * 20.0  # Rs 20 per executed order
stt = total_sell_val * 0.001       # 0.1% on sell turnover (STT)
exchange_turnover = (total_buy_val + total_sell_val) * 0.0003503  # NSE Transaction fee 0.03503%
sebi_turnover = (total_buy_val + total_sell_val) * 0.000001        # SEBI Rs 10 per crore
stamp_duty = total_buy_val * 0.00003                                # 0.003% on buy turnover
gst = (brokerage + exchange_turnover + sebi_turnover) * 0.18        # 18% GST on brokerage + exchange + SEBI

total_charges = brokerage + stt + exchange_turnover + sebi_turnover + stamp_duty + gst

print("\\n=== TAXES & CHARGES BREAKDOWN ===")
print(f"Total Executed Orders  : {orders_count}")
print(f"Total Trades           : {trades_count}")
print(f"Total Buy Turnover     : Rs {total_buy_val:,.2f}")
print(f"Total Sell Turnover    : Rs {total_sell_val:,.2f}")
print(f"1. Brokerage (Zerodha) : Rs {brokerage:,.2f}")
print(f"2. STT (Securities Tax): Rs {stt:,.2f}")
print(f"3. Exchange Turn. Fee  : Rs {exchange_turnover:,.2f}")
print(f"4. GST (18%)           : Rs {gst:,.2f}")
print(f"5. Stamp Duty (State)  : Rs {stamp_duty:,.2f}")
print(f"6. SEBI Charges        : Rs {sebi_turnover:,.2f}")
print(f"----------------------------------------")
print(f"🔥 TOTAL TAXES & FEES  : Rs {total_charges:,.2f}")

# Positions summary
pos = kite.positions()
net_pos = pos.get('net', [])
total_gross_pnl = sum(float(p.get('pnl', 0.0) or 0.0) for p in net_pos)

# Realized booked portion vs Open
net_after_tax = total_gross_pnl - total_charges

print("\\n=== NET PROFIT IN HAND ===")
print(f"Gross Portfolio Profit : Rs {total_gross_pnl:,.2f}")
print(f"Less: Total Taxes/Fees : Rs {total_charges:,.2f}")
print(f"🏆 NET IN-HAND PROFIT  : Rs {net_after_tax:,.2f}")
"""

sftp = client.open_sftp()
with sftp.file("/root/BHARAT-SYSTEMS/ZERODHA-OS/calc_today_taxes.py", "w") as f:
    f.write(remote_script)
sftp.close()

_, stdout, stderr = client.exec_command("python3 /root/BHARAT-SYSTEMS/ZERODHA-OS/calc_today_taxes.py")
print(stdout.read().decode(errors='replace'))
err = stderr.read().decode(errors='replace')
if err:
    print("STDERR:", err)

client.close()
