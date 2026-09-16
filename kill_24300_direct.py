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

db.load_secrets()
kite_executor.load_session_from_db()

print("=== 1. FETCHING CURRENT KITE POSITIONS ===")
if not kite_executor.ensure_logged_in():
    print("ERROR: Kite not logged in!")
    sys.exit(1)

kite = kite_executor.kite
pos = kite.positions()
net_pos = pos.get('net', [])

for p in net_pos:
    sym = p.get('tradingsymbol')
    qty = p.get('quantity', 0)
    print(f"Position: {sym} | Qty: {qty} | LTP: {p.get('last_price')} | PnL: Rs {p.get('pnl', 0):,.2f}")
    
    # 1. Close 24300 CE if open
    if '24300' in sym and qty != 0:
        if qty < 0:
            print(f"Executing BUY order on broker to close 24300 CE short (Qty: {abs(qty)})...")
            oid = kite.place_order(
                variety=kite.VARIETY_REGULAR,
                exchange=kite.EXCHANGE_NFO,
                tradingsymbol=sym,
                transaction_type=kite.TRANSACTION_TYPE_BUY,
                quantity=abs(qty),
                product=kite.PRODUCT_NRML,
                order_type=kite.ORDER_TYPE_MARKET
            )
            print(f"✅ Order placed for {sym}: Order ID {oid}")
        elif qty > 0:
            print(f"Executing SELL order on broker to close 24300 CE long (Qty: {qty})...")
            oid = kite.place_order(
                variety=kite.VARIETY_REGULAR,
                exchange=kite.EXCHANGE_NFO,
                tradingsymbol=sym,
                transaction_type=kite.TRANSACTION_TYPE_SELL,
                quantity=qty,
                product=kite.PRODUCT_NRML,
                order_type=kite.ORDER_TYPE_MARKET
            )
            print(f"✅ Order placed for {sym}: Order ID {oid}")

    # 2. Close 24800 CE (hedge) if open
    if '24800' in sym and qty != 0:
        if qty > 0:
            print(f"Executing SELL order on broker to close 24800 CE hedge (Qty: {qty})...")
            oid = kite.place_order(
                variety=kite.VARIETY_REGULAR,
                exchange=kite.EXCHANGE_NFO,
                tradingsymbol=sym,
                transaction_type=kite.TRANSACTION_TYPE_SELL,
                quantity=qty,
                product=kite.PRODUCT_NRML,
                order_type=kite.ORDER_TYPE_MARKET
            )
            print(f"✅ Order placed for {sym}: Order ID {oid}")
        elif qty < 0:
            print(f"Executing BUY order on broker to close 24800 CE (Qty: {abs(qty)})...")
            oid = kite.place_order(
                variety=kite.VARIETY_REGULAR,
                exchange=kite.EXCHANGE_NFO,
                tradingsymbol=sym,
                transaction_type=kite.TRANSACTION_TYPE_BUY,
                quantity=abs(qty),
                product=kite.PRODUCT_NRML,
                order_type=kite.ORDER_TYPE_MARKET
            )
            print(f"✅ Order placed for {sym}: Order ID {oid}")

print("\\n=== 2. FORCE DELETING BLOCK 1 / M1 FROM DATABASE ===")
all_blocks = db.get_all_blocks()
for b in all_blocks:
    if b.get('block_number') == 1 or (b.get('anchor_unit_name') or '').upper() == 'M1':
        bid = b['block_id']
        res = db.force_delete_block(bid)
        print(f"Force deleted Block #{b['block_number']} (ID {bid}): {res}")

print("\\n=== 3. FINAL VERIFICATION OF KITE POSITIONS ===")
import time
time.sleep(1.5)
pos_after = kite.positions()
net_pos_after = pos_after.get('net', [])
print("Remaining Active Positions on Broker:")
for p in net_pos_after:
    if p.get('quantity', 0) != 0:
        print(f"* {p.get('tradingsymbol')} | Qty: {p.get('quantity')} | LTP: {p.get('last_price')} | PnL: Rs {p.get('pnl', 0):,.2f}")

tg.send_silent("🛑 <b>KILL EXECUTED</b>: 24300 CE and 24800 CE have been fully closed/squared-off on Zerodha. Block 1 (M1) wiped from DB.")
print("ALL DONE.")
"""

sftp = client.open_sftp()
with sftp.file("/root/BHARAT-SYSTEMS/ZERODHA-OS/kill_24300_now.py", "w") as f:
    f.write(remote_script)
sftp.close()

_, stdout, stderr = client.exec_command("python3 /root/BHARAT-SYSTEMS/ZERODHA-OS/kill_24300_now.py")
print(stdout.read().decode(errors='replace'))
err = stderr.read().decode(errors='replace')
if err:
    print("STDERR:", err)

client.close()
