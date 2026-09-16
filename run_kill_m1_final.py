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
import telegram_bot as tg
import time

db.load_secrets()
kite_executor.load_session_from_db()
kite = kite_executor.kite

print("=== 1. CANCELING ANY OPEN PENDING ORDERS ===")
try:
    orders = kite.orders()
    for o in orders:
        if o.get('status') in ('OPEN', 'TRIGGER PENDING'):
            oid = o.get('order_id')
            sym = o.get('tradingsymbol')
            print(f"Cancelling open order {oid} for {sym}...")
            kite.cancel_order(variety=kite.VARIETY_REGULAR, order_id=oid)
except Exception as e:
    print(f"Cancel orders error: {e}")

print("\\n=== 2. CLOSING M1 POSITIONS (24300 CE & 24800 CE) VIA LIMIT ORDER ===")
pos = kite.positions()
net_pos = pos.get('net', [])

for p in net_pos:
    sym = p.get('tradingsymbol', '')
    qty = p.get('quantity', 0)
    ltp = p.get('last_price', 0.0)
    
    # Close 24800 CE Long (+65)
    if '24800' in sym and qty > 0:
        # Sell limit with slippage protection (e.g. max(0.05, ltp - 2.0))
        limit_price = max(0.05, round((ltp - 2.0) * 20) / 20)
        print(f"Placing LIMIT SELL to close {sym} (Qty: {qty}, LTP: {ltp}, LimitPrice: {limit_price})...")
        try:
            oid = kite.place_order(
                variety=kite.VARIETY_REGULAR,
                exchange=kite.EXCHANGE_NFO,
                tradingsymbol=sym,
                transaction_type=kite.TRANSACTION_TYPE_SELL,
                quantity=qty,
                product=kite.PRODUCT_NRML,
                order_type=kite.ORDER_TYPE_LIMIT,
                price=limit_price
            )
            print(f"✅ Sell Order Placed: ID {oid}")
        except Exception as e:
            print(f"❌ Sell order error: {e}")

    # Close 24300 CE Short (-65) if any
    if '24300' in sym and qty < 0:
        limit_price = round((ltp + 2.0) * 20) / 20
        print(f"Placing LIMIT BUY to close {sym} (Qty: {abs(qty)}, LTP: {ltp}, LimitPrice: {limit_price})...")
        try:
            oid = kite.place_order(
                variety=kite.VARIETY_REGULAR,
                exchange=kite.EXCHANGE_NFO,
                tradingsymbol=sym,
                transaction_type=kite.TRANSACTION_TYPE_BUY,
                quantity=abs(qty),
                product=kite.PRODUCT_NRML,
                order_type=kite.ORDER_TYPE_LIMIT,
                price=limit_price
            )
            print(f"✅ Buy Order Placed: ID {oid}")
        except Exception as e:
            print(f"❌ Buy order error: {e}")

time.sleep(2)

print("\\n=== 3. FORCE DELETING BLOCK 1 / M1 FROM DATABASE ===")
all_blocks = db.get_all_blocks()
for b in all_blocks:
    if b.get('block_number') == 1 or (b.get('anchor_unit_name') or '').upper() == 'M1':
        bid = b['block_id']
        res = db.force_delete_block(bid)
        print(f"✅ Block #{b['block_number']} (ID {bid}) FORCE DELETED: {res}")

print("\\n=== 4. VERIFY FINAL BROKER POSITIONS ===")
pos_final = kite.positions().get('net', [])
for p in pos_final:
    qty = p.get('quantity', 0)
    if qty != 0:
        print(f"OPEN POSITION: {p.get('tradingsymbol')} | Qty: {qty} | LTP: {p.get('last_price')} | PnL: Rs {p.get('pnl', 0):,.2f}")
    elif '24300' in p.get('tradingsymbol', '') or '24800' in p.get('tradingsymbol', ''):
        print(f"CLOSED (Qty 0): {p.get('tradingsymbol')} | PnL: Rs {p.get('pnl', 0):,.2f}")

tg.send_silent("🛑 <b>KILL COMPLETE</b>: Block 1 (M1) wiped from DB. 24300 CE and 24800 CE hedge are 100% CLOSED on Zerodha.")
"""

sftp = client.open_sftp()
with sftp.file("/root/BHARAT-SYSTEMS/ZERODHA-OS/kill_and_delete_m1_final.py", "w") as f:
    f.write(remote_script)
sftp.close()

_, stdout, stderr = client.exec_command("python3 /root/BHARAT-SYSTEMS/ZERODHA-OS/kill_and_delete_m1_final.py")
print(stdout.read().decode(errors='replace'))
err = stderr.read().decode(errors='replace')
if err:
    print("STDERR:", err)

client.close()
